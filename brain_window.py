import os
import json
import asyncio
import threading
import ctypes
import ctypes.wintypes
import webview
from pathlib import Path
from brain.brain_data import BrainAPI, BrainWatcher, get_graph_data


class HeadlessUI:
    """Minimal JarvisUI-compatible interface for headless (no PyQt) operation."""

    def __init__(self):
        self._muted = True  # mic starts muted; brain mic button controls this
        self._on_text_command = None

    @property
    def muted(self) -> bool:
        return self._muted

    @muted.setter
    def muted(self, v: bool):
        self._muted = bool(v)

    @property
    def current_file(self):
        return None

    @property
    def on_text_command(self):
        return self._on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._on_text_command = cb

    def set_state(self, state: str):
        pass

    def write_log(self, text: str):
        pass

    def start_speaking(self):
        pass

    def stop_speaking(self):
        pass

    def wait_for_api_key(self):
        config = Path(__file__).parent / "config" / "api_keys.json"
        if not config.exists():
            raise RuntimeError(
                "config/api_keys.json missing — run main.py once to configure the API key"
            )
        data = json.loads(config.read_text())
        if not data.get("gemini_api_key"):
            raise RuntimeError("gemini_api_key missing in config/api_keys.json")


headless_ui = HeadlessUI()


def _work_area():
    rc = ctypes.wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rc), 0)
    return rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top


_restore_bounds = None


class AppAPI(BrainAPI):
    def set_win(self, win):
        self._win = win

    def minimize_window(self):
        self._win.minimize()

    def maximize_window(self):
        global _restore_bounds
        _restore_bounds = (self._win.x, self._win.y, self._win.width, self._win.height)
        x, y, w, h = _work_area()
        self._win.move(x, y)
        self._win.resize(w, h)

    def restore_window(self):
        global _restore_bounds
        if _restore_bounds:
            x, y, w, h = _restore_bounds
            self._win.move(x, y)
            self._win.resize(w, h)
        else:
            self._win.move(60, 60)
            self._win.resize(1280, 800)

    def close_window(self):
        self._win.destroy()
        threading.Timer(0.4, lambda: os._exit(0)).start()

    def get_bounds(self):
        return {"x": self._win.x, "y": self._win.y, "w": self._win.width, "h": self._win.height}

    def set_bounds(self, x: int, y: int, w: int, h: int):
        w, h = max(700, int(w)), max(500, int(h))
        self._win.move(int(x), int(y))
        self._win.resize(w, h)

    def toggle_mic(self):
        headless_ui.muted = not headless_ui.muted
        return not headless_ui.muted  # True = mic now active


def _start_engine():
    from main import JarvisLive
    try:
        headless_ui.wait_for_api_key()
    except RuntimeError as e:
        print(f"[BRAIN-ENGINE] ❌ {e}")
        return
    jarvis = JarvisLive(headless_ui)
    try:
        asyncio.run(jarvis.run())
    except KeyboardInterrupt:
        pass


HTML = (Path(__file__).parent / "brain" / "index.html").as_uri()
api  = AppAPI()

window = webview.create_window(
    "Werkules",
    url=HTML,
    js_api=api,
    maximized=True,
    frameless=True,
)

def on_started():
    api.set_win(window)
    data      = get_graph_data()
    locked    = sum(1 for n in data["nodes"] if     n["locked"])
    editable  = sum(1 for n in data["nodes"] if not n["locked"])
    n_imports = sum(1 for lk in data["links"] if lk["type"] == "import")
    n_wiki    = sum(1 for lk in data["links"] if lk["type"] == "wikilink")
    print(f"[brain] Nodes  : {len(data['nodes'])}  ({locked} locked, {editable} editable)")
    print(f"[brain] Links  : {len(data['links'])}  ({n_imports} imports, {n_wiki} wikilinks)")
    watcher = BrainWatcher(window)
    watcher.start()
    print("[brain] Watcher: live — watching C:\\Werkules for changes")


threading.Thread(target=_start_engine, daemon=True).start()
webview.start(on_started)
