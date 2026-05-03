import json
import os
import re
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

_THINK_BLOCK_RE = re.compile(
    r"<think>[\s\S]*?</think>",
    re.IGNORECASE,
)

_REASON_LINE_PREFIXES_EN = (
    "okay,",
    "the user is asking",
    "the user provided",
    "user is asking",
    "let me think",
    "let me analyze",
    "let me check",
    "let me review",
    "let me see",
    "i need to",
    "first, i need to",
    "looking at the search results",
    "i should",
    "now i need to",
    "i will",
    "we need to",
)


def _strip_leading_english_reasoning(s: str) -> str:
    """답변 앞부분에 붙는 영어 self-reasoning 줄만 보수적으로 제거."""
    lines = s.splitlines()
    i = 0
    removed = 0
    while i < len(lines) and removed < 48:
        line = lines[i].strip()
        if not line:
            i += 1
            removed += 1
            continue
        low = line.lower()
        if not any(low.startswith(p) for p in _REASON_LINE_PREFIXES_EN):
            break
        hangul = sum(1 for c in line if "\uac00" <= c <= "\ud7af")
        if hangul >= 4:
            break
        i += 1
        removed += 1
    return "\n".join(lines[i:]).lstrip()


def _strip_leading_search_walkthrough_lines(s: str) -> str:
    """앞쪽 'Let me…' / 'User is asking' / '[n] - …' 영어 검색 해설 줄 제거."""
    lines = s.splitlines()
    i = 0
    max_scan = min(len(lines), 160)
    while i < max_scan:
        st = lines[i].strip()
        if not st:
            i += 1
            continue
        low = st.lower()
        hangul = sum(1 for c in st if "\uac00" <= c <= "\ud7af")
        removed = False

        if re.match(r"^\[\d+\]\s+", st) and hangul < 8:
            i += 1
            removed = True
        elif re.match(r"^\d+\.\s+", st) and hangul < 8:
            if any(
                k in low
                for k in (
                    "result",
                    "pdf",
                    "search",
                    "dictionary",
                    "catti",
                    "grammar",
                    "syntax",
                    "mention",
                    "textbook",
                    "translation",
                )
            ):
                i += 1
                removed = True
        elif low.startswith("let me ") or low.startswith("user is asking"):
            i += 1
            removed = True
        elif low.startswith("first, i") and hangul < 6 and ("search" in low or "result" in low):
            i += 1
            removed = True
        elif low.startswith("let me check the search results"):
            i += 1
            removed = True
        elif low.startswith("checking the search results"):
            i += 1
            removed = True
        elif hangul < 12 and low.startswith("'s look"):
            i += 1
            removed = True
        elif hangul < 12 and "look at the search results" in low:
            i += 1
            removed = True
        elif hangul < 20 and "i'll respond in korean" in low:
            i += 1
            removed = True
        elif hangul < 10 and re.match(r"^result\s+\d+\s*:", low, re.IGNORECASE):
            i += 1
            removed = True
        elif re.match(r"^search result\s*\[", low):
            i += 1
            removed = True
        elif hangul < 16 and "none of these" in low and ("search" in low or "result" in low):
            i += 1
            removed = True
        elif hangul < 14 and low.startswith("hmm,"):
            i += 1
            removed = True

        if removed:
            continue
        if hangul >= 6:
            break
        break
    return "\n".join(lines[i:]).lstrip()


_META_PARAGRAPH_HINTS = (
    "i need to make sure",
    "the rules say",
    "since there's no information",
    "since there is no information",
    "since there are no",
    "provided search results",
    "search results don't",
    "search results do not",
    "none of the search results",
    "none of these results mention",
    "none of these search results mention",
    "the user is asking for",
    "inform the user that",
    "don't contain any relevant",
    "confidence is low",
    "i should inform the user",
    "no information about",
)


def _strip_english_meta_paragraphs(s: str) -> str:
    """본문 중간에 끼는 영어 검색/계획 메타 단락만 제거(한글 본문 보존)."""
    if not (s or "").strip():
        return s or ""
    blocks = re.split(r"\n{2,}", s)
    kept: List[str] = []
    for b in blocks:
        t = b.strip()
        if not t:
            continue
        low = t.lower()
        hangul = sum(1 for c in t if "\uac00" <= c <= "\ud7af")
        if hangul >= 8:
            kept.append(t)
            continue
        if re.match(r"^\[\d+\]\s+", t) and hangul < 8:
            continue
        if re.search(r"result\s*\[\d+\]", low) and hangul < 8:
            continue
        searchish = "search" in low or re.search(r"result\s*\[\d+\]", low) is not None
        if (
            len(t) > 28
            and hangul < 8
            and searchish
            and (
                any(h in low for h in _META_PARAGRAPH_HINTS)
                or ("i need to" in low and len(t) > 40)
                or ("i should" in low and "user" in low)
            )
        ):
            continue
        kept.append(t)
    return "\n\n".join(kept).strip()


