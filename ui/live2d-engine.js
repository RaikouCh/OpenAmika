/* OpenAmika Live2D engine
 *
 * Ported from the AmikaCrescentineTravelProp viewer (pixi-live2d-display 0.4.0 on
 * PixiJS legacy 6.5.8 + Cubism Core), adapted for OpenAmika:
 *   - emotion vocabulary = the 69 `register_emotion` keys (served by /api/avatar/models);
 *   - mouth parameter names are configurable per model (ParamMouthOpenY/ParamMouthForm defaults);
 *   - THE audio sink of the page: the Use page feeds every tts_audio/sfx chunk here, so
 *     face and voice stay atomically coupled — the emotion is applied at PLAYBACK START
 *     of its sentence, never on arrival (that coupling is what keeps sync drift at zero);
 *   - banks fall back to the motion-file naming convention server-side; the engine just
 *     consumes {emotes:[{name,likelihood}], movements:[{name,likelihood}]} per key.
 *
 * Requires (loaded before this file):
 *   /ui/vendor/live2dcubismcore.min.js
 *   /ui/vendor/pixi-legacy.min.js
 *   /ui/vendor/cubism4.min.js
 *
 * Page API:
 *   const avatar = OpenAmikaAvatar;
 *   await avatar.init({canvas, area, onChunkStart, onQueueEmpty, onModelChange, fixed});
 *     (fixed: the desktop pet — she always fills the stage: no drag/zoom of the model, no saved view)
 *   avatar.playChunk(b64wav, emotionKey|null, pauseAfterSec|0, meta|null)
 *   avatar.surfaceEmotion(key)      // early face reaction while nothing is speaking
 *   avatar.flush()                  // barge-in / reset: stop audio, clear queue, idle
 *   avatar.switchModel(id); avatar.setVolume(v01); avatar.models; avatar.currentId;
 *   avatar.setBusy(on)              // her animated "loading" emote: waiting on the deep layer or a helper
 *   avatar.loadAgent(); avatar.setAgentVisible(on); avatar.setAgentBase("idle"|"working");
 *   avatar.setAgentState(mood, ms)  // the agent avatar's passing mood (talk/listen/happy/worried/surprise)
 *   avatar.converse("amika"|"agent", ms, mood?)   // she and the agent avatar turn to each other
 *   avatar.anchors()                // {her, agent}: head positions (stage px) for the page's speech bubbles
 */
