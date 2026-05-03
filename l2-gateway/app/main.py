import json
import os
import time
import uuid
import httpx
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple, AsyncIterator

APP_NAME = "iris-l2-gateway"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/")


def _normalize_l4_search_urls() -> Tuple[str, str]:
    """Return (base for /health, full URL for POST /search)."""
    raw = os.getenv("L4_SEARCH_URL", "http://l4-search:8020/search").strip().rstrip("/")
    if raw.endswith("/search"):
        base = raw[: -len("/search")]
        post_url = raw
    else:
        base = raw.rstrip("/")
        post_url = f"{base}/search"
    return base, post_url


L4_SEARCH_BASE, L4_SEARCH_POST_URL = _normalize_l4_search_urls()

# 명시형 기본 트리거(v0.1). IRIS_SEARCH_TRIGGERS 환경변수로 덮어쓸 수 있음.
_DEFAULT_TRIGGERS_CSV = (
    "검색,찾아봐,최신,오늘,현재,뉴스,공휴일,주가,가격,2026,법정,일정,트렌드"
)

IRIS_TRACE_ROUTE = "openwebui -> l2 -> l4-search -> ollama"


def _parse_bool_env(name: str, default: bool = True) -> bool:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on", "y")


def _parse_max_results() -> int:
    try:
        n = int(os.getenv("IRIS_SEARCH_MAX_RESULTS", "3"))
    except ValueError:
        n = 3
    return max(1, min(n, 20))


def get_iris_search_settings() -> Dict[str, Any]:
    raw_triggers = os.getenv("IRIS_SEARCH_TRIGGERS")
    if raw_triggers is None or not str(raw_triggers).strip():
        trigger_list = [t.strip() for t in _DEFAULT_TRIGGERS_CSV.split(",") if t.strip()]
    else:
        trigger_list = [t.strip() for t in str(raw_triggers).split(",") if t.strip()]
    return {
        "search_enabled": _parse_bool_env("IRIS_SEARCH_ENABLED", True),
        "append_sources": _parse_bool_env("IRIS_APPEND_SEARCH_SOURCES", True),
        "max_results": _parse_max_results(),
        "triggers": trigger_list,
    }


def find_matched_triggers(text: str, triggers: List[str]) -> List[str]:
    if not text or not str(text).strip():
        return []
    t = str(text).lower()
    matched: List[str] = []
    for kw in triggers:
        if not kw:
            continue
        if kw.lower() in t:
            matched.append(kw)
    return matched


def should_use_search(text: str, settings: Optional[Dict[str, Any]] = None) -> bool:
    cfg = settings if settings is not None else get_iris_search_settings()
    if not cfg.get("search_enabled", True):
        return False
    if not text or not str(text).strip():
        return False
    triggers = cfg.get("triggers") or []
    return len(find_matched_triggers(text, triggers)) > 0


async def call_l4_search(query: str, limit: int = 3) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                L4_SEARCH_POST_URL,
                json={"query": query, "limit": limit},
            )
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else {"ok": False, "error": "invalid response", "results": []}
    except httpx.HTTPStatusError as e:
        try:
            err_body = e.response.json()
            msg = err_body.get("error", str(e))
        except Exception:
            msg = (e.response.text or str(e)).strip() or str(e)
        return {"ok": False, "error": msg, "results": []}
    except Exception as e:
        return {"ok": False, "error": str(e), "results": []}


def build_search_context(search_result: dict, max_results: int) -> str:
    if not search_result.get("ok"):
        return ""
    results = search_result.get("results") or []
    if not results:
        return ""
    n = max(1, min(int(max_results), 20))
    lines = [
        "[IRIS_SEARCH_CONTEXT]",
        "아래 내용은 Firecrawl 검색 결과입니다. 답변은 가능한 한 이 검색 결과를 근거로 작성하십시오.",
        "검색 결과에 없는 내용을 확정적으로 말하지 마십시오.",
    ]
    for i, item in enumerate(results[:n], start=1):
        title = item.get("title") or ""
        url = item.get("url") or ""
        summary = item.get("snippet") or item.get("description") or ""
        lines.append(f"[{i}]")
        lines.append(f"title: {title}")
        lines.append(f"url: {url}")
        lines.append(f"summary: {summary}")
    lines.append("[/IRIS_SEARCH_CONTEXT]")
    return "\n".join(lines)