def extract_query_terms(user_text: str) -> List[str]:
    """질문에서 핵심어 추출(최소 동작)."""
    if not user_text or not str(user_text).strip():
        return []
    text = str(user_text)
    terms: List[str] = []
    seen: set[str] = set()

    def add(t: str) -> None:
        t = (t or "").strip()
        if len(t) < 2:
            return
        key = t.lower()
        if key not in seen:
            seen.add(key)
            terms.append(t)

    for m in re.finditer(r"""["']([^"']{2,})["']""", text):
        add(m.group(1))
    for m in re.finditer(r"\b(19|20)\d{2}\b", text):
        add(m.group(0))
    for m in re.finditer(r"[\u3131-\u318E\uAC00-\uD7A3]{2,}", text):
        add(m.group(0))
    for m in re.finditer(r"[\u4e00-\u9fff]{2,}", text):
        add(m.group(0))
    for m in re.finditer(r"[A-Za-z]{2,}", text):
        add(m.group(0))
    for m in re.finditer(r"\$[A-Za-z]{1,6}\b|\b[A-Z]{2,6}\b", text):
        add(m.group(0).lstrip("$"))
    return terms


def _search_result_haystack(result: dict) -> str:
    parts: List[str] = []
    for k in ("title", "url", "description", "content", "snippet"):
        v = result.get(k)
        if v is not None and str(v).strip():
            parts.append(str(v))
    return " ".join(parts)


def score_search_result_relevance(result: dict, query_terms: List[str]) -> Dict[str, Any]:
    hay = _search_result_haystack(result).lower()
    matched: List[str] = []
    for term in query_terms:
        tl = term.lower()
        if tl and tl in hay:
            matched.append(term)
    return {
        "matched_terms": matched,
        "score": len(matched),
        "low_confidence": len(matched) == 0,
    }


def filter_search_results(search_result: dict, user_text: str) -> dict:
    """
    L4 원본을 유지하면서 results는 relevance 있는 항목만 남김.
    전부 low면 ok 유지 + low_confidence + relevance_warning.
    """
    out: Dict[str, Any] = dict(search_result)
    results = list(out.get("results") or [])
    orig_n = len(results)
    preview = [{"title": r.get("title"), "url": r.get("url")} for r in results[: max(8, orig_n)]]
    out["original_results_preview"] = preview

    if not out.get("ok") or orig_n == 0:
        out["_iris_original_count"] = orig_n
        out["_iris_filtered_count"] = orig_n
        out["low_confidence"] = False
        out.pop("relevance_warning", None)
        return out

    terms = extract_query_terms(user_text)
    if not terms:
        out["_iris_original_count"] = orig_n
        out["_iris_filtered_count"] = orig_n
        out["low_confidence"] = False
        out.pop("relevance_warning", None)
        return out

    kept: List[dict] = []
    for r in results:
        sc = score_search_result_relevance(r, terms)
        if not sc["low_confidence"]:
            kept.append(r)

    out["_iris_original_count"] = orig_n
    if not kept:
        out["results"] = []
        out["low_confidence"] = True
        out["relevance_warning"] = "Search results do not strongly match the user query."
        out["_iris_filtered_count"] = 0
        return out

    out["results"] = kept
    out["low_confidence"] = False
    out.pop("relevance_warning", None)
    out["_iris_filtered_count"] = len(kept)
    return out


def strip_thinking_content(text: str) -> str:
    """redacted_thinking 태그 및 앞부분 영어 reasoning 제거."""
    s = text or ""
    s = _THINK_BLOCK_RE.sub("", s)
    s = s.replace("<think>", "").replace("</think>", "")
    for _ in range(8):
        n = _strip_leading_english_reasoning(s)
        n = _strip_leading_search_walkthrough_lines(n)
        if n == s:
            s = n
            break
        s = n
    s = _strip_english_meta_paragraphs(s)
    return s


