import os
import threading
import webview
from pathlib import Path
from brain.brain_data import BrainAPI, BrainWatcher, get_graph_data


class AppAPI(BrainAPI):
    def set_win(self, win):
        self._win = win

    def minimize_window(self):
        self._win.minimize()

    def maximize_window(self):
        self._win.maximize()

    def restore_window(self):
        self._win.restore()

    def close_window(self):
        self._win.destroy()
        threading.Timer(0.4, lambda: os._exit(0)).start()


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

webview.start(on_started)