def build_iris_source_footer(search_result: Optional[dict], max_results: int) -> str:
    """OpenWebUI 등에서 보이도록 답변 끝에 붙일 출처 블록. URL이 없으면 빈 문자열."""
    if not search_result or not search_result.get("ok"):
        return ""
    results = search_result.get("results") or []
    n = max(1, min(int(max_results), 20))
    entries: List[str] = []
    for item in results[:n]:
        url = (item.get("url") or "").strip()
        if not url:
            continue
        title = (item.get("title") or "").strip() or "(제목 없음)"
        entries.append(f"{len(entries) + 1}. {title} - {url}")
    if not entries:
        return ""
    return "\n\n[IRIS 검색 출처]\n" + "\n".join(entries)


def build_iris_trace(
    *,
    model: str,
    stream: bool,
    search_used: bool,
    search_result: Optional[dict],
    max_results: int,
    last_user_text: str,
    settings: Dict[str, Any],
) -> dict:
    """OpenWebUI /v1/chat/completions용 표준 iris_trace (stream 시 마지막 chunk에만 첨부)."""
    cap = max(1, min(int(max_results), 20))
    triggers_cfg = settings.get("triggers") or []
    matched = find_matched_triggers(last_user_text, triggers_cfg)

    out: Dict[str, Any] = {
        "l2_gateway": True,
        "model": model,
        "search_used": bool(search_used),
        "search_ok": False,
        "search_count": 0,
        "search_urls": [],
        "route": IRIS_TRACE_ROUTE,
        "stream": bool(stream),
        "matched_triggers": matched,
    }

    if not search_used or search_result is None:
        return out

    ok = bool(search_result.get("ok"))
    results = search_result.get("results") or []
    urls = [item.get("url") for item in results if item.get("url")][:cap]
    out["search_ok"] = ok
    out["search_count"] = len(results)
    out["search_urls"] = urls
    if not ok:
        err = search_result.get("error")
        out["search_error"] = str(err) if err is not None else "search failed"
    return out


def _sse_data(obj: Any) -> bytes:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")


def _openai_chunk(
    request_id: str,
    created: int,
    model: str,
    *,
    role: Optional[str] = None,
    content: Optional[str] = None,
    finish_reason: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    delta: Dict[str, Any] = {}
    if role is not None:
        delta["role"] = role
    if content is not None:
        delta["content"] = content
    out: Dict[str, Any] = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }
    if extra:
        out.update(extra)
    return out


