from pathlib import Path
import re

VAULT_PATH = Path(r"C:\Werkules\vault")
MAX_RESULTS = 8
MAX_SNIPPET_CHARS = 600

def _safe_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def _make_snippet(text: str, query: str) -> str:
    if not text:
        return ""
    q = query.strip().lower()
    lower = text.lower()
    if q and q in lower:
        idx = lower.find(q)
        start = max(0, idx - 220)
        end = min(len(text), idx + 380)
        snippet = text[start:end]
    else:
        snippet = text[:MAX_SNIPPET_CHARS]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if len(snippet) > MAX_SNIPPET_CHARS:
        snippet = snippet[:MAX_SNIPPET_CHARS].rstrip() + "..."
    return snippet

def vault_search(parameters=None, player=None):
    parameters = parameters or {}
    query = str(parameters.get("query", "")).strip()
    folder = str(parameters.get("folder", "")).strip()

    if not VAULT_PATH.exists():
        return f"Vault not found: {VAULT_PATH}"

    search_root = VAULT_PATH
    if folder:
        candidate = (VAULT_PATH / folder).resolve()
        try:
            candidate.relative_to(VAULT_PATH.resolve())
            if candidate.exists() and candidate.is_dir():
                search_root = candidate
        except Exception:
            return "Invalid folder. Search cancelled."

    files = list(search_root.rglob("*.md"))
    if not files:
        return f"No markdown files found in {search_root}"

    results = []
    for path in files:
        text = _safe_text(path)
        rel = path.relative_to(VAULT_PATH)

        if not query:
            score = 1
        else:
            q = query.lower()
            haystack = f"{rel} {text}".lower()
            score = haystack.count(q)
            for token in q.split():
                if len(token) >= 3:
                    score += haystack.count(token)

        if score > 0:
            results.append({
                "score": score,
                "path": str(rel),
                "snippet": _make_snippet(text, query),
            })

    results.sort(key=lambda r: r["score"], reverse=True)
    results = results[:MAX_RESULTS]

    if not results:
        return f"No vault matches found for: {query}"

    lines = [f"Vault search results for: {query or '[all markdown notes]'}"]
    for i, item in enumerate(results, start=1):
        lines.append("")
        lines.append(f"{i}. {item['path']} | score {item['score']}")
        if item["snippet"]:
            lines.append(f"   {item['snippet']}")

    return "\n".join(lines)
