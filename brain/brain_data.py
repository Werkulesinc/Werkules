import json
import re
import threading
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Werkules")
APP_ROOT     = Path(r"C:\Werkules\app")
VAULT_ROOT   = Path(r"C:\Werkules\vault")

SKIP_DIRS = {"backups", ".venv", ".git", "__pycache__", "node_modules"}

SEMANTIC_THRESHOLD = 0.75  # minimum cosine similarity to draw a semantic link
SEMANTIC_TOP_N     = 3     # max semantic links kept per file

_IMPORT_RE   = re.compile(r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:[|#][^\]]*)?\]\]")


def _skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def _node_id(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


def _locked(path: Path) -> bool:
    try:
        path.relative_to(VAULT_ROOT)
        if path.suffix.lower() == ".md":
            return False
    except ValueError:
        pass
    return True


def build_nodes() -> list:
    nodes = []
    for f in sorted(PROJECT_ROOT.rglob("*")):
        if f.is_dir() or _skip(f):
            continue
        nodes.append({
            "id":     _node_id(f),
            "name":   f.name,
            "folder": f.parent.name,
            "type":   f.suffix.lower().lstrip(".") or "file",
            "path":   str(f),
            "locked": _locked(f),
        })
    return nodes


def _py_module_map(nodes: list) -> dict:
    m = {}
    for n in nodes:
        if n["type"] != "py":
            continue
        p = Path(n["path"])
        try:
            rel = p.relative_to(APP_ROOT)
        except ValueError:
            continue
        parts = list(rel.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            m[".".join(parts)] = n["id"]
        if len(rel.parts) == 1:
            m[rel.stem] = n["id"]
    return m


def build_links(nodes: list) -> list:
    links = []
    seen  = set()
    mmap  = _py_module_map(nodes)

    for node in nodes:
        if node["type"] != "py":
            continue
        try:
            text = Path(node["path"]).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in _IMPORT_RE.finditer(text):
            mod = m.group(1) or m.group(2)
            if not mod:
                continue
            target = mmap.get(mod)
            if not target or target == node["id"]:
                continue
            key = (node["id"], target)
            if key not in seen:
                seen.add(key)
                links.append({"source": node["id"], "target": target, "type": "import"})

    vault_ids = {
        Path(n["path"]).stem: n["id"]
        for n in nodes
        if not n["locked"] and n["type"] == "md"
    }
    for node in nodes:
        if node["locked"] or node["type"] != "md":
            continue
        try:
            text = Path(node["path"]).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in _WIKILINK_RE.finditer(text):
            target = vault_ids.get(m.group(1).strip())
            if not target or target == node["id"]:
                continue
            key = (node["id"], target)
            if key not in seen:
                seen.add(key)
                links.append({"source": node["id"], "target": target, "type": "wikilink"})

    return links


def _cosine(a: list, b: list) -> float:
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na  = sum(x * x for x in a) ** 0.5
    nb  = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def build_semantic_links(nodes: list) -> list:
    try:
        cache_path = Path(__file__).parent / "embeddings_cache.json"
        if not cache_path.exists():
            return []
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[semantic] cache unreadable: {e}")
            return []

        vectors: dict[str, list] = {}
        ref_len: int | None = None
        for nid, entry in cache.items():
            vec = entry.get("vector") if isinstance(entry, dict) else None
            if not isinstance(vec, list) or len(vec) == 0:
                print(f"[semantic] skip {nid}: missing or empty vector "
                      f"(likely rate-limited during embedding and never retried)")
                continue
            if not all(isinstance(v, (int, float)) for v in vec[:8]):
                print(f"[semantic] skip {nid}: non-numeric values in vector")
                continue
            if ref_len is None:
                ref_len = len(vec)
            elif len(vec) != ref_len:
                print(f"[semantic] skip {nid}: vector length {len(vec)} != {ref_len} "
                      f"(model changed since last embed — re-run test_embeddings.py)")
                continue
            vectors[nid] = vec

        if len(vectors) < 2:
            return []

        node_ids = [n["id"] for n in nodes if n["id"] in vectors]
        seen  = set()
        links = []

        for i, src in enumerate(node_ids):
            vec_a = vectors[src]
            sims  = []
            for j, tgt in enumerate(node_ids):
                if i == j:
                    continue
                try:
                    sim = _cosine(vec_a, vectors[tgt])
                except Exception as e:
                    print(f"[semantic] cosine error {src} ↔ {tgt}: {e}")
                    continue
                if sim >= SEMANTIC_THRESHOLD:
                    sims.append((sim, tgt))
            sims.sort(reverse=True)
            for _, tgt in sims[:SEMANTIC_TOP_N]:
                key = tuple(sorted([src, tgt]))
                if key not in seen:
                    seen.add(key)
                    links.append({"source": src, "target": tgt, "type": "semantic"})

        return links

    except Exception as e:
        print(f"[semantic] unexpected error — returning no semantic links: {e}")
        return []


def get_graph_data() -> dict:
    nodes = build_nodes()
    links = build_links(nodes)
    links += build_semantic_links(nodes)
    return {"nodes": nodes, "links": links}


class BrainAPI:
    def get_graph(self):
        return get_graph_data()

    def read_file(self, path: str):
        p = Path(path)
        try:
            p.relative_to(VAULT_ROOT)
        except ValueError:
            return {"error": "Access denied — only vault notes are readable"}
        if not p.exists() or not p.is_file():
            return {"error": "File not found"}
        try:
            return {"content": p.read_text(encoding="utf-8", errors="ignore")}
        except Exception as e:
            return {"error": str(e)}


class BrainWatcher:
    def __init__(self, window):
        self._window   = window
        self._observer = None
        self._timer    = None
        self._lock     = threading.Lock()

    def start(self):
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        watcher = self

        class _Handler(FileSystemEventHandler):
            def on_any_event(self, event):
                if event.is_directory:
                    return
                p = Path(getattr(event, "src_path", "") or "")
                if any(part in SKIP_DIRS for part in p.parts):
                    return
                watcher._schedule_push()

        self._observer = Observer()
        self._observer.schedule(_Handler(), str(PROJECT_ROOT), recursive=True)
        self._observer.daemon = True
        self._observer.start()

    def _schedule_push(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(0.6, self._push)
            self._timer.daemon = True
            self._timer.start()

    def _push(self):
        try:
            data   = get_graph_data()
            js_arg = json.dumps(data)
            self._window.evaluate_js(
                f"window.werkulesUpdate && window.werkulesUpdate({js_arg})"
            )
        except Exception:
            pass

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()
