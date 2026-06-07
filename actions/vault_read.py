from pathlib import Path

VAULT_PATH = Path(r"C:\Jarvis_local_Comp\Jarvis_Brain\Vault")
MAX_READ_CHARS = 12000

def _resolve_vault_path(note_path: str) -> Path | None:
    if not note_path:
        return None

    note_path = note_path.strip().strip('"').strip("'")
    note_path = note_path.replace("/", "\\")

    candidate = (VAULT_PATH / note_path).resolve()

    try:
        candidate.relative_to(VAULT_PATH.resolve())
    except Exception:
        return None

    if candidate.exists() and candidate.is_file() and candidate.suffix.lower() == ".md":
        return candidate

    if not note_path.lower().endswith(".md"):
        candidate_md = (VAULT_PATH / (note_path + ".md")).resolve()
        try:
            candidate_md.relative_to(VAULT_PATH.resolve())
        except Exception:
            return None
        if candidate_md.exists() and candidate_md.is_file():
            return candidate_md

    return None

def vault_read(parameters=None, player=None):
    parameters = parameters or {}

    note_path = str(parameters.get("path", "")).strip()
    if not note_path:
        note_path = str(parameters.get("note_path", "")).strip()

    if not VAULT_PATH.exists():
        return f"Vault not found: {VAULT_PATH}"

    resolved = _resolve_vault_path(note_path)
    if not resolved:
        return (
            "Vault note not found or invalid path. "
            "Use a relative vault path such as System\\MISSION.md."
        )

    try:
        text = resolved.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"Could not read vault note: {e}"

    rel = resolved.relative_to(VAULT_PATH)

    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS].rstrip() + "\n\n[TRUNCATED: note is longer than read limit]"

    return f"Vault note: {rel}\n\n{text}"