(function () {
  "use strict";

  // ── state ──
  let pixiApp = null;
  let live2dModel = null;
  let modelStates = {};          // id -> {model, motionAssets, expressionAssets, idleMotionBank, emotionBanks, config, originalWidth, originalHeight}
  let registry = [];             // /api/avatar/models payload
  let ALL_EMOTIONS = [];
  let currentId = null;

  let motionAssets = [], expressionAssets = [], idleMotionBank = [], emotionBanks = {};
  let mouthOpenParam = "ParamMouthOpenY", mouthFormParam = "ParamMouthForm";
  let currentEmotion = null;
  let activeExpressions = new Set();
  let _lastPlayedMotionName = null, _lastIdleMotionName = null;
  let _emotionMotionLoopInterval = null, _idleMotionLoopInterval = null;
  let _emotionAudioPlaying = false;

  // lip sync
  let lipSyncEnabled = false;
  let wsAudioContext = null, wsAnalyser = null, wsAudioDataArray = null, wsGainNode = null;
  let outputVolumeAnalyser = null, outputVolumeData = null;
  let pendingMouthOpen, pendingMouthForm, lastMouthOpen, lastMouthForm;
  let _wsLipSyncBound = null;
  const lipSyncCalibration = {
    sensitivity: parseFloat(safeGet("openamika-lipSyncGain") || "1.5"),
    smoothing: 0.5,
    vowelParams: {
      A: { openness: 1.0, form: 0.0 },
      I: { openness: 0.35, form: 1.0 },
      U: { openness: 0.45, form: -1.0 },
      E: { openness: 0.6, form: 0.6 },
      O: { openness: 0.8, form: -0.6 },
    },
  };

  // audio queue
  let audioQueue = [];
  let audioPlaying = false;
  let currentAudioSource = null;
  let currentMeta = null;   // meta of the chunk being played (for ack suppression on flush)

  // callbacks
  let onChunkStart = null, onChunkEnd = null, onQueueEmpty = null, onModelChange = null;
  let areaEl = null, canvasEl = null;
  let fixedView = false;         // init({fixed}): the desktop pet, where a drag moves her window instead (pet.py)

  function safeGet(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }
  function safeSet(k, v) { try { localStorage.setItem(k, v); } catch (_) {} }

  // ── Pixi stage ──
  function ensurePixiApp() {
    if (pixiApp) return pixiApp;
    const w = areaEl.clientWidth || window.innerWidth;
    const h = areaEl.clientHeight || window.innerHeight;
    pixiApp = new PIXI.Application({
      view: canvasEl, autoStart: true, backgroundAlpha: 0,
      width: w, height: h,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true, antialias: true,
      powerPreference: "high-performance",
    });
    pixiApp.ticker.maxFPS = 0;
    pixiApp.ticker.add(agentTick);
    return pixiApp;
  }

  function fillEmptyEmotionBanks(banks) {
    for (const em of ALL_EMOTIONS) {
      if (!banks[em]) banks[em] = { emotes: [], movements: [] };
    }
  }

  // ── model preload + activate (stage swap, no network after first load) ──
  async function loadModelData(opt, onProgress) {
    if (!opt) return null;
    if (modelStates[opt.id]) return modelStates[opt.id];
    const p = (frac, sub) => onProgress && onProgress(frac, sub);
    p(2, "preparing renderer");
    ensurePixiApp();

    const Live2DModel = (PIXI.live2d && PIXI.live2d.Live2DModel) || PIXI.Live2DModel;
    if (!Live2DModel) { console.error("[Live2D] pixi-live2d-display not loaded"); return null; }
    if (PIXI.live2d && PIXI.live2d.config) PIXI.live2d.config.expressionFadingDuration = 500;

    p(8, "fetching motions + emotion banks");
    let mAssets = [], eAssets = [], iBank = [], eBanks = {}, config = {};
    try {
      const [motionsRes, banksRes] = await Promise.all([fetch(opt.motions_url), fetch(opt.banks_url)]);
      const motionsList = motionsRes.ok ? await motionsRes.json() : [];
      mAssets = motionsList.filter((m) => m.type === "motion");
      eAssets = motionsList.filter((m) => m.type === "expression");
      if (banksRes.ok) {
        const data = await banksRes.json();
        config = data.config || {};
        const banks = data.banks || {};
        if (banks.__idle__) { iBank = banks.__idle__.movements || []; delete banks.__idle__; }
        eBanks = banks;
      }
    } catch (e) { console.error("[Live2D] asset/banks load error:", e); }
    fillEmptyEmotionBanks(eBanks);
    if (!iBank.length && mAssets.length) {
      iBank = mAssets.map((m) => ({ name: m.name, likelihood: 100 }));
    }

    p(40, "downloading textures + moc3");
    let model;
    try {
      model = await Live2DModel.from(opt.model3_url, { autoInteract: false });
    } catch (e) { console.error("[Live2D] failed to instantiate", opt.id, e); return null; }
    model.anchor.set(0.5, 0.5);
    const origW = model.width, origH = model.height;

    p(80, "patching lip-sync mouth params");
    patchModelForLipSyncOverride(model, config.mouth_open_param || "ParamMouthOpenY",
                                        config.mouth_form_param || "ParamMouthForm");
    const im = model.internalModel;
    if (im && typeof im.on === "function") {
      im.on("beforeModelUpdate", () => { if (model === live2dModel) applyFrameOverlays(model, opt.id); });
    }
    slowFocus(model);

    p(90, "registering external motions");
    const mm = model.internalModel && model.internalModel.motionManager;
    if (mm) await injectExternalMotions(mm, opt);

    const state = {
      id: opt.id, name: opt.name, model, config,
      motionAssets: mAssets, expressionAssets: eAssets,
      idleMotionBank: iBank, emotionBanks: eBanks,
      originalWidth: origW, originalHeight: origH,
    };
    modelStates[opt.id] = state;
    p(100, `${opt.name} ready`);
    return state;
  }

  function activateModel(opt) {
    const state = opt && modelStates[opt.id];
    if (!state || !state.model) return false;
    stopIdleLoop(); stopMotionLoop();
    if (live2dModel && live2dModel !== state.model) {
      try { pixiApp.stage.removeChild(live2dModel); } catch (_) {}
    }
    live2dModel = state.model;
    motionAssets = state.motionAssets;
    expressionAssets = state.expressionAssets;
    idleMotionBank = state.idleMotionBank;
    emotionBanks = state.emotionBanks;
    mouthOpenParam = state.config.mouth_open_param || "ParamMouthOpenY";
    mouthFormParam = state.config.mouth_form_param || "ParamMouthForm";
    _lastPlayedMotionName = null; _lastIdleMotionName = null;
    currentEmotion = null; activeExpressions = new Set();
    if (!live2dModel.parent) pixiApp.stage.addChild(live2dModel);
    repositionModel(state);
    if (pixiApp.ticker) pixiApp.ticker.start();
    startIdleLoop();
    currentId = opt.id;
    safeSet("openamika-avatar-model", opt.id);
    if (busyOn) setBusy(true);
    if (onModelChange) onModelChange(opt.id);
    return true;
  }

  function repositionModel(state) {
    const s = state || modelStates[currentId];
    if (!live2dModel || !s || !s.originalHeight) return;
    const w = areaEl.clientWidth || window.innerWidth;
    const h = areaEl.clientHeight || window.innerHeight;
    if (w < 1 || h < 1) return;
    const saved = fixedView ? null : safeGet("openamika-avatar-view-" + s.id);
    if (saved) {
      try {
        const v = JSON.parse(saved);
        live2dModel.scale.set(v.s, v.s); live2dModel.x = v.x; live2dModel.y = v.y;
        return;
      } catch (_) {}
    }
    const scale = (h * (s.config.scale || 0.85)) / s.originalHeight;
    live2dModel.scale.set(scale, scale);
    live2dModel.x = w / 2; live2dModel.y = h / 2;
  }

  function persistView() {
    if (!live2dModel || !currentId) return;
    safeSet("openamika-avatar-view-" + currentId,
      JSON.stringify({ s: live2dModel.scale.x, x: live2dModel.x, y: live2dModel.y }));
  }

  function pointInAgent(px, py) {
    const m = agent.model;
    if (!m || !agent.shown) return false;
    try {
      const b = m.getBounds();
      return px >= b.x && px <= b.x + b.width && py >= b.y && py <= b.y + b.height;
    } catch (_) { return false; }
  }

  function pickTarget(clientX, clientY) {
    // the agent avatar sits in front of her: a pointer on it moves / zooms it, anywhere else moves her
    const r = canvasEl.getBoundingClientRect();
    if (pointInAgent(clientX - r.left, clientY - r.top)) return agent.model;
    return live2dModel;
  }

  function persistTarget(t) {
    if (!t) return;
    if (t === agent.model) { agent.homeY = t.y - agent.slide; persistAgentView(); }
    else persistView();
  }

  function setupDragZoom() {
    if (fixedView) { window.addEventListener("resize", notifyResize); return; }
    let dragging = false, target = null, dragStartX = 0, dragStartY = 0, modelStartX = 0, modelStartY = 0;
    let pinchStartDist = 0, pinchStartScale = 1;
    const begin = (x, y) => {
      target = pickTarget(x, y);
      if (!target) return false;
      dragging = true; dragStartX = x; dragStartY = y; modelStartX = target.x; modelStartY = target.y;
      return true;
    };
    const move = (x, y) => {
      if (!dragging || !target) return;
      target.x = modelStartX + (x - dragStartX);
      target.y = modelStartY + (y - dragStartY);
    };
    const end = () => {
      if (!dragging) return;
      dragging = false; areaEl.style.cursor = "";
      persistTarget(target);
    };
    areaEl.addEventListener("mousedown", (e) => { if (begin(e.clientX, e.clientY)) areaEl.style.cursor = "grabbing"; });
    document.addEventListener("mousemove", (e) => move(e.clientX, e.clientY));
    document.addEventListener("mouseup", end);
    areaEl.addEventListener("wheel", (e) => {
      const t = pickTarget(e.clientX, e.clientY);
      if (!t) return;
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.05 : 0.95;
      const ns = Math.max(0.1, Math.min(5, t.scale.x * factor));
      t.scale.set(ns, ns);
      persistTarget(t);
    }, { passive: false });
    areaEl.addEventListener("touchstart", (e) => {
      if (!live2dModel) return;
      if (e.touches.length === 2) {
        if (!target) target = pickTarget(e.touches[0].clientX, e.touches[0].clientY);
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        pinchStartDist = Math.hypot(dx, dy); pinchStartScale = target.scale.x;
        dragging = false; e.preventDefault();
      } else if (e.touches.length === 1) {
        begin(e.touches[0].clientX, e.touches[0].clientY);
      }
    }, { passive: false });
    areaEl.addEventListener("touchmove", (e) => {
      if (!target) return;
      if (e.touches.length === 2 && pinchStartDist > 0) {
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const ns = Math.max(0.1, Math.min(5, pinchStartScale * (Math.hypot(dx, dy) / pinchStartDist)));
        target.scale.set(ns, ns); dragging = false; e.preventDefault();
      } else if (e.touches.length === 1 && dragging) {
        move(e.touches[0].clientX, e.touches[0].clientY);
        e.preventDefault();
      }
    }, { passive: false });
    areaEl.addEventListener("touchend", () => {
      pinchStartDist = 0;
      if (target) persistTarget(target);
      dragging = false;
    });
    window.addEventListener("resize", notifyResize);
  }

  function notifyResize() {
    // Resize the renderer to the stage area and remap the model proportionally —
    // used on window resizes AND fullscreen toggles (which don't fire window resize).
    if (!pixiApp) return;
    const ow = pixiApp.screen.width, oh = pixiApp.screen.height;
    const w = areaEl.clientWidth || window.innerWidth;
    const h = areaEl.clientHeight || window.innerHeight;
    if (w < 1 || h < 1 || (w === ow && h === oh)) return;
    pixiApp.renderer.resize(w, h);
    if (live2dModel && ow > 0 && oh > 0) {
      live2dModel.x = (live2dModel.x / ow) * w;
      live2dModel.y = (live2dModel.y / oh) * h;
      const ns = live2dModel.scale.x * (h / oh);
      live2dModel.scale.set(ns, ns);
      // keep the saved view consistent with the remapped coordinates
      if (!fixedView && safeGet("openamika-avatar-view-" + currentId)) persistView();
    }
    repositionAgent();
  }

  async function injectExternalMotions(motionManager, opt) {
    if (!motionManager || !motionManager.definitions) return;
    const groups = Object.keys(motionManager.definitions);
    if (!groups.length) return;
    const gm = motionManager.definitions[groups[0]];
    if (!Array.isArray(gm)) return;
    try {
      const list = await (await fetch(opt.motions_url)).json();
      const existing = new Set(gm.map((m) => (m && m.File && m.File.split("/").pop()) || (m && m.File)).filter(Boolean));
      let added = 0;
      for (const item of list) {
        if (item.type === "expression") continue;
        const fn = item.file || (item.path && item.path.split("/").pop());
        if (!fn || !fn.endsWith(".motion3.json") || existing.has(fn)) continue;
        gm.push({ File: fn, FadeInTime: 0.5, FadeOutTime: 0.5 });
        existing.add(fn); added++;
      }
      if (added) console.info(`[Live2D] injected ${added} external motion(s)`);
    } catch (e) { console.warn("[Live2D] motion inject error:", e); }
  }

  // ── lip sync ──
  function patchModelForLipSyncOverride(model, openName, formName) {
    if (!model || model._lipSyncPatched) return;
    const internal = model.internalModel;
    const coreModel = internal && (internal.coreModel || internal.model);
    if (coreModel && typeof coreModel.setParameterValueByIndex === "function") {
      const moIdx = (coreModel.getParameterIndex && coreModel.getParameterIndex(openName));
      const mfIdx = (coreModel.getParameterIndex && coreModel.getParameterIndex(formName));
      const originalSet = coreModel.setParameterValueByIndex.bind(coreModel);
      model._lipSyncIndices = { mouthOpenIndex: (moIdx == null ? -1 : moIdx), mouthFormIndex: (mfIdx == null ? -1 : mfIdx) };
      model._lipSyncOriginalSet = originalSet;
      coreModel.setParameterValueByIndex = function (pi, v) {
        const idx = model._lipSyncIndices;
        if (lipSyncEnabled && (pi === idx.mouthOpenIndex || pi === idx.mouthFormIndex)) return;
        return originalSet(pi, v);
      };
    }
    const rk = typeof model._render === "function" ? "_render"
             : typeof model.render === "function" ? "render" : null;
    if (rk) {
      const originalRender = model[rk].bind(model);
      model._lipSyncOriginalRender = originalRender;
      model[rk] = function (renderer) {
        if (lipSyncEnabled && pendingMouthOpen !== undefined && model.internalModel && model === live2dModel) {
          applyLipSyncMouth();
        }
        return originalRender(renderer);
      };
    }
    model._lipSyncPatched = true;
  }

  function applyLipSyncMouth() {
    if (!lipSyncEnabled || !live2dModel || !live2dModel.internalModel || pendingMouthOpen === undefined) return;
    const model = live2dModel.internalModel.coreModel || live2dModel.internalModel.model;
    if (!model) return;
    try {
      const sp = live2dModel._lipSyncOriginalSet || model.setParameterValueByIndex.bind(model);
      const idx = live2dModel._lipSyncIndices || {};
      const mo = idx.mouthOpenIndex != null ? idx.mouthOpenIndex : -1;
      const mf = idx.mouthFormIndex != null ? idx.mouthFormIndex : -1;
      if (mo >= 0) sp(mo, pendingMouthOpen);
      if (mf >= 0) sp(mf, pendingMouthForm);
      const c = model._model || model;
      if (typeof c.update === "function") c.update();
      else if (typeof model.update === "function") model.update();
    } catch (_) {}
  }

  function updateLipSyncFromWS() {
    if (!wsAnalyser || !live2dModel || !live2dModel.internalModel) return;
    try {
      wsAnalyser.getByteFrequencyData(wsAudioDataArray);
      let sum = 0;
      for (let i = 0; i < wsAudioDataArray.length; i++) { const n = wsAudioDataArray[i] / 255; sum += n * n; }
      const rms = Math.sqrt(sum / wsAudioDataArray.length);
      const vd = detectVowelFromFormants(wsAudioDataArray);
      const vm = Math.min(1, rms * 4 * lipSyncCalibration.sensitivity);
      let mo = vd.openness * vm, mf = vd.form * vm;
      if (lastMouthOpen !== undefined) {
        const s = lipSyncCalibration.smoothing;
        mo = lastMouthOpen * s + mo * (1 - s);
        mf = lastMouthForm * s + mf * (1 - s);
      }
      lastMouthOpen = mo; lastMouthForm = mf;
      pendingMouthOpen = mo; pendingMouthForm = mf;
    } catch (_) {}
  }

  function detectVowelFromFormants(arr) {
    let te = 0;
    for (let i = 0; i < arr.length; i++) te += arr[i];
    if (te < 10) return { vowel: "silence", openness: 0, form: 0 };
    const sr = wsAudioContext ? wsAudioContext.sampleRate : 44100, bh = sr / 256;
    const ge = (s, e) => {
      const si = Math.floor(s / bh), ei = Math.ceil(e / bh);
      let v = 0;
      for (let i = si; i < Math.min(ei, arr.length); i++) v += arr[i];
      return v / Math.max(1, ei - si);
    };
    const f1l = ge(200, 400), f1m = ge(400, 650), f1h = ge(650, 900);
    const f2l = ge(700, 1200), f2m = ge(1200, 2000), f2h = ge(2000, 2800);
    const tot = f1l + f1m + f1h + f2l + f2m + f2h;
    if (tot < 10) return { vowel: "silence", openness: 0, form: 0 };
    const n = (v) => v / tot;
    const sc = {
      A: n(f1h) * 2 + n(f2m) * 1.5, I: n(f1l) * 2 + n(f2h) * 2, U: n(f1l) * 1.8 + n(f2l) * 2,
      E: n(f1m) * 1.8 + n(f2m) * 1.5, O: n(f1m) * 1.5 + n(f2l) * 1.8,
    };
    let mv = "A", ms = sc.A;
    for (const [k, v] of Object.entries(sc)) if (v > ms) { ms = v; mv = k; }
    return { vowel: mv, openness: lipSyncCalibration.vowelParams[mv].openness, form: lipSyncCalibration.vowelParams[mv].form };
  }

  // ── expression & motion ──
  function clearExpressionTracking() {
    const em = live2dModel && live2dModel.internalModel && live2dModel.internalModel.motionManager
      && live2dModel.internalModel.motionManager.expressionManager;
    if (em) {
      if (em._currentExpressionIndex !== undefined) em._currentExpressionIndex = -1;
      if (em.currentExpressionIndex !== undefined) em.currentExpressionIndex = -1;
      try { if (em._currentExpression !== undefined) em._currentExpression = undefined; } catch (_) {}
    }
    activeExpressions.clear();
  }

  function deactivateAllExpressions() {
    if (!live2dModel) return;
    const em = live2dModel.internalModel && live2dModel.internalModel.motionManager
      && live2dModel.internalModel.motionManager.expressionManager;
    if (em) {
      try { em.resetExpression(); } catch (_) {}
      if (em._currentExpressionIndex !== undefined) em._currentExpressionIndex = -1;
      if (em.currentExpressionIndex !== undefined) em.currentExpressionIndex = -1;
      try { if (em._currentExpression !== undefined) em._currentExpression = undefined; } catch (_) {}
    }
    activeExpressions.clear();
  }

  function activateExpressionByName(name) {
    const asset = expressionAssets.find((e) => e.name === name || (e.file && e.file.includes(name)));
    if (!asset) return;
    const fn = asset.file;
    if (activeExpressions.has(fn)) return;
    const internal = live2dModel && live2dModel.internalModel;
    if (!internal) return;
    if (internal.motionManager && internal.motionManager.expressionManager) {
      const defs = internal.motionManager.expressionManager.definitions;
      const idx = defs.findIndex((d) => d.File === fn || d.Name === fn || (d.File && d.File.endsWith(fn)));
      if (idx >= 0) {
        internal.motionManager.expressionManager.setExpression(idx);
        activeExpressions.add(fn);
        return;
      }
    }
    applyExpressionFromPath(asset.path, fn);
  }

  async function applyExpressionFromPath(path, filename) {
    try {
      const exp = await (await fetch(path)).json();
      const cm = live2dModel.internalModel.coreModel || live2dModel.internalModel.model;
      if (!cm) return;
      for (const p of (exp.Parameters || [])) {
        const idx = (cm.getParameterIndex && cm.getParameterIndex(p.Id));
        if (idx == null || idx < 0) continue;
        const s = live2dModel._lipSyncOriginalSet || cm.setParameterValueByIndex.bind(cm);
        if ((p.Blend || "Add").toLowerCase() === "add") {
          s(idx, ((cm.getParameterValueByIndex && cm.getParameterValueByIndex(idx)) || 0) + (p.Value || 0));
        } else s(idx, p.Value || 0);
      }
      activeExpressions.add(filename);
    } catch (e) { console.warn("[Live2D] expression error:", e); }
  }

  function playMotionByName(name) {
    if (!live2dModel) return false;
    const mm = live2dModel.internalModel && live2dModel.internalModel.motionManager;
    if (!mm) return false;
    const groups = Object.keys(mm.definitions || {});
    if (!groups.length) return false;
    const g = groups[0], defs = mm.definitions[g];
    const idx = defs.findIndex((d) => {
      const f = d.File || "";
      return f === name || f.includes(name) || f.endsWith(name + ".motion3.json");
    });
    if (idx >= 0) { live2dModel.motion(g, idx, 3); _lastPlayedMotionName = name; return true; }
    return false;
  }

  function isMotionPlaying() {
    const mm = live2dModel && live2dModel.internalModel && live2dModel.internalModel.motionManager;
    return mm ? !mm.isFinished() : false;
  }

  function handleEmotionChange(emotion) {
    if (!ALL_EMOTIONS.includes(emotion)) return;
    stopIdleLoop();
    currentEmotion = emotion;
    const bank = emotionBanks[emotion] || { emotes: [], movements: [] };
    clearExpressionTracking();
    let ea = false;
    for (const e of bank.emotes) if (Math.random() * 100 < e.likelihood) { activateExpressionByName(e.name); ea = true; }
    if (!ea) deactivateAllExpressions();
    _lastPlayedMotionName = null;
    const cands = [];
    for (const m of bank.movements) if (Math.random() * 100 < m.likelihood) cands.push(m);
    if (cands.length) playMotionByName(cands[Math.floor(Math.random() * cands.length)].name);
    startMotionLoop(emotion);
  }

  function pickAndPlayNextMotion(em) {
    const movs = (emotionBanks[em] || { movements: [] }).movements || [];
    if (!movs.length) return;
    const c = [];
    for (const m of movs) {
      if (m.name === _lastPlayedMotionName && movs.length > 1) continue;
      if (Math.random() * 100 < m.likelihood) c.push(m);
    }
    if (!c.length) {
      const fb = movs.filter((m) => m.name !== _lastPlayedMotionName || movs.length === 1);
      if (fb.length) c.push(fb[Math.floor(Math.random() * fb.length)]);
    }
    if (c.length) playMotionByName(c[Math.floor(Math.random() * c.length)].name);
  }

  function startMotionLoop(em) {
    stopMotionLoop(); stopIdleLoop();
    _emotionAudioPlaying = true;
    _emotionMotionLoopInterval = setInterval(() => {
      if (!_emotionAudioPlaying) { stopMotionLoop(); startIdleLoop(); return; }
      if (currentEmotion !== em) { stopMotionLoop(); return; }
      if (!isMotionPlaying()) pickAndPlayNextMotion(em);
    }, 200);
  }
  function stopMotionLoop() {
    _emotionAudioPlaying = false;
    if (_emotionMotionLoopInterval) { clearInterval(_emotionMotionLoopInterval); _emotionMotionLoopInterval = null; }
  }
  function startIdleLoop() {
    stopIdleLoop();
    if (!idleMotionBank.length) return;
    pickAndPlayNextIdleMotion();
    _idleMotionLoopInterval = setInterval(() => {
      if (_emotionAudioPlaying) return;
      if (!isMotionPlaying()) pickAndPlayNextIdleMotion();
    }, 300);
  }
  function stopIdleLoop() {
    if (_idleMotionLoopInterval) { clearInterval(_idleMotionLoopInterval); _idleMotionLoopInterval = null; }
  }
  function pickAndPlayNextIdleMotion() {
    const movs = idleMotionBank;
    if (!movs.length) return;
    const c = [];
    for (const m of movs) {
      if (m.name === _lastIdleMotionName && movs.length > 1) continue;
      if (Math.random() * 100 < m.likelihood) c.push(m);
    }
    if (!c.length) {
      const fb = movs.filter((m) => m.name !== _lastIdleMotionName || movs.length === 1);
      if (fb.length) c.push(fb[Math.floor(Math.random() * fb.length)]);
    }
    if (c.length) {
      const p = c[Math.floor(Math.random() * c.length)];
      _lastIdleMotionName = p.name;
      playMotionByName(p.name);
    }
  }

  // ── audio playback (THE sink: emotion fires at playback start of its sentence) ──
  function initWsAudioContext() {
    if (wsAudioContext) return;
    wsAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    wsAnalyser = wsAudioContext.createAnalyser();
    wsAnalyser.fftSize = 256; wsAnalyser.smoothingTimeConstant = 0.8;
    wsAudioDataArray = new Uint8Array(wsAnalyser.frequencyBinCount);
    outputVolumeAnalyser = wsAudioContext.createAnalyser();
    outputVolumeAnalyser.fftSize = 256; outputVolumeAnalyser.smoothingTimeConstant = 0.8;
    outputVolumeData = new Uint8Array(outputVolumeAnalyser.frequencyBinCount);
    wsGainNode = wsAudioContext.createGain();
    wsGainNode.gain.value = parseFloat(safeGet("openamika-outputGain") || "1");
    wsGainNode.connect(wsAnalyser);
    wsGainNode.connect(outputVolumeAnalyser);
    wsGainNode.connect(wsAudioContext.destination);
    if (!_wsLipSyncBound) _wsLipSyncBound = () => updateLipSyncFromWS();
    if (pixiApp && pixiApp.ticker) {
      const L = (PIXI.UPDATE_PRIORITY && PIXI.UPDATE_PRIORITY.LOW) != null ? PIXI.UPDATE_PRIORITY.LOW : -100;
      pixiApp.ticker.add(_wsLipSyncBound, null, L);
      lipSyncEnabled = true;
    }
  }

  // ── portrait: her face, copied from the stage into another canvas every frame (the first-run wizard's
  // circle). The copy runs in the ticker right after Pixi's render (UTILITY priority), while the WebGL
  // buffer still holds the frame. The crop is a square around the head, from the model's own geometry
  // (anchor 0.5 at x/y, height = originalHeight × scale), so it follows drag and zoom.
  let portrait = null;
  function detachPortrait() {
    if (portrait && pixiApp && pixiApp.ticker) { try { pixiApp.ticker.remove(portrait.tick); } catch (_) {} }
    portrait = null;
  }
  function attachPortrait(canvas, opts) {
    detachPortrait();
    if (!canvas || !pixiApp || !live2dModel || !canvasEl) return false;
    const ctx = canvas.getContext("2d");
    if (!ctx) return false;
    const o = Object.assign({ side: 0.30, center: 0.17 }, opts || {});   // fractions of the model's height
    const tick = () => {
      const s = modelStates[currentId];
      if (!live2dModel || !s || !s.originalHeight) return;
      const res = pixiApp.renderer.resolution || 1;
      const mh = s.originalHeight * Math.abs(live2dModel.scale.y);
      const top = live2dModel.y - mh * (live2dModel.anchor ? live2dModel.anchor.y : 0.5);
      const side = mh * o.side, cx = live2dModel.x, cy = top + mh * o.center;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      try {
        ctx.drawImage(canvasEl, (cx - side / 2) * res, (cy - side / 2) * res, side * res, side * res,
                      0, 0, canvas.width, canvas.height);
      } catch (_) {}
    };
    const P = (PIXI.UPDATE_PRIORITY && PIXI.UPDATE_PRIORITY.UTILITY) != null ? PIXI.UPDATE_PRIORITY.UTILITY : -50;
    pixiApp.ticker.add(tick, null, P);
    portrait = { canvas, tick };
    return true;
  }
  // The browser only lets audio start after a click: resolve true once the context runs (a 300 ms wait so
  // a call made outside a gesture does not hang on resume()).
  async function ensureAudio() {
    initWsAudioContext();
    try {
      if (wsAudioContext.state === "suspended") {
        await Promise.race([wsAudioContext.resume(), new Promise((r) => setTimeout(r, 300))]);
      }
    } catch (_) {}
    return wsAudioContext.state === "running";
  }

  function playChunk(b64, emotionKey, pauseAfterSec, meta) {
    if (!b64) return;
    audioQueue.push({ audio: b64, emotion: emotionKey || null, pause: pauseAfterSec || 0, meta: meta || null });
    if (!audioPlaying) playNextChunk();
  }

  function playBuffer(arrayBuffer, emotionKey, pauseAfterSec, meta) {
    if (!arrayBuffer || !arrayBuffer.byteLength) return;
    audioQueue.push({ buf: arrayBuffer.slice(0), emotion: emotionKey || null, pause: pauseAfterSec || 0, meta: meta || null });
    if (!audioPlaying) playNextChunk();
  }

  // One playback chain at a time. Only a chunk's own onended (also fired by flush()'s stop()) or its
  // trailing-pause timer may start the next chunk, and only while they still belong to the current
  // chain: flush() retires the chain (playEpoch++) and clears the timer. Before this, a flush during a
  // chunk's trailing pause — a proactive turn firing the instant her last sentence ended — left the old
  // pause timer alive; it started a second chunk beside the new turn's first one, and from then on two
  // chains ran in parallel: she spoke two different sentences at the same time (2026-10-24).
  let playEpoch = 0, pauseTimer = null, chunkStarting = false;

  function flush() {
    // Barge-in semantics (ported from the original console's stopAllTTS): stop every
    // queued/playing source AND suppress the killed chunk's tts_playing/tts_finished
    // acks — a mis-reported "finished" would corrupt the server's interruption anchor
    // (what she believes she managed to say before being cut off).
    audioQueue = [];
    playEpoch++;
    if (pauseTimer) { clearTimeout(pauseTimer); pauseTimer = null; }
    if (currentMeta) currentMeta.ack = false;
    currentMeta = null;
    if (currentAudioSource) { try { currentAudioSource.stop(); } catch (_) {} }
    currentAudioSource = null;
    audioPlaying = false;
    chunkStarting = false;
    _emotionAudioPlaying = false;
    deactivateAllExpressions();
    startIdleLoop();
  }

  async function playNextChunk() {
    if (chunkStarting || currentAudioSource) return;   // a chunk is decoding or playing: its own onended continues the chain
    if (!audioQueue.length) {
      audioPlaying = false;
      _emotionAudioPlaying = false;
      setTimeout(() => { if (!_emotionAudioPlaying) startIdleLoop(); }, 400);
      if (onQueueEmpty) onQueueEmpty();
      return;
    }
    audioPlaying = true;
    chunkStarting = true;
    const epoch = playEpoch;
    const item = audioQueue.shift();
    const flushedMeanwhile = () => {
      // flush() ran while this chunk was resuming/decoding: drop it and let the new turn's queue go on
      chunkStarting = false;
      if (audioQueue.length && !currentAudioSource) playNextChunk();
      return true;
    };
    try {
      initWsAudioContext();
      if (wsAudioContext.state === "suspended") await wsAudioContext.resume();
      if (epoch !== playEpoch) return void flushedMeanwhile();
      if (item.emotion) handleEmotionChange(item.emotion);   // ← sync point: face turns as the voice starts
      if (onChunkStart) onChunkStart(item.meta, item.emotion);
      let rawBuffer;
      if (item.buf) {
        rawBuffer = item.buf;
      } else {
        const bin = atob(item.audio), bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        rawBuffer = bytes.buffer;
      }
      const ab = await wsAudioContext.decodeAudioData(rawBuffer.slice(0));
      if (epoch !== playEpoch) return void flushedMeanwhile();
      const src = wsAudioContext.createBufferSource();
      src.buffer = ab;
      src.connect(wsGainNode);
      currentAudioSource = src;
      currentMeta = item.meta;
      _emotionAudioPlaying = true;
      src.onended = () => {
        if (currentAudioSource === src) currentAudioSource = null;
        if (currentMeta === item.meta) currentMeta = null;
        if (onChunkEnd) { try { onChunkEnd(item.meta); } catch (_) {} }
        if (epoch !== playEpoch) return;                   // stopped by flush(): the new chain drives itself
        const pause = Math.max(0, item.pause || 0);
        if (pause > 0) {
          pauseTimer = setTimeout(() => { pauseTimer = null; if (epoch === playEpoch) playNextChunk(); }, pause * 1000);
        } else {
          playNextChunk();
        }
      };
      src.start(0);
      chunkStarting = false;
    } catch (e) {
      console.error("[Audio] chunk error:", e);
      chunkStarting = false;
      if (epoch === playEpoch) playNextChunk();
    }
  }

  function surfaceEmotion(key) {
    // early face reaction (e.g. the surface tier's tone) — only while nothing is speaking
    if (key && !_emotionAudioPlaying) handleEmotionChange(key);
  }

  function outputLevel() {
    if (!outputVolumeAnalyser || !outputVolumeData) return 0;
    outputVolumeAnalyser.getByteFrequencyData(outputVolumeData);
    let sum = 0;
    for (let i = 0; i < outputVolumeData.length; i++) { const n = outputVolumeData[i] / 255; sum += n * n; }
    return Math.min(100, Math.round(Math.sqrt(sum / outputVolumeData.length) * 300));
  }

  // ── per-frame parameter overlays ──
  // Her "Loading" emote (Param33 加载中) must sit on top of whatever face she is making and must
  // survive her motions, which write that parameter too (every idle motion holds it at 0). An
  // expression set through the ExpressionManager would replace the emote, and a value written before
  // the frame's update is overwritten by the motion — so overlays are written in `beforeModelUpdate`:
  // after motions, expressions and physics, right before the core computes the frame.
  // `loadParameters()` restores the post-motion values afterwards, so an additive overlay never
  // accumulates across frames and switching it off needs no cleanup.
  const overlays = new Map();        // lower-case expression name -> {on, byModel: {modelId: [{idx, value, blend}] | null}}
  const expressionDefs = new Map();  // path -> [{id, value, blend}]
  let busyOn = false, busyName = null, busyMotion = null;

  function findExpressionAsset(name, assets) {
    const lower = String(name || "").toLowerCase();
    return (assets || []).find((e) => String(e.name || "").toLowerCase() === lower
      || String(e.file || "").toLowerCase() === lower + ".exp3.json") || null;
  }

  async function loadExpressionDefs(asset) {
    if (expressionDefs.has(asset.path)) return expressionDefs.get(asset.path);
    const doc = await (await fetch(asset.path)).json();
    const defs = (doc.Parameters || []).filter((p) => p && p.Id)
      .map((p) => ({ id: p.Id, value: Number(p.Value) || 0, blend: String(p.Blend || "Add").toLowerCase() }));
    expressionDefs.set(asset.path, defs);
    return defs;
  }

  function overlayParams(entry, name, modelId) {
    if (entry.byModel[modelId] !== undefined) return entry.byModel[modelId];
    entry.byModel[modelId] = null;                       // claimed; filled in once the file is read
    const state = modelStates[modelId];
    const asset = state && findExpressionAsset(name, state.expressionAssets);
    if (!asset) { console.info(`[Live2D] ${modelId} has no "${name}" expression to overlay`); return null; }
    loadExpressionDefs(asset).then((defs) => {
      const im = state.model.internalModel, cm = im && (im.coreModel || im.model);
      if (!cm || !cm.getParameterIndex) return;
      const list = [];
      for (const d of defs) {
        const idx = cm.getParameterIndex(d.id);
        if (idx != null && idx >= 0) list.push({ idx, value: d.value, blend: d.blend });
      }
      entry.byModel[modelId] = list;
    }).catch((e) => console.warn("[Live2D] overlay", name, e));
    return null;
  }

  function applyFrameOverlays(model, modelId) {
    if (!overlays.size && !overlayMotions.size) return;
    const im = model.internalModel, cm = im && (im.coreModel || im.model);
    if (!cm || !cm.getParameterValueByIndex) return;
    const set = model._lipSyncOriginalSet || cm.setParameterValueByIndex.bind(cm);
    for (const [name, entry] of overlays) {
      if (!entry.on) continue;
      const list = overlayParams(entry, name, modelId);
      if (!list) continue;
      for (const p of list) {
        const cur = cm.getParameterValueByIndex(p.idx) || 0;
        set(p.idx, p.blend === "multiply" ? cur * p.value : p.blend === "overwrite" ? p.value : cur + p.value);
      }
    }
    if (overlayMotions.size) applyOverlayMotions(modelId, set, performance.now());
  }

  // ── motion overlays: a looping motion3 track evaluated on top of everything else ──
  // Her loading icon's spin is its own little animation (Scene1.motion3.json sweeps Param32 / Param40
  // over two seconds). Played through the motion manager it would replace her idle motion, so the
  // track is sampled here and written every frame while it is on.
  const overlayMotions = new Map();   // lower-case motion name -> {on, start, byModel: {modelId: {duration, fps, tracks} | null}}
  const motionDefs = new Map();       // path -> parsed motion3 json

  function sampleCurve(segments, duration, fps) {
    // motion3 segments: [t0, v0, type, points…] with type 0 linear (t, v), 1 bezier (t1, v1, t2, v2, t3, v3),
    // 2 stepped (t, v), 3 inverse-stepped (t, v). Sampled at `fps` over `duration` (restricted beziers:
    // the parameter runs linearly in time, as Cubism's own evaluator assumes).
    const pieces = [];
    let i = 2, t0 = segments[0], v0 = segments[1];
    while (i < segments.length) {
      const type = segments[i], count = type === 1 ? 3 : 1, pts = [];
      for (let k = 0; k < count; k++) pts.push([segments[i + 1 + 2 * k], segments[i + 2 + 2 * k]]);
      pieces.push({ t0, v0, type, pts, t1: pts[count - 1][0] });
      t0 = pts[count - 1][0]; v0 = pts[count - 1][1];
      i += 1 + 2 * count;
    }
    const n = Math.max(2, Math.ceil(duration * fps) + 1), out = new Float32Array(n);
    const last = pieces.length ? pieces[pieces.length - 1].pts[pieces[pieces.length - 1].pts.length - 1][1] : segments[1];
    for (let s = 0; s < n; s++) {
      const t = Math.min(duration, s / fps);
      let v = last;
      if (t <= segments[0]) { out[s] = segments[1]; continue; }
      for (const p of pieces) {
        if (t > p.t1) continue;
        const u = p.t1 > p.t0 ? (t - p.t0) / (p.t1 - p.t0) : 1;
        if (p.type === 0) v = p.v0 + (p.pts[0][1] - p.v0) * u;
        else if (p.type === 1) {
          const [p1, p2, p3] = p.pts;
          const a = p.v0 + (p1[1] - p.v0) * u, b = p1[1] + (p2[1] - p1[1]) * u, c = p2[1] + (p3[1] - p2[1]) * u;
          const d = a + (b - a) * u, e = b + (c - b) * u;
          v = d + (e - d) * u;
        } else if (p.type === 2) v = p.v0;
        else v = p.pts[0][1];
        break;
      }
      out[s] = v;
    }
    return out;
  }

  function findMotionAsset(name, assets) {
    const lower = String(name || "").toLowerCase();
    return (assets || []).find((m) => String(m.name || "").toLowerCase() === lower
      || String(m.file || "").toLowerCase() === lower + ".motion3.json") || null;
  }

  function motionTrack(entry, name, modelId) {
    if (entry.byModel[modelId] !== undefined) return entry.byModel[modelId];
    entry.byModel[modelId] = null;
    const state = modelStates[modelId];
    const asset = state && findMotionAsset(name, state.motionAssets);
    if (!asset) { console.info(`[Live2D] ${modelId} has no "${name}" motion to overlay`); return null; }
    const load = motionDefs.has(asset.path) ? Promise.resolve(motionDefs.get(asset.path))
      : fetch(asset.path).then((r) => r.json()).then((doc) => { motionDefs.set(asset.path, doc); return doc; });
    load.then((doc) => {
      const im = state.model.internalModel, cm = im && (im.coreModel || im.model);
      if (!cm || !cm.getParameterIndex) return;
      const meta = doc.Meta || {}, duration = Number(meta.Duration) || 1, fps = Number(meta.Fps) || 30;
      const tracks = [];
      for (const c of doc.Curves || []) {
        if (!c || c.Target !== "Parameter" || !c.Id || !Array.isArray(c.Segments)) continue;
        const idx = cm.getParameterIndex(c.Id);
        if (idx == null || idx < 0 || idx >= cm.getParameterCount()) continue;    // not a parameter of this model
        tracks.push({ idx, values: sampleCurve(c.Segments, duration, fps) });
      }
      entry.byModel[modelId] = { duration, fps, tracks };
    }).catch((e) => console.warn("[Live2D] motion overlay", name, e));
    return null;
  }

  function applyOverlayMotions(modelId, set, now) {
    for (const [name, entry] of overlayMotions) {
      if (!entry.on) continue;
      const track = motionTrack(entry, name, modelId);
      if (!track) continue;
      const t = ((now - entry.start) / 1000) % track.duration;
      for (const tr of track.tracks) {
        const pos = t * track.fps, i0 = Math.min(tr.values.length - 1, Math.floor(pos));
        const i1 = Math.min(tr.values.length - 1, i0 + 1), f = pos - i0;
        set(tr.idx, tr.values[i0] + (tr.values[i1] - tr.values[i0]) * f);
      }
    }
  }

  function setOverlayMotion(name, on) {
    const key = String(name || "").toLowerCase();
    if (!key) return false;
    let entry = overlayMotions.get(key);
    if (!entry) { entry = { on: false, start: 0, byModel: {} }; overlayMotions.set(key, entry); }
    if (on && !entry.on) entry.start = performance.now();
    entry.on = !!on;
    return true;
  }

  function setOverlay(name, on) {
    const key = String(name || "").toLowerCase();
    if (!key) return false;
    let entry = overlays.get(key);
    if (!entry) { entry = { on: false, byModel: {} }; overlays.set(key, entry); }
    entry.on = !!on;
    return true;
  }

  function busyExpressionName() {
    const state = currentId && modelStates[currentId];
    return (state && state.config && state.config.busy_expression) || "Loading";
  }
  function busyMotionName() {
    // the loop that animates the icon (banks.json config "busy_motion"); nothing by default
    const state = currentId && modelStates[currentId];
    return (state && state.config && state.config.busy_motion) || null;
  }

  function setBusy(on) {
    // the animated "loading" emote: on while she waits on the deep layer or on a helper (Hermes…)
    const name = busyExpressionName(), motion = busyMotionName();
    if (busyName && busyName !== name) setOverlay(busyName, false);
    if (busyMotion && busyMotion !== motion) setOverlayMotion(busyMotion, false);
    busyName = name; busyMotion = motion; busyOn = !!on;
    setOverlay(name, busyOn);
    if (motion) setOverlayMotion(motion, busyOn);
  }

  // ── the agent avatar ──
  // The paper-doll "host" model (registry role "agent") stands in for her helpers: Hermes, nanoMuse.
  // It shares the stage, bottom-right by default, and plays motions retargeted from her recordings
  // (avatar/retarget_motions.py): idle* / talk* / listen* / think* / happy* / worried* / surprise*.
  const AGENT_STATES = {
    idle: ["idle"], working: ["think", "idle"], talk: ["talk", "happy"], listen: ["listen", "idle"],
    happy: ["happy", "talk"], worried: ["worried", "listen"], surprise: ["surprise", "listen"],
  };
  const AGENT_NO_IDLE_GROUP = "__agent_state_loop__";   // no such group: the library never auto-plays on the doll
  const agent = { opt: null, model: null, baseW: 0, baseH: 0, motions: [], loading: null,
                  visible: false, shown: false, slide: 60, alpha: 0, homeY: 0,
                  base: "idle", state: "idle", stateUntil: 0, loop: null, lastMotion: null };

  function loadAgent() {
    if (agent.model) return Promise.resolve(true);
    if (agent.loading) return agent.loading;
    const opt = registry.find((m) => m.role === "agent");
    if (!opt) return Promise.resolve(false);
    agent.loading = (async () => {
      if (!areaEl || !canvasEl) { agent.loading = null; return false; }   // before init(): init() loads it
      ensurePixiApp();
      const Live2DModel = (PIXI.live2d && PIXI.live2d.Live2DModel) || PIXI.Live2DModel;
      if (!Live2DModel) return false;
      let model;
      try { model = await Live2DModel.from(opt.model3_url, { autoInteract: false }); }
      catch (e) { console.warn("[Live2D] agent avatar failed to load:", e); return false; }
      model.anchor.set(0.5, 0.5);
      model.zIndex = 10;                               // in front of her: small, at the edge of the stage
      model.visible = false;
      pixiApp.stage.sortableChildren = true;
      agent.opt = opt; agent.model = model;
      agent.baseW = model.width || 1; agent.baseH = model.height || 1;
      try {
        const list = await (await fetch(opt.motions_url)).json();
        agent.motions = list.filter((m) => m.type === "motion").map((m) => m.name);
      } catch (_) { agent.motions = []; }
      const mm = model.internalModel && model.internalModel.motionManager;
      if (mm) await injectExternalMotions(mm, opt);
      // Its state loop alone picks its motions. The gateway puts every loose motion of a model3.json without Motions
      // into one "Idle" group, and the library starts a random motion of its idle group whenever nothing plays (any
      // family: surprise while idle, happy mid-job). Point the library at a group that does not exist.
      if (mm && mm.groups) mm.groups.idle = AGENT_NO_IDLE_GROUP;
      slowFocus(model);
      pixiApp.stage.addChild(model);
      repositionAgent();
      startAgentLoop();
      if (agent.visible) showAgentNow();
      console.info(`[Live2D] agent avatar ${opt.id} ready (${agent.motions.length} motions)`);
      return true;
    })();
    return agent.loading;
  }

  function agentPlacement() {
    const cfg = (agent.opt && agent.opt.stage) || {};
    return { scale: cfg.scale || 0.42, nx: cfg.nx != null ? cfg.nx : 0.84, ny: cfg.ny != null ? cfg.ny : 0.70 };
  }

  function repositionAgent() {
    const m = agent.model;
    if (!m || !agent.baseH) return;
    const w = areaEl.clientWidth || window.innerWidth, h = areaEl.clientHeight || window.innerHeight;
    if (w < 1 || h < 1) return;
    let s = 0, x = 0, y = 0;
    try {
      const saved = agent.opt && safeGet("openamika-agent-view-" + agent.opt.id);
      const v = saved && JSON.parse(saved);
      if (v && v.sh > 0) { s = (h * v.sh) / agent.baseH; x = v.nx * w; y = v.ny * h; }
    } catch (_) {}
    if (!(s > 0)) { const d = agentPlacement(); s = (h * d.scale) / agent.baseH; x = w * d.nx; y = h * d.ny; }
    m.scale.set(s, s); m.x = x; agent.homeY = y; m.y = y + agent.slide;
  }

  function persistAgentView() {
    const m = agent.model;
    if (!m || !agent.opt) return;
    const w = areaEl.clientWidth || 1, h = areaEl.clientHeight || 1;
    safeSet("openamika-agent-view-" + agent.opt.id,
      JSON.stringify({ sh: (m.scale.x * agent.baseH) / h, nx: m.x / w, ny: agent.homeY / h }));
  }

  function setAgentVisible(on) {
    on = !!on;
    if (agent.visible === on) return;
    agent.visible = on;
    if (!agent.model) { if (on) loadAgent(); return; }
    if (on) showAgentNow(); else agent.shown = false;   // the ticker slides it out, then hides it
  }

  function showAgentNow() {
    const m = agent.model;
    if (!m) return;
    agent.shown = true; m.visible = true;
    if (!agentMotionPlaying()) agentPlay(agentPick(agent.state));
  }

  function agentTick() {
    const m = agent.model;
    if (!m || !m.visible) return;
    const target = agent.shown ? 0 : 60, alphaTarget = agent.shown ? 1 : 0;
    if (agent.slide !== target) {
      agent.slide += (target - agent.slide) * 0.14;
      if (Math.abs(agent.slide - target) < 0.4) agent.slide = target;
      m.y = agent.homeY + agent.slide;
    }
    if (agent.alpha !== alphaTarget) {
      agent.alpha += (alphaTarget - agent.alpha) * 0.14;
      if (Math.abs(agent.alpha - alphaTarget) < 0.02) agent.alpha = alphaTarget;
      try {
        const r = m.internalModel && m.internalModel.renderer;
        if (r && typeof r.setModelColor === "function") r.setModelColor(1, 1, 1, agent.alpha);
      } catch (_) {}
    }
    if (!agent.shown && agent.slide === target && agent.alpha === alphaTarget) m.visible = false;
  }

  function agentMotionPlaying() {
    const mm = agent.model && agent.model.internalModel && agent.model.internalModel.motionManager;
    return mm ? !mm.isFinished() : false;
  }

  function agentPick(state) {
    const prefixes = AGENT_STATES[state] || AGENT_STATES.idle;
    for (const p of prefixes) {
      const c = agent.motions.filter((n) => n.toLowerCase().startsWith(p) && (n !== agent.lastMotion || agent.motions.length === 1));
      if (c.length) return c[Math.floor(Math.random() * c.length)];
    }
    return agent.motions.length ? agent.motions[Math.floor(Math.random() * agent.motions.length)] : null;
  }

  function agentPlay(name) {
    const m = agent.model, mm = m && m.internalModel && m.internalModel.motionManager;
    if (!mm || !name) return false;
    const groups = Object.keys(mm.definitions || {});
    if (!groups.length) return false;
    const g = groups[0], defs = mm.definitions[g] || [];
    const idx = defs.findIndex((d) => {
      const f = d.File || "";
      return f === name + ".motion3.json" || f.endsWith("/" + name + ".motion3.json");
    });
    if (idx < 0) return false;
    m.motion(g, idx, 3);
    agent.lastMotion = name;
    return true;
  }

  function startAgentLoop() {
    if (agent.loop) return;
    agent.loop = setInterval(() => {
      if (!agent.model || !agent.shown) return;
      if (agent.state !== agent.base && agent.stateUntil && Date.now() > agent.stateUntil) {
        agent.state = agent.base; agent.stateUntil = 0;
      }
      if (!agentMotionPlaying()) agentPlay(agentPick(agent.state));
    }, 250);
  }

  function setAgentBase(state) {           // what it does when nobody has the word: "idle" or "working"
    agent.base = AGENT_STATES[state] ? state : "idle";
    if (!agent.stateUntil) agent.state = agent.base;
  }

  function setAgentState(state, ms) {      // a passing mood; back to the base state after ms
    if (!AGENT_STATES[state]) return;
    agent.state = state; agent.stateUntil = Date.now() + (ms || 3000);
    if (agent.model && agent.shown) agentPlay(agentPick(state));
  }

  // ── glances: she and the agent avatar turn to each other while one of them has the word ──
  function focusController(model) { const im = model && model.internalModel; return im && im.focusController; }

  function slowFocus(model) {
    // relaxed gaze easing: the focus controller advances at half speed, so glances glide instead of snapping
    const fc = focusController(model);
    if (!fc || fc._slowed || typeof fc.update !== "function") return;
    const orig = fc.update.bind(fc);
    fc.update = (dt) => orig(dt * 0.5);
    fc._slowed = true;
  }

  function herHeadFrac() {
    const s = currentId && modelStates[currentId];
    return (s && s.config && Number(s.config.head_y)) || 0.34;
  }
  function agentHeadFrac() { return (agent.opt && agent.opt.stage && Number(agent.opt.stage.head_y)) || 0.26; }
  function headPoint(model, frac) { return { x: model.x, y: model.y - (model.height || 0) * frac }; }

  function lookToward(model, pt, strength) {
    const fc = focusController(model);
    if (!fc) return;
    const w = areaEl.clientWidth || 2, h = areaEl.clientHeight || 2;
    const clamp = (v) => Math.max(-1, Math.min(1, v));
    try {
      fc.focus(clamp((pt.x - model.x) / (w * 0.5)) * strength, clamp(-(pt.y - model.y) / (h * 0.5)) * strength, false);
    } catch (_) {}
  }
  function lookRelease(model) { const fc = focusController(model); if (fc) { try { fc.focus(0, 0, false); } catch (_) {} } }

  let converseTimer = null;
  function converse(speaker, ms, mood) {
    if (!live2dModel || !agent.model || !agent.shown) return false;
    lookToward(live2dModel, headPoint(agent.model, agentHeadFrac()), 0.85);
    lookToward(agent.model, headPoint(live2dModel, herHeadFrac()), 1);
    setAgentState(mood || (speaker === "agent" ? "talk" : "listen"), ms);
    clearTimeout(converseTimer);
    converseTimer = setTimeout(() => {
      if (live2dModel) lookRelease(live2dModel);
      if (agent.model) lookRelease(agent.model);
    }, (ms || 3000) + 1500);
    return true;
  }

  function anchors() {
    // head positions in stage pixels (for the page's speech bubbles); null when that avatar is not on stage
    const out = { her: null, agent: null };
    if (live2dModel) {
      out.her = { x: live2dModel.x, y: live2dModel.y - live2dModel.height * herHeadFrac(),
                  w: live2dModel.width, h: live2dModel.height };
    }
    if (agent.model && agent.shown) {
      out.agent = { x: agent.model.x, y: agent.homeY - agent.model.height * agentHeadFrac(),
                    w: agent.model.width, h: agent.model.height };
    }
    return out;
  }

  // ── public API ──
  const OpenAmikaAvatar = {
    get models() { return registry.filter((m) => m.role !== "agent"); },   // the ones she can wear
    get agentLoaded() { return !!agent.model; },
    get internals() { return { model: live2dModel, agent: agent.model, overlays, overlayMotions }; },   // console / test inspection
    get currentId() { return currentId; },
    get hasModel() { return !!live2dModel; },

    async init(opts) {
      canvasEl = opts.canvas; areaEl = opts.area;
      onChunkStart = opts.onChunkStart || null;
      onChunkEnd = opts.onChunkEnd || null;
      onQueueEmpty = opts.onQueueEmpty || null;
      onModelChange = opts.onModelChange || null;
      fixedView = !!opts.fixed;
      setupDragZoom();
      let payload;
      try {
        payload = await (await fetch("/api/avatar/models")).json();
      } catch (e) {
        console.warn("[Live2D] registry fetch failed:", e);
        return { ok: false, reason: "registry" };
      }
      registry = payload.models || [];
      ALL_EMOTIONS = payload.emotions || [];
      const characters = registry.filter((m) => m.role !== "agent");
      if (!characters.length) return { ok: false, reason: "no-models" };
      const savedId = safeGet("openamika-avatar-model");
      const pick = characters.find((m) => m.id === (opts.modelId || savedId)) || characters[0];
      const state = await loadModelData(pick, opts.onProgress);
      if (!state) return { ok: false, reason: "load-failed", model: pick.id };
      activateModel(pick);
      if (agent.visible) loadAgent();          // the page asked for the agent avatar before her model was up
      return { ok: true, model: pick.id };
    },

    async switchModel(id) {
      const opt = registry.find((m) => m.id === id);
      if (!opt) return false;
      const state = await loadModelData(opt);
      if (!state) return false;
      return activateModel(opt);
    },

    async reloadBanks() {
      // re-fetch banks for the current model (after Setup-page edits)
      const opt = registry.find((m) => m.id === currentId);
      const state = currentId && modelStates[currentId];
      if (!opt || !state) return false;
      try {
        const data = await (await fetch(opt.banks_url)).json();
        state.config = data.config || {};
        const banks = data.banks || {};
        let iBank = [];
        if (banks.__idle__) { iBank = banks.__idle__.movements || []; delete banks.__idle__; }
        fillEmptyEmotionBanks(banks);
        if (!iBank.length && state.motionAssets.length) {
          iBank = state.motionAssets.map((m) => ({ name: m.name, likelihood: 100 }));
        }
        state.emotionBanks = banks; state.idleMotionBank = iBank;
        emotionBanks = banks; idleMotionBank = iBank;
        return true;
      } catch (_) { return false; }
    },

    playChunk, playBuffer, flush, surfaceEmotion, outputLevel, notifyResize,
    attachPortrait, detachPortrait, ensureAudio,
    setBusy, setOverlay, setOverlayMotion, loadAgent, setAgentVisible, setAgentBase, setAgentState, converse, anchors,
    previewEmotion(key) { handleEmotionChange(key); },
    setVolume(v) {
      const g = Math.max(0, Math.min(2, Number(v) || 0));
      safeSet("openamika-outputGain", String(g));
      if (wsGainNode) wsGainNode.gain.value = g;
    },
    setLipSyncGain(v) {
      const g = Math.max(0.1, Math.min(5, Number(v) || 1.5));
      lipSyncCalibration.sensitivity = g;
      safeSet("openamika-lipSyncGain", String(g));
    },
    resetView() {
      if (currentId) {
        try { localStorage.removeItem("openamika-avatar-view-" + currentId); } catch (_) {}
        repositionModel();
      }
      if (agent.opt) {
        try { localStorage.removeItem("openamika-agent-view-" + agent.opt.id); } catch (_) {}
        repositionAgent();
      }
    },
  };

  window.OpenAmikaAvatar = OpenAmikaAvatar;
})();
