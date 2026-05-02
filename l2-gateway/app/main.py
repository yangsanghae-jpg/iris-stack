import os
import time
import uuid
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

APP_NAME = "iris-l2-gateway"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/")

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
def openai_chat_completions(req: OpenAIChatCompletionRequest):
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
    payload = {
        "model": req.model,
        "messages": [m.model_dump() for m in req.messages],
        "stream": False,
        "think": False,
    }
    if options:
        payload["options"] = options
    created = int(time.time())
    request_id = f"chatcmpl-iris-{uuid.uuid4().hex[:12]}"
    try:
        print("[L2] /v1/chat/completions request:", {
            "model": req.model,
            "message_count": len(req.messages),
            "stream": req.stream,
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
        ],
    }
