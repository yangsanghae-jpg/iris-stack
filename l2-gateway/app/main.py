import os
import time
import uuid
import httpx
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple

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

SEARCH_TRIGGERS = [
    "검색",
    "찾아",
    "최신",
    "오늘",
    "현재",
    "지금",
    "뉴스",
    "주가",
    "공휴일",
    "일정",
    "가격",
    "2025",
    "2026",
    "2027",
    "search",
    "latest",
    "today",
    "current",
    "news",
    "price",
]


def should_use_search(text: str) -> bool:
    if not text or not str(text).strip():
        return False
    t = str(text).lower()
    for kw in SEARCH_TRIGGERS:
        if kw.lower() in t:
            return True
    return False


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


def build_search_context(search_result: dict) -> str:
    if not search_result.get("ok"):
        return ""
    results = search_result.get("results") or []
    if not results:
        return ""
    lines = [
        "[IRIS_SEARCH_CONTEXT]",
        "아래 내용은 Firecrawl 검색 결과입니다. 답변은 가능한 한 이 검색 결과를 근거로 작성하십시오.",
        "검색 결과에 없는 내용을 확정적으로 말하지 마십시오.",
    ]
    for i, item in enumerate(results[:3], start=1):
        title = item.get("title") or ""
        url = item.get("url") or ""
        summary = item.get("snippet") or item.get("description") or ""
        lines.append(f"[{i}]")
        lines.append(f"title: {title}")
        lines.append(f"url: {url}")
        lines.append(f"summary: {summary}")
    lines.append("[/IRIS_SEARCH_CONTEXT]")
    return "\n".join(lines)


def build_iris_source_footer(search_result: Optional[dict]) -> str:
    """OpenWebUI 등에서 보이도록 답변 끝에 붙일 출처 블록. URL이 없으면 빈 문자열."""
    if not search_result or not search_result.get("ok"):
        return ""
    results = search_result.get("results") or []
    entries: List[str] = []
    for item in results[:3]:
        url = (item.get("url") or "").strip()
        if not url:
            continue
        title = (item.get("title") or "").strip() or "(제목 없음)"
        entries.append(f"{len(entries) + 1}. {title} - {url}")
    if not entries:
        return ""
    return "\n\n[IRIS 검색 출처]\n" + "\n".join(entries)


def build_iris_trace(
    search_used: bool,
    search_result: Optional[dict],
) -> dict:
    if not search_used or search_result is None:
        return {
            "l2_gateway": True,
            "search_checked": True,
            "search_used": False,
            "search_ok": False,
            "search_provider": None,
            "search_count": 0,
            "search_urls": [],
        }
    ok = bool(search_result.get("ok"))
    results = search_result.get("results") or []
    urls = [item.get("url") for item in results if item.get("url")][:3]
    return {
        "l2_gateway": True,
        "search_checked": True,
        "search_used": True,
        "search_ok": ok,
        "search_provider": "firecrawl",
        "search_count": len(results),
        "search_urls": urls,
    }

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
    if req.stream:
        raise HTTPException(
            status_code=400,
            detail="stream=true is not supported yet by iris-l2-gateway v0.1",
        )
    options = req.options.copy() if req.options else {}
    if req.temperature is not None:
        options["temperature"] = req.temperature
    if req.max_tokens is not None:
        options["num_predict"] = req.max_tokens
    if req.top_p is not None:
        options["top_p"] = req.top_p

    last_user_content = get_last_user_content(req.messages)
    search_used = should_use_search(last_user_content)
    search_result: Optional[dict] = None
    search_context = ""

    if search_used:
        print("[L2] /v1/chat/completions search branch: calling L4-search", flush=True)
        search_result = await call_l4_search(last_user_content, limit=3)
        search_context = build_search_context(search_result)
        print(
            "[L2] /v1/chat/completions search branch: ok=",
            search_result.get("ok"),
            "count=",
            len(search_result.get("results") or []),
            flush=True,
        )

    messages_for_ollama: List[Dict[str, Any]] = [m.model_dump() for m in req.messages]
    if search_context:
        messages_for_ollama.insert(
            0,
            {"role": "system", "content": search_context},
        )

    payload = {
        "model": req.model,
        "messages": messages_for_ollama,
        "stream": False,
        "think": False,
    }
    if options:
        payload["options"] = options
    created = int(time.time())
    request_id = f"chatcmpl-iris-{uuid.uuid4().hex[:12]}"
    iris_trace = build_iris_trace(search_used, search_result)
    try:
        print("[L2] /v1/chat/completions request:", {
            "model": req.model,
            "message_count": len(req.messages),
            "ollama_message_count": len(messages_for_ollama),
            "stream": req.stream,
            "search_used": search_used,
        }, flush=True)
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
        if search_used:
            footer = build_iris_source_footer(search_result)
            if footer:
                content = f"{str(content).rstrip()}{footer}"
        print("[L2] /v1/chat/completions response ok", flush=True)
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
        ],
    }