async def _ollama_chat_stream_sse(
    ollama_payload: Dict[str, Any],
    request_id: str,
    created: int,
    model: str,
    iris_trace: Dict[str, Any],
    search_used: bool,
    settings: Dict[str, Any],
    search_result: Optional[dict],
) -> AsyncIterator[bytes]:
    """Ollama /api/chat NDJSON(stream) → OpenAI 호환 SSE."""
    yield _sse_data(
        _openai_chunk(request_id, created, model, role="assistant", content=None)
    )

    last_content = ""
    timeout = httpx.Timeout(180.0, connect=30.0)
    try:
        print("[L2] calling Ollama", flush=True)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/chat",
                json=ollama_payload,
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    line = (line or "").strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if obj.get("error"):
                        err = obj["error"]
                        msg = err if isinstance(err, str) else (err.get("message") or str(err))
                        yield _sse_data({"error": {"message": msg, "type": "ollama_error"}})
                        return

                    msg = obj.get("message") or {}
                    cur_raw = msg.get("content")
                    cur = "" if cur_raw is None else str(cur_raw)
                    done = bool(obj.get("done"))

                    if cur.startswith(last_content):
                        delta_text = cur[len(last_content) :]
                    else:
                        delta_text = cur
                        last_content = ""
                    last_content = cur if cur else last_content

                    if delta_text:
                        yield _sse_data(
                            _openai_chunk(
                                request_id,
                                created,
                                model,
                                content=delta_text,
                            )
                        )

                    if done:
                        if search_used and settings.get("append_sources", True) and search_result is not None:
                            footer = build_iris_source_footer(
                                search_result,
                                int(settings["max_results"]),
                            )
                            if footer:
                                yield _sse_data(
                                    _openai_chunk(
                                        request_id,
                                        created,
                                        model,
                                        content=footer,
                                    )
                                )

                        fr = obj.get("done_reason") or "stop"
                        last_chunk = _openai_chunk(
                            request_id,
                            created,
                            model,
                            finish_reason=fr,
                        )
                        last_chunk["iris_trace"] = iris_trace
                        yield _sse_data(last_chunk)
                        yield b"data: [DONE]\n\n"
                        print("[L2] response ok", flush=True)
                        return
    except httpx.HTTPStatusError as e:
        yield _sse_data(
            {
                "error": {
                    "message": f"Ollama HTTP {e.response.status_code}",
                    "type": "http_error",
                }
            }
        )
    except Exception as e:
        yield _sse_data({"error": {"message": str(e), "type": "internal_error"}})


app = FastAPI(title=APP_NAME)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: bool = False
    options: Optional[Dict[str, Any]] = None


class OpenAIChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    options: Optional[Dict[str, Any]] = None


class SearchProxyRequest(BaseModel):
    query: str
    limit: int = 3


class SearchDecisionDebugRequest(BaseModel):
    text: str


def get_last_user_content(messages: List[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user" and m.content is not None:
            s = str(m.content).strip()
            if s:
                return s
    return ""


@app.get("/search/health")
def search_health_proxy():
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{L4_SEARCH_BASE}/health")
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"L4-search health failed: {e}")


@app.post("/search")
def search_proxy(body: SearchProxyRequest):
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                f"{L4_SEARCH_BASE}/search",
                json={"query": body.query, "limit": body.limit},
            )
            r.raise_for_status()
            data = r.json()
        if isinstance(data, dict):
            return {**data, "via": "l2-gateway"}
        return {"via": "l2-gateway", "data": data}
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json()
        except Exception:
            detail = {"error": e.response.text}
        raise HTTPException(status_code=e.response.status_code, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"L4-search proxy failed: {e}")


@app.get("/health")
def health():
    return {
        "ok": True,
        "app": APP_NAME,
        "ollama_base_url": OLLAMA_BASE_URL,
        "ts": int(time.time()),
        "openwebui_chat_path": "/v1/chat/completions",
        "route": IRIS_TRACE_ROUTE,
        "l4_search_base": L4_SEARCH_BASE,
    }


@app.get("/models")
def models():
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama models fetch failed: {e}")