def strip_model_generated_source_blocks(content: str) -> str:
    """모델이 본문에 만든 출처 블록 제거(L2 footer 1회만 유지)."""
    s = (content or "").rstrip()
    if not s:
        return ""
    cut = len(s)
    iris = s.find("[IRIS 검색 출처]")
    if iris >= 0:
        cut = min(cut, iris)
    thresh = int(len(s) * 0.7)
    tail_markers = (
        "검색 결과 출처",
        "\n\nSources:",
        "\nSources:",
        "Sources:",
        "\n\nReferences:",
        "\nReferences:",
        "References:",
        "\n\n출처:",
        "\n출처:",
    )
    for m in tail_markers:
        j = s.find(m)
        if j >= 0 and j >= thresh:
            cut = min(cut, j)
    for marker in ("\n\n검색 결과 출처", "\n검색 결과 출처"):
        j = s.find(marker)
        if j >= 0:
            cut = min(cut, j)
    for marker in ("\n\n출처:", "\n출처:", "출처:", "\n\n출처：", "\n출처：", "출처："):
        j = s.find(marker)
        if j >= 0 and j >= thresh:
            cut = min(cut, j)
    out = s[:cut].rstrip() if cut < len(s) else s
    return out.rstrip()


def normalize_answer_markdown(text: str) -> str:
    """깨진 마크다운 최소 정리."""
    s = text or ""
    s = re.sub(r"(?<![#\n])#{4,}\s*", "### ", s)
    s = re.sub(r"(---)(#{2,})", r"\1\n\n\2", s)

    def _fix_line(line: str) -> str:
        st = line.lstrip()
        if st.startswith(">") and not st.startswith(">>"):
            rest = re.sub(r"^\s*>\s?", "", line)
            if rest.strip()[:2] in ("📌", "✅", "▶", "🔹", "📎"):
                return rest.rstrip("\n")
        return line

    s = "\n".join(_fix_line(ln) for ln in s.split("\n"))
    s = re.sub(r"\n{4,}", "\n\n", s)
    s = re.sub(r"([\.!?。])\s*(#{1,6}\s)", r"\1\n\n\2", s)
    return s.strip()


def sanitize_final_answer(
    content: str,
    search_result: Optional[dict] = None,
) -> Tuple[str, Dict[str, bool]]:
    """최종 사용자 노출용 본문 정리(footer는 호출 측에서 1회만)."""
    _ = search_result
    raw = "" if content is None else str(content)
    a = strip_thinking_content(raw)
    b = strip_model_generated_source_blocks(a)
    c = normalize_answer_markdown(b)
    flags = {
        "stripped_think": a != raw,
        "stripped_sources": b != a,
        "normalized_md": c != b,
    }
    return c.strip(), flags


def _chunk_text_for_sse(text: str, max_chars: int = 900) -> List[str]:
    if not text:
        return []
    n = len(text)
    chunks: List[str] = []
    start = 0
    while start < n:
        end = min(n, start + max_chars)
        if end < n:
            cut = text.rfind("\n", start + 1, end)
            if cut <= start:
                cut = end
            else:
                end = cut + 1
        chunks.append(text[start:end])
        start = end
    return [c for c in chunks if c]


