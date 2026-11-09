"""What a person sees of OpenRouter: the balance next to a saved key (and "no credits"), a chosen model that left the
catalog, and the provider's own first line when a reply fails. Offline: fake HTTP objects only."""
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "brain"))

import f_openrouter as fo  # noqa: E402
from f_openrouter import (OpenRouterClient, OpenRouterError, account_balance, describe_error, fetch_model_ids,  # noqa: E402
                          load_catalog, provider_detail, role_config)


class Reply:
    def __init__(self, status=200, data=None, events=(), text=""):
        self.status_code, self.data, self.events, self.text = status, data, list(events), text
        self.encoding = None

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"{self.status_code} Client Error: for url: {fo.CHAT_URL}")   # like requests' HTTPError

    def json(self):
        if self.data is None:
            raise ValueError("not json")
        return self.data

    def iter_lines(self, decode_unicode=True):
        for event in self.events:
            yield "data: " + (event if isinstance(event, str) else json.dumps(event))
            yield ""

    def close(self):
        pass


class HTTP:
    def __init__(self, post=None, gets=None):
        self.post_reply, self.gets, self.calls = post, gets or {}, []

    def post(self, url, **kwargs):
        return self.post_reply

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs.get("headers", {}).get("Authorization")))
        reply = self.gets.get(url)
        if isinstance(reply, Exception):
            raise reply
        return reply


def client(http):
    receipts = []
    return OpenRouterClient(http, "sk-or-v1-test", lambda request: "h1", lambda handle, receipt: receipts.append(receipt))


CONFIG = role_config(load_catalog(ROOT / "config" / "openrouter_models.json"), "deepseek/deepseek-v4-flash-0731", "surface")
MESSAGES = [{"role": "system", "content": "persona"}, {"role": "user", "content": "hi"}]


# ---- the provider's first line -------------------------------------------------------------------------------------
def test_no_credits_says_openrouter_is_prepaid():
    line = provider_detail("OpenRouter", 402, {"message": "Insufficient credits. Add more using https://openrouter.ai/settings/credits\nmore",
                                               "code": 402})
    assert line.startswith("OpenRouter (HTTP 402): Insufficient credits.") and "\n" not in line
    assert "prepaid" in line and "openrouter.ai/settings/credits" in line


def test_a_model_gone_from_openrouter_points_at_the_preset():
    line = provider_detail("OpenRouter", 404, {"message": "No endpoints found for qwen/qwen3-235b-a22b."})
    assert "Switch back to the OpenRouter preset" in line
    assert "paste a new one" in provider_detail("OpenRouter", 401, {"message": "User not found."})


def test_a_refused_request_carries_the_providers_words_and_keeps_its_type():
    http = HTTP(post=Reply(402, {"error": {"message": "Insufficient credits. Add more using https://openrouter.ai/settings/credits", "code": 402}}))
    with pytest.raises(RuntimeError) as caught:
        list(client(http).stream(CONFIG, MESSAGES))
    assert str(caught.value).startswith("402 Client Error")           # what memory jobs classify by, unchanged
    detail = describe_error(caught.value)
    assert detail.startswith("OpenRouter (HTTP 402): Insufficient credits") and "prepaid" in detail


def test_an_error_event_keeps_its_message_for_the_memory_retry_rules():
    http = HTTP(post=Reply(200, events=[{"error": {"message": "Provider overloaded\nretry later", "code": 429}}]))
    with pytest.raises(OpenRouterError) as caught:
        list(client(http).stream(CONFIG, MESSAGES))
    assert str(caught.value) == "OpenRouter returned an error event"
    assert describe_error(caught.value) == "OpenRouter (HTTP 429): Provider overloaded — too many requests right now: wait a moment"
    import f_memory
    assert f_memory.transient_failure("OpenRouterError: OpenRouter returned an error event", "extracting")


def test_an_error_without_a_provider_answer_has_no_detail():
    assert describe_error(ValueError("boom")) is None
    try:
        try:
            raise OpenRouterError("x").with_traceback(None)
        except OpenRouterError as inner:
            inner.provider_detail = "OpenRouter (HTTP 402): no money"
            raise RuntimeError("wrapped") from inner
    except RuntimeError as outer:
        assert describe_error(outer) == "OpenRouter (HTTP 402): no money"


# ---- the balance next to a saved key ------------------------------------------------------------------------------
def test_the_balance_comes_from_the_accounts_credits():
    http = HTTP(gets={fo.CREDITS_URL: Reply(200, {"data": {"total_credits": 10, "total_usage": 2.5}})})
    assert account_balance(http, "sk-or-v1-x") == {"ok": True, "left": 7.5, "total": 10.0, "used": 2.5, "empty": False,
                                                   "source": "credits"}
    assert http.calls[0][1] == "Bearer sk-or-v1-x"


def test_zero_credits_is_empty():
    http = HTTP(gets={fo.CREDITS_URL: Reply(200, {"data": {"total_credits": 5, "total_usage": 5}})})
    result = account_balance(http, "sk-or-v1-x")
    assert result["ok"] and result["empty"] and result["left"] == 0


def test_a_key_without_access_to_the_credits_falls_back_to_its_own_limit():
    http = HTTP(gets={fo.CREDITS_URL: Reply(403, {"error": {"message": "forbidden", "code": 403}}),
                      fo.KEY_USAGE_URL: Reply(200, {"data": {"usage": 1.25, "limit_remaining": 0.0}})})
    result = account_balance(http, "sk-or-v1-x")
    assert result["ok"] and result["source"] == "key" and result["empty"]


