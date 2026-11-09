# Hane 前端协议

服务端：Flask + Flask-SocketIO，默认 `http://localhost:5000`。

对话走 **WebSocket**（Socket.IO），其他（模型列表、记忆整理、阶段切换等）走 **HTTP**。

---

## 1. WebSocket（对话）

连接地址：与服务同源，走 Socket.IO，自动协商 `websocket`（退化 `polling`）。

### 1.1 客户端 → 服务端

#### `message` — 发一条用户消息

```json
{
  "turn_id": "c1a7f6e2-...",
  "text": "今天天气怎么样",
  "my_partial": ""
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `text` | ✅ | STT 当前转写出的用户文本 |
| `turn_id` |  | 前端给这轮对话分配的 ID（建议 UUID）；服务端收到后会在本轮所有返回事件里**原样带回来**，前端可据此把 chunk / done / end 绑到正确的消息上。不提供则后端生成 |
| `my_partial` |  | 打断场景专用：AI 被打断**那一刻嘴上正在说的最后几个字**（定位打断点即可，不是整段已播放文本）。没打断就传空或省略 |
| `channel` |  | messengers 传 `"discord"` / `"telegram"`（她在手机上看文字，用 `text_scene`）；舞台不传 |
| `voice` |  | 舞台关掉了她的声音时，发声端传 `false`：这轮回复是给人读的，深层不加「四句左右」的语音长度提示（`webui.VOICE_REPLY_NOTE`）。不传 = 会说出口 |

模型搭配由后端固定（表层 `groq-qwen3-32b`，深层 `claude-4.6-sonnet`），前端不传、不选。

服务端收到后的行为：

1. 若 `my_partial` 非空：找到历史里最近一条 `protected=True` 的 turn（上一轮被打断的那轮），把它标成 `interrupted=True`，如果它的生成还在跑就取消（partial 被保留）。
2. 从历史末尾开始删掉所有未保护（未 `protected`）的 turn，它们在跑的生成也一并取消。
3. 建一条新 turn，开始流式生成。

这意味着：**短停顿连发 `message`，前面的推测生成自动作废，只有最新那条有效。**

#### `protect` — 把最新的 turn 标为保护

```json
{}
```

时机：**TTS 开始播这一轮的回复时**立刻调用。一旦保护，后续 `message` 就不会把它从历史里清掉。

服务端会返回一个 Socket.IO ACK（`{"ok": true}` / `{"ok": false}`）。正常情况下不必等这个 ACK，`emit` 即发即走就行。

> 边缘情况说明：服务端 `protect` 和 `message` 两个 handler 在不同线程并发跑。若某轮 `protect` 和下一条 `message` 由于网络抖动等原因几乎"贴着到"服务端，`message` 可能先抢到 `_hist_lock` 并把尚未 protected 的那条（已完成生成的）turn 当作未保护的推测轮次 prune 掉。
> 真实场景里用户停嘴 → 发 `protect` → 用户再开口 → STT 出转写 → 发 `message`，这条链路天然有秒级间隔，基本不会触发。如果需要绝对规避，前端可以用 `socket.emitWithAck('protect', {})` / `sio.call('protect', {})` 等 ACK 再继续。

> 没有 TTS 的调试场景（比如 `index.html`）可以在每次 `end` 之后自动发 `protect`，模拟"TTS 全程没被打断"的情况。

### 1.2 服务端 → 客户端

按时序。**所有事件的载荷都会带上 `turn_id`**（就是前端在 `message` 里提供的那个，或后端生成并沿用的那个），便于前端把流事件绑到正确的消息上：

| 事件 | 载荷 | 说明 |
|------|------|------|
| `begin` | `{turn_id}` | 一次新生成开始 |
| `surface_chunk` | `{turn_id, text}` | 表层流式片段（一字一字） |
| `surface_done` | `{turn_id, mode, reply, tone, recall, raw}` | 表层完成。`mode` ∈ `"say"` / `"think"` / `"say+think"` |
| `deep_chunk` | `{turn_id, text}` | 深层流式片段（仅当 `mode` 需要深层时才会有） |
| `deep_done` | `{turn_id, speech, raw}` | 深层完成 |
| `error` | `{turn_id, message}` | 出错；这轮 turn 已从历史丢弃，后端紧跟一个 `end` |
| `end` | `{turn_id}` | 生成终点（正常完成 或 出错后） |

关于 mode：

- `say`：表层直接给回复，不跑深层。**`end` 会在 `surface_done` 之后直接到来。**
- `think`：表层不说出口，只做 recall，让深层接着想。前端不要把 surface 的内容当作要 TTS 的回复。
- `say+think`：表层先"脱口而出"一句 (`reply`)，然后深层继续生成真正的回复。TTS 可以先播 `reply`，等深层的 `deep_done` 再接着播。

### 1.3 取消语义

没有显式的 cancel 事件。**前端只要再发一次 `message`，就自动作废所有未保护的生成。**

被作废的生成会停止消耗上游 LLM（`threading.Event` 中断流式读取），不会再 `emit` 剩余 chunk，也不会发 `end` —— 因为作废这件事是前端发起的，前端自己知道。

### 1.4 `disconnect`

WebSocket 断开时，所有归属这个 `sid` 的在跑生成按 `discard` 取消，历史里的对应 turn 被清掉。其他客户端不受影响。

---

## 2. 打断场景的约定（前端负责）

假设 AI 正在 TTS 播放 turn N 的回复（前端已发过 `protect`），用户插话打断：

1. TTS 停掉。
2. 记下打断**那一刻 AI 嘴上正在说的最后几个字**（而不是整段已播放的文本），作为 `my_partial`。比如 AI 正说到"……我昨天去了图书馆，看到一本"被打断，就取 `"看到一本"` 之类即可。
3. STT 开始听用户，每次短停顿发一次 `message`：
   ```json
   {"text": "<用户到目前为止说的>", "my_partial": "<AI 被打断时的最后那几个字>"}
   ```
4. 长停顿（认定用户说完了）→ 用最终的 text 发一次 `message`，然后开始 TTS 播新的回复，TTS 一响就 `protect`。

后端把打断信息写进下一轮的 `user` 字段：`当我说到"<my_partial>"的时候，对方说："<text>"`。`my_partial` 的语义就是**定位打断点**——完整已播出的内容后端已经单独存在上一轮 turn 的 `surface_partial / deep_partial` 里了，这里再塞一遍反而把 prompt 撑得又长又别扭。

`my_partial` 长度建议 4–10 个字足够，LLM 只需要知道"我话说到哪儿被打断的"。

---

## 3. HTTP 接口

### `GET /` — 调试 UI

返回 `templates/index.html`。仅测试用。

### `GET /api/relationship_stage` / `POST /api/relationship_stage`

查询/切换当前关系阶段（给调试 UI 用的；生产前端一般不动）。

```http
GET  → {"current": 0, "stages": [{"index": 0, "name": "..."}, ...]}
POST  {"stage": 1}  → {"current": 1, "name": "..."}
```

### `POST /api/reload`

重新加载 `例子.txt` / `表层.txt` / `记忆1.txt`。改模板文件后按一下。

```json
{"ok": true, "deep_length": 12345, "surface_length": 6789}
```

### `GET /api/template`

调试用，返回当前深层 prompt 的长度等信息。

### `POST /api/clear_memory`

**清空**所有对话记录和已整理的记忆。慎用。

```json
{"status": "ok"}
```

### `POST /api/consolidate` — 手动触发记忆整理（SSE）

```json
{
  "level": "10min",
  "checkpoint": "4 2",
  "hour": 4,
  "period_name": "清晨"
}
```

- 记忆整理固定用 `claude-4.6-sonnet`，前端不用传 `model`
- `level` 可选：`10min` / `hour` / `period`
- 不给 `checkpoint` 时按当前时间推算

返回 `text/event-stream`，每行 `data: {...}`：
- `{"t": "..."}` 流式片段
- `{"done": true, "raw": "...", "memory_id": "..."}`
- `{"error": "..."}`

正常情况下不用前端调用，后台整理线程会自动跑。

---

## 4. 模型调用错误处理建议

- 收到 `error` → 把提示显示给用户，标记当前 turn 失败；不要自动重试（后端会紧跟 `end`，用户自己说下一句即可）。
- WS `disconnect` → 清掉本地"正在播"状态，重连后重新发未完成的消息。
- 长时间（>30s）没收到任何事件 → 主动关连接重连。

---

## 5. 字段/类型小抄

```ts
// message
type MessageIn = {
  text: string;          // 必填
  turn_id?: string;      // 建议传（UUID），服务端会在所有返回事件里原样带回
  my_partial?: string;   // 打断场景才传
  channel?: string;      // messengers: "discord" | "telegram"
  voice?: boolean;       // false: the page has her voice off (no ~4-sentence voice note)
};

// 服务端推给前端（所有 out 事件都带 turn_id）
type TurnMeta         = { turn_id: string };
type BeginOut         = TurnMeta;
type SurfaceChunkOut  = TurnMeta & { text: string };
type SurfaceDoneOut   = TurnMeta & {
  mode: 'say' | 'think' | 'say+think';
  reply: string;
  tone: string;
  recall: string;
  raw: string;
};
type DeepChunkOut     = TurnMeta & { text: string };
type DeepDoneOut      = TurnMeta & { speech: string; raw: string };
type ErrorOut         = Partial<TurnMeta> & { message: string };
type EndOut           = TurnMeta;
```
