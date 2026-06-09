import json
from pathlib import Path

_APP_ROOT    = Path(__file__).resolve().parent.parent
_API_CONFIG  = _APP_ROOT / "config" / "api_keys.json"
_VAULT_ROOT  = Path(r"C:\Werkules\vault")
_PROJ_ROOT   = Path(r"C:\Werkules")
_CACHE_PATH  = Path(__file__).parent / "embeddings_cache.json"
_EMBED_MODEL = "gemini-embedding-2"
_TEXT_LIMIT  = 10_000  # chars; embedding-004 has a ~2048-token input cap


def _get_api_key() -> str:
    return json.loads(_API_CONFIG.read_text(encoding="utf-8"))["gemini_api_key"]


def _load_cache() -> dict:
    if _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_cache(cache: dict) -> None:
    _CACHE_PATH.write_text(
        json.dumps(cache, separators=(",", ":")),
        encoding="utf-8",
    )


def _node_id(path: Path) -> str:
    return str(path.relative_to(_PROJ_ROOT)).replace("\\", "/")


def get_vault_embeddings() -> tuple[dict[str, list[float]], dict[str, int]]:
    """
    Returns (embeddings, stats).
      embeddings: {node_id -> float-vector} for every .md file under the vault.
      stats: {"fresh": n, "cached": n}
    Vectors are loaded from disk when path + mtime are unchanged.
    Only new or modified files hit the Gemini API.
    """
    cache  = _load_cache()
    result: dict[str, list[float]] = {}
    fresh  = 0
    cached = 0

    vault_files = sorted(f for f in _VAULT_ROOT.rglob("*.md") if f.is_file())

    if not vault_files:
        return result, {"fresh": 0, "cached": 0}

    from google import genai
    client = genai.Client(api_key=_get_api_key())

    for path in vault_files:
        node_id = _node_id(path)
        mtime   = path.stat().st_mtime
        entry   = cache.get(node_id)

        if entry and abs(entry.get("mtime", 0) - mtime) < 0.01:
            result[node_id] = entry["vector"]
            cached += 1
            continue

        try:
            text   = path.read_text(encoding="utf-8", errors="ignore")
            resp   = client.models.embed_content(
                model=_EMBED_MODEL,
                contents=[text[:_TEXT_LIMIT]],
            )
            vector = resp.embeddings[0].values
            cache[node_id]  = {"mtime": mtime, "vector": vector}
            result[node_id] = vector
            fresh += 1
        except Exception as e:
            print(f"[embeddings] skip {node_id}: {e}")

    _save_cache(cache)
    return result, {"fresh": fresh, "cached": cached}