def test_a_wrong_key_is_refused_and_an_offline_check_is_not_an_error():
    refused = HTTP(gets={fo.CREDITS_URL: Reply(401, {"error": {"message": "User not found.", "code": 401}}),
                         fo.KEY_USAGE_URL: Reply(401, {"error": {"message": "User not found.", "code": 401}})})
    assert account_balance(refused, "sk-or-v1-x") == {"ok": False, "refused": True,
                                                      "error": "OpenRouter refused this key: it is wrong or was deleted"}
    offline = HTTP(gets={fo.CREDITS_URL: OSError("no network")})
    result = account_balance(offline, "sk-or-v1-x")
    assert result["ok"] is False and result["refused"] is False and "sk-or" not in json.dumps(result)


# ---- a chosen model that left the catalog ---------------------------------------------------------------------------
def test_the_model_list_reads_ids_and_canonical_slugs():
    http = HTTP(gets={fo.MODELS_URL: Reply(200, {"data": [{"id": "z-ai/glm-5", "canonical_slug": "z-ai/glm-5-20260101"},
                                                          {"id": "deepseek/deepseek-v4.1-flash"}]})})
    assert fetch_model_ids(http) == {"z-ai/glm-5", "z-ai/glm-5-20260101", "deepseek/deepseek-v4.1-flash"}
    with pytest.raises(OpenRouterError):
        fetch_model_ids(HTTP(gets={fo.MODELS_URL: Reply(200, {"data": []})}))


class Manager:
    def __init__(self):
        def row(model, transport="openrouter"):
            return {"transport": transport, "config": {"model_id": model, "canonical_slug": model}}
        self.options = {"deep": {"deep:gone": row("qwen/qwen3-235b-a22b"), "deep:glm": row("z-ai/glm-5")},
                        "surface": {"surface:ds": row("deepseek/deepseek-v4.1-flash"),
                                    "surface:local": {"transport": "ollama", "config": {"model_id": "gemma3:27b"}}}}
        self.selections = {"deep": "deep:gone", "surface": "surface:local"}
        self.document = {"presets": [{"name": "Default", "provider": "openrouter",
                                      "selections": {"deep": "deep:glm", "surface": "surface:ds"}}]}

    def _preset_ok(self, preset):
        return True


class App:
    def __init__(self):
        self.routes = {}

    def route(self, path, methods=("GET",)):
        def register(fn):
            for method in methods:
                self.routes[(path, method)] = fn
            return fn
        return register


class Args:
    def __init__(self, **values):
        self.values = values

    def get(self, name, default=None):
        return self.values.get(name, default)


def test_a_chosen_model_that_left_openrouter_is_named_with_the_preset(capsys):
    from f_controls import install_catalog_check
    offered = {"data": [{"id": "z-ai/glm-5"}, {"id": "deepseek/deepseek-v4.1-flash"}]}
    started = threading.Event()
    g = {"app": App(), "jsonify": lambda value: value, "F_ROLES": Manager(), "request": type("R", (), {"args": Args()})(),
         "http_requests": HTTP(gets={fo.MODELS_URL: Reply(200, offered)}), "f_resume_pending": started.set}
    install_catalog_check(g)
    result = g["app"].routes[("/api/build_f/openrouter/catalog", "GET")]()
    assert result["checked"] and result["missing"] == [{"role": "deep", "model": "qwen/qwen3-235b-a22b"}]
    assert result["preset"] == "Default" and result["preset_missing"] == []
    g["f_resume_pending"]()                       # the boot-time resume still runs, and the check follows it
    assert started.is_set()


def test_without_the_model_list_nothing_is_called_gone():
    from f_controls import install_catalog_check
    g = {"app": App(), "jsonify": lambda value: value, "F_ROLES": Manager(), "request": type("R", (), {"args": Args()})(),
         "http_requests": HTTP(gets={fo.MODELS_URL: OSError("offline")})}
    install_catalog_check(g)
    result = g["F_CATALOG_STATUS"]()
    assert result["checked"] is False and result["missing"] == [] and "unavailable" in result["error"]


# ---- the key save answers with the balance --------------------------------------------------------------------------
def test_saving_a_key_answers_with_its_balance_and_applies_it_at_once(tmp_path, monkeypatch):
    import f_persona
    monkeypatch.setattr(f_persona, "BRAIN_DIR", tmp_path)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=sk-or-v1-your-key-here\nOTHER=1\n", "utf-8")
    monkeypatch.setenv("OPENROUTER_API_KEY", "old")
    key = "sk-or-v1-" + "a" * 64
    request = type("R", (), {})()
    request.headers = {"X-Build-F-Action": "openrouter-key"}
    request.is_json = True
    request.get_json = lambda **kw: {"key": key}
    request.args = Args(credits="1")
    http = HTTP(gets={fo.CREDITS_URL: Reply(200, {"data": {"total_credits": 5, "total_usage": 5}})})
    g = {"app": App(), "request": request, "jsonify": lambda value: value, "http_requests": http, "OPENROUTER_KEY": "stale"}
    f_persona.install_persona(g)
    result = g["app"].routes[("/api/build_f/openrouter_key", "POST")]()
    assert result["ok"] and result["credits"]["empty"] and "no credits" in result["note"] and "prepaid" in result["note"]
    assert f_persona.os.environ["OPENROUTER_API_KEY"] == key and "OPENROUTER_KEY" not in g
    assert "OPENROUTER_API_KEY=" + key in (tmp_path / ".env").read_text("utf-8")
    status = g["app"].routes[("/api/build_f/openrouter_key", "GET")]()
    assert status["present"] and status["credits"]["empty"] and key not in json.dumps(status)