def _iris_search_rules_text() -> str:
    return "\n".join(
        [
            "[IRIS_SEARCH_RULES]",
            "- Use only the search results below when answering search-based questions.",
            "- Do not invent facts that are not present in the search results.",
            "- If the search results do not strongly match the user's target, say that the search result is low confidence.",
            "- If the user provided company/entity information conflicts with the search results, do not overwrite the user's information. State that the search results are insufficient or mismatched.",
            '- Do not create a separate "source list" in the main answer. The system will append sources automatically.',
            "- Keep the answer concise and evidence-based.",
            "",
            "[IRIS_SEARCH_RULES_KO]",
            "- 검색 기반 질문은 아래 검색 결과에 있는 내용만 사용한다.",
            "- 검색 결과에 없는 사실을 단정하지 않는다.",
            '- 검색 결과가 질문 대상과 강하게 일치하지 않으면 "검색 결과 신뢰도 낮음"이라고 명시한다.',
            '- 사용자가 제공한 회사명/대상 정보와 검색 결과가 충돌하면, 사용자 정보를 덮어쓰지 말고 "검색 결과만으로는 확인 불가"라고 말한다.',
            "- 본문 안에 별도 출처 목록을 만들지 않는다. 출처는 시스템이 답변 끝에 자동으로 붙인다.",
            "- 답변은 간결하고 근거 중심으로 작성한다.",
        ]
    )


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
    rules = _iris_search_rules_text()
    parts: List[str] = [rules]

    if search_result.get("low_confidence"):
        parts.append(
            "\n".join(
                [
                    "[IRIS_SEARCH_CONFIDENCE]",
                    "low_confidence: true",
                    "reason: Search results do not strongly match the user query.",
                    "instruction: Do not treat these results as confirmed facts. Explain that the search result is insufficient or mismatched.",
                ]
            )
        )

    results = search_result.get("results") or []
    if results:
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
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


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
        "search_low_confidence": False,
        "search_relevance_warning": None,
        "search_filtered_count": 0,
        "search_original_count": 0,
    }

    if not search_used or search_result is None:
        return out

    ok = bool(search_result.get("ok"))
    results = search_result.get("results") or []
    urls = [item.get("url") for item in results if item.get("url")][:cap]
    out["search_ok"] = ok
    out["search_count"] = len(results)
    out["search_urls"] = urls
    out["search_original_count"] = int(search_result.get("_iris_original_count", len(results) if ok else 0))
    out["search_filtered_count"] = int(search_result.get("_iris_filtered_count", len(results) if ok else 0))
    if search_result.get("low_confidence"):
        out["search_low_confidence"] = True
        out["search_relevance_warning"] = search_result.get("relevance_warning")
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
    """Ollama stream 수집 → sanitize → OpenAI SSE로 재전송(품질 우선)."""
    yield _sse_data(
        _openai_chunk(request_id, created, model, role="assistant", content=None)
    )

    last_full = ""
    done_reason = "stop"
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
                    # Ollama /api/chat stream: message.content는 대부분 누적 전체 문자열
                    if cur:
                        if not last_full:
                            last_full = cur
                        elif cur.startswith(last_full):
                            last_full = cur
                        elif last_full.startswith(cur):
                            pass
                        else:
                            last_full = last_full + cur
                    if done:
                        done_reason = obj.get("done_reason") or "stop"
                        fc = msg.get("content")
                        if isinstance(fc, str) and fc.strip():
                            if not last_full:
                                last_full = fc
                            elif fc.startswith(last_full):
                                last_full = fc
                            elif last_full.startswith(fc):
                                pass
                            else:
                                last_full = last_full + fc
                        break

        raw_full = last_full or ""
        clean, flags = sanitize_final_answer(raw_full, search_result)
        footer = ""
        if search_used and settings.get("append_sources", True) and search_result is not None:
            footer = build_iris_source_footer(search_result, int(settings["max_results"])) or ""
        final_text = clean
        if footer:
            final_text = f"{clean.rstrip()}{footer}"
        print(
            "[L2] content cleanup: "
            f"stripped_think={flags.get('stripped_think')} stripped_sources={flags.get('stripped_sources')}",
            flush=True,
        )
        pieces = _chunk_text_for_sse(final_text, max_chars=900)
        if not pieces:
            pieces = [""]
        for piece in pieces:
            yield _sse_data(
                _openai_chunk(
                    request_id,
                    created,
                    model,
                    content=piece,
                )
            )
        last_chunk = _openai_chunk(
            request_id,
            created,
            model,
            finish_reason=done_reason,
        )
        last_chunk["iris_trace"] = iris_trace
        yield _sse_data(last_chunk)
        yield b"data: [DONE]\n\n"
        print("[L2] response ok", flush=True)
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
        ok = bool(search_result.get("ok"))
        cnt = len(search_result.get("results") or [])
        print(f"[L2] L4-search result: ok={ok} count={cnt}", flush=True)
        if ok:
            search_result = filter_search_results(search_result, last_user_content)
            oc = int(search_result.get("_iris_original_count", 0))
            fc = int(search_result.get("_iris_filtered_count", 0))
            lc = bool(search_result.get("low_confidence"))
            print(
                f"[L2] search relevance: original_count={oc} filtered_count={fc} low_confidence={lc}",
                flush=True,
            )
        search_context = build_search_context(
            search_result,
            int(settings["max_results"]),
        )

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
        raw_content = (data.get("message", {}) or {}).get("content", "")
        raw_content = "" if raw_content is None else str(raw_content)
        clean_content, flags = sanitize_final_answer(raw_content, search_result)
        footer = ""
        if search_used and settings.get("append_sources", True):
            footer = build_iris_source_footer(
                search_result,
                int(settings["max_results"]),
            ) or ""
        content = clean_content if not footer else f"{clean_content.rstrip()}{footer}"
        print(
            "[L2] content cleanup: "
            f"stripped_think={flags.get('stripped_think')} stripped_sources={flags.get('stripped_sources')}",
            flush=True,
        )
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