@app.get("/v1/models")
def openai_models():
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        r.raise_for_status()
        data = r.json()
        models = data.get("models", [])
        return {
            "object": "list",
            "data": [
                {
                    "id": m.get("name"),
                    "object": "model",
                    "created": 0,
                    "owned_by": "iris-ollama",
                }
                for m in models
                if m.get("name")
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama models fetch failed: {e}")


@app.post("/chat")
def chat(req: ChatRequest):
    """
    Minimal L2 chat endpoint.
    현재는 OpenAI 호환이 아니라 Ollama /api/chat passthrough에 가깝게 동작한다.
    """
    payload = {
        "model": req.model,
        "messages": [m.model_dump() for m in req.messages],
        "stream": req.stream,
    }
    if req.options:
        payload["options"] = req.options
    try:
        print("[L2] /chat request:", {
            "model": req.model,
            "message_count": len(req.messages),
            "stream": req.stream,
        }, flush=True)
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        print("[L2] /chat response ok", flush=True)
        return data
    except Exception as e:
        print("[L2] /chat error:", str(e), flush=True)
        raise HTTPException(status_code=502, detail=f"Ollama chat failed: {e}")


@app.post("/v1/chat/completions")
async def openai_chat_completions(req: OpenAIChatCompletionRequest):
    print(
        "[L2] request received",
        {"path": "/v1/chat/completions", "model": req.model, "stream": req.stream},
        flush=True,
    )

    options = req.options.copy() if req.options else {}
    if req.temperature is not None:
        options["temperature"] = req.temperature
    if req.max_tokens is not None:
        options["num_predict"] = req.max_tokens
    if req.top_p is not None:
        options["top_p"] = req.top_p

    settings = get_iris_search_settings()
    last_user_content = get_last_user_content(req.messages)
    search_used = should_use_search(last_user_content, settings)
    print(f"[L2] search decision: {search_used}", flush=True)

    search_result: Optional[dict] = None
    search_context = ""

    if search_used:
        print("[L2] calling L4-search", flush=True)
        search_result = await call_l4_search(
            last_user_content,
            limit=int(settings["max_results"]),
        )
        search_context = build_search_context(
            search_result,
            int(settings["max_results"]),
        )
        ok = bool(search_result.get("ok"))
        cnt = len(search_result.get("results") or [])
        print(f"[L2] L4-search result: ok={ok} count={cnt}", flush=True)

    messages_for_ollama: List[Dict[str, Any]] = [m.model_dump() for m in req.messages]
    if search_context:
        messages_for_ollama.insert(
            0,
            {"role": "system", "content": search_context},
        )

    payload: Dict[str, Any] = {
        "model": req.model,
        "messages": messages_for_ollama,
        "stream": bool(req.stream),
        "think": False,
    }
    if options:
        payload["options"] = options
    created = int(time.time())
    request_id = f"chatcmpl-iris-{uuid.uuid4().hex[:12]}"
    iris_trace = build_iris_trace(
        model=req.model,
        stream=bool(req.stream),
        search_used=search_used,
        search_result=search_result,
        max_results=int(settings["max_results"]),
        last_user_text=last_user_content,
        settings=settings,
    )

    if req.stream:
        return StreamingResponse(
            _ollama_chat_stream_sse(
                payload,
                request_id,
                created,
                req.model,
                iris_trace,
                search_used,
                settings,
                search_result,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    payload["stream"] = False
    try:
        print("[L2] calling Ollama", flush=True)
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=180,
        )
        r.raise_for_status()
        data = r.json()
        content = (
            data.get("message", {}) or {}
        ).get("content", "")
        if search_used and settings.get("append_sources", True):
            footer = build_iris_source_footer(
                search_result,
                int(settings["max_results"]),
            )
            if footer:
                content = f"{str(content).rstrip()}{footer}"
        print("[L2] response ok", flush=True)
        return {
            "id": request_id,
            "object": "chat.completion",
            "created": created,
            "model": req.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": data.get("done_reason", "stop") or "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "iris_trace": iris_trace,
        }
    except Exception as e:
        print("[L2] /v1/chat/completions error:", str(e), flush=True)
        raise HTTPException(status_code=502, detail=f"Ollama chat failed: {e}")


@app.post("/debug/search-decision")
def debug_search_decision(body: SearchDecisionDebugRequest):
    cfg = get_iris_search_settings()
    matched = find_matched_triggers(body.text, cfg["triggers"])
    use = bool(cfg["search_enabled"]) and len(matched) > 0
    return {
        "search_enabled": cfg["search_enabled"],
        "should_use_search": use,
        "matched_triggers": matched,
        "max_results": cfg["max_results"],
        "append_sources": cfg["append_sources"],
        "route": IRIS_TRACE_ROUTE,
    }


@app.get("/")
def root():
    return {
        "app": APP_NAME,
        "routes": [
            "/health",
            "/models",
            "/chat",
            "/v1/models",
            "/v1/chat/completions",
            "/search/health",
            "/search",
            "/debug/search-decision",
        ],
    }
