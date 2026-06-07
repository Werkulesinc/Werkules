# Werkules / Jarvis — Project Reference

This file is the authoritative reference for Claude Code sessions working on this project.
Read this before reading any source file. It prevents re-discovering things that are already known.

---

## What This Project Is

**Werkules** is a personal AI assistant platform. The AI is named **Jarvis**. The platform is owned
by Netwerk Inc / Werkules Inc. Website: werkules.com.

The core experience is a real-time voice conversation: you speak, Jarvis hears you, thinks, and
speaks back — and can control your computer, browse the web, manage files, write code, read your
Obsidian vault, and run multi-step autonomous tasks.

The underlying AI is **Google Gemini Live** (native audio streaming over WebSocket). This is not a
chatbot — it is a continuous audio session with bidirectional audio and function-calling.

---

## Folder Structure

```
C:\Werkules\
  app\                 # all application code (this repo)
  vault\               # Obsidian vault and brain files (move from Jarvis_Brain\Vault)
  logs\                # log files
  backups\             # backups (empty)
```

## Repository Layout

```
C:\Werkules\app\
  main.py              # entry point — audio pipeline + tool dispatch
  ui.py                # entire PyQt6 interface (~1,500 lines)
  setup.py             # one-shot install (pip + playwright)
  requirements.txt     # all Python dependencies
  werkules_launcher.bat  # launch with pythonw (no console window)
  werkules.ico         # app icon
  face.png             # avatar shown in HUD (optional — fallback orb if missing)

  core/
    prompt.txt         # Jarvis personality + behavior rules injected every session

  config/
    __init__.py        # get_os(), is_windows(), is_mac(), is_linux() helpers
    api_keys.json      # runtime config — NOT in git (gitignored)

  memory/
    __init__.py        # package marker only
    memory_manager.py  # long_term.json CRUD + prompt formatting
    config_manager.py  # reads/writes api_keys.json (overlaps with config/__init__.py)

  agent/
    task_queue.py      # priority queue for background multi-step tasks
    planner.py         # Gemini call: goal → JSON step plan
    executor.py        # walks plan, calls tools, injects context between steps
    error_handler.py   # Gemini call: failed step → retry/skip/replan/abort decision

  actions/             # one file per tool Jarvis can call (24 files)
    browser_control.py
    code_helper.py
    computer_control.py
    computer_settings.py
    desktop.py
    dev_agent.py
    environment_scanner.py
    file_controller.py
    file_processor.py
    flight_finder.py
    game_updater.py
    open_app.py
    reminder.py
    screen_processor.py
    send_message.py
    vault_graph.py
    vault_graph_query.py
    vault_graph_tool.py
    vault_index.py
    vault_read.py
    vault_search.py
    weather_report.py
    web_search.py
    youtube_video.py
```

---

## Architecture: How Everything Connects

```
face.png + core/prompt.txt
        |
        v
main.py  ←→  Gemini Live (WebSocket, bidirectional audio)
  |               |
  |           Gemini decides to call a tool
  |               |
  |    JarvisLive._execute_tool(fc)
  |               |
  |    ┌──────────┴──────────────────────────┐
  |    │  simple tool → actions/<tool>.py     │
  |    │  agent_task  → agent/task_queue.py   │
  |    │    → planner → executor → tools      │
  |    └───────────────────────────────────────┘
  |
  v
ui.py  (JarvisUI)
  ← receives state/log updates via Qt signals (thread-safe)
  ← HUD animation, sys metrics, file drop zone, text input, mute button
```

### Session Startup Sequence

1. `main()` in `main.py` creates `JarvisUI("face.png")`.
2. A background thread waits for the API key (blocks if not yet configured).
3. If `config/api_keys.json` is missing or invalid, the UI shows a setup overlay.
4. Once configured, `JarvisLive.run()` starts the async loop.
5. `_build_config()` loads memory from `memory/long_term.json` + `core/prompt.txt`,
   injects them into the Gemini Live session config as the system instruction.
6. Four async tasks run concurrently: `_send_realtime`, `_listen_audio`, `_receive_audio`,
   `_play_audio`.
7. On connection: UI state → LISTENING, log → "SYS: Werkules online - Jarvis ready."
8. If the session drops, it reconnects automatically after 3 seconds.

---

## The Gemini Live Connection

- **Model:** `models/gemini-2.5-flash-native-audio-preview-12-2025`
- **SDK:** `google-genai` (the newer `from google import genai` import style)
- **Audio in:** 16 kHz mono PCM, chunk size 1024
- **Audio out:** 24 kHz mono PCM, chunk size 1024
- **Response modality:** AUDIO (not text — Gemini speaks back)
- **Transcription:** both input and output transcription enabled; transcripts shown in the log
- **Voice:** "Charon"
- **Session resumption:** enabled via `types.SessionResumptionConfig()`
- **Tools:** all 23 tool declarations are passed as `function_declarations` in `LiveConnectConfig`

**Important:** The agent system (`agent/`) uses the *older* `google.generativeai` SDK
(`import google.generativeai as genai`). These are two different SDK clients. Don't confuse them.
The newer `from google import genai` client is used in `main.py`, `web_search.py`, and
`screen_processor.py`. The older client is used in `agent/`, `code_helper.py`, `dev_agent.py`,
`computer_settings.py`, and `environment_scanner.py`.

---

## Tool Dispatch Pattern

When Gemini decides to call a tool, `JarvisLive._execute_tool(fc)` in `main.py` handles it.

The dispatch is a large `if/elif` chain (lines 671–800 of `main.py`). Every new tool must be
added in three places:

1. **`TOOL_DECLARATIONS`** list in `main.py` — the JSON schema Gemini sees
2. **`_execute_tool()`** — the `elif name == "your_tool"` branch that calls the action
3. **Import at top of `main.py`** — `from actions.your_tool import your_function`

The executor returns a `types.FunctionResponse` to Gemini, which then synthesizes a spoken reply.

---

## Action File Contract

Every file in `actions/` exports one callable that Jarvis dispatches to.
The standard signature is:

```python
def your_action(
    parameters: dict,
    player=None,          # JarvisUI instance, or None when called from agent/executor
    response=None,        # legacy, mostly unused
    session_memory=None,  # legacy, mostly unused
    speak=None,           # callable for agent-context speech, or None
) -> str:
```

Rules:
- **Always return a string.** Gemini uses it to formulate a spoken response.
- **Log to UI** with `player.write_log("text")` if `player` is not None.
- **Set UI state** with `player.set_state("THINKING")` if `player` is not None.
- **Never crash silently.** Catch exceptions and return an error string; `main.py` also wraps
  calls in try/except and calls `speak_error()`.
- **player can be None** — the agent executor calls actions with `player=None`. All `if player:`
  guards are mandatory.
- **Read the API key locally.** Every action that calls Gemini reads `config/api_keys.json`
  itself. There is no centralized API client. This is an inconsistency — do not make it worse
  by introducing yet another pattern. If refactoring, centralize then.

---

## Configuration File

`config/api_keys.json` — gitignored, created by the setup overlay on first run.

```json
{
  "gemini_api_key": "AIza...",
  "os_system": "windows"
}
```

- `os_system` is one of: `"windows"`, `"mac"`, `"linux"`
- Read via `config/__init__.py` helpers: `is_windows()`, `is_mac()`, `is_linux()`
- Also read directly in many action files: `json.load(open("config/api_keys.json"))`
- `memory/config_manager.py` provides the same read/write functions — it overlaps with
  `config/__init__.py`. Both exist; don't add a third pattern.

---

## Memory System

**File:** `memory/long_term.json` (gitignored — listed in `.gitignore`)

Six categories, each a dict of `key → {value, updated}`:

```
identity      — name, age, city, job, language, etc.
preferences   — favorite food, music, colors, etc.
projects      — active projects and goals
relationships — people, family, friends
wishes        — future plans, things to buy
notes         — anything else
```

**Key functions in `memory/memory_manager.py`:**

- `load_memory()` — reads file, returns dict with all six keys guaranteed
- `save_memory(memory)` — trims oldest entries if >2,200 chars, then writes
- `update_memory({category: {key: {value: ...}}})` — load → diff → save if changed
- `format_memory_for_prompt(memory)` — formats as natural-language text for system prompt
- `forget(key, category)` — removes one entry

**Limits:**
- Each value is truncated at 380 characters
- Total memory JSON is capped at 2,200 characters (oldest entries trimmed first)
- Memory is injected into every Gemini session as part of the system instruction

**Memory is only saved when the user explicitly asks.** `core/prompt.txt` enforces this.
Do not save silently. The `save_memory` tool declaration includes this rule.

---

## Agent System (Multi-Step Tasks)

Triggered when Gemini calls the `agent_task` tool with a natural-language `goal`.

```
task_queue.submit(goal)
    → TaskQueue._worker_loop() (background thread)
    → AgentExecutor.execute(goal)
        → create_plan(goal)            [planner.py — Gemini call]
        → for each step:
            _call_tool(tool, params)   [executor.py — calls actions/]
            on failure: analyze_error(step, error)  [error_handler.py — Gemini call]
                → RETRY: sleep 2s, retry
                → SKIP: mark done, continue
                → REPLAN: generate_fix() → call fixed step
                → ABORT: return error message
        → _summarize(goal, steps)      [Gemini call]
```

**Planner model:** `gemini-2.5-flash-lite` (fast, cheap — plan generation)
**Error handler model:** `gemini-2.5-flash-lite` (fast — triage decision)
**Fix generation model:** `gemini-2.0-flash`
**Summary model:** `gemini-2.5-flash-lite`
**Executor fallback:** if tool is unknown, generates Python code via Gemini, writes to temp
file, runs with subprocess, captures output.

**Max replan attempts:** 2. After that, task fails with message.
**Max concurrent tasks:** 1 (TaskQueue is initialized with `max_concurrent=1`).
**Task queue is a singleton** — `get_queue()` starts it on first call.

The agent uses the **older** `google.generativeai` SDK. See SDK note above.

---

## UI Architecture

**File:** `ui.py` — ~1,500 lines, pure PyQt6. No business logic. No Gemini calls.

**Key classes:**

- `JarvisUI` — public interface used by `main.py`. Exposes: `set_state()`, `write_log()`,
  `wait_for_api_key()`, `muted`, `current_file`, `on_text_command`, `start_speaking()`,
  `stop_speaking()`.
- `MainWindow(QMainWindow)` — the actual window. Contains all sub-widgets.
- `HudCanvas(QWidget)` — the animated central face display. Runs at 60fps (16ms timer).
  States: idle (slow pulse), speaking (fast pulse + particles), muted (red/pink).
- `LogWidget(QTextEdit)` — the activity log. Messages are typed out character-by-character
  for aesthetic effect. Thread-safe via `_sig` pyqtSignal.
- `MetricBar(QWidget)` — a single CPU/MEM/NET/GPU/TMP progress bar. Painted custom.
- `_SysMetrics` — background thread polling psutil every 1.5s. GPU via nvidia-smi/rocm-smi.
- `FileDropZone` — drag-and-drop file upload area. Emits `file_selected` signal.
- `SetupOverlay` — first-run overlay for API key + OS selection.

**Thread safety:** `main.py` runs Gemini I/O on a background asyncio loop. UI updates must go
through Qt signals. `MainWindow` has two signals:
- `_log_sig = pyqtSignal(str)` — connected to `_log.append_log()`
- `_state_sig = pyqtSignal(str)` — connected to `_apply_state()`

Call `self.ui.write_log(text)` and `self.ui.set_state(state)` from any thread — they emit
signals internally. Never call PyQt6 widget methods directly from a non-Qt thread.

**Valid state strings:** `"LISTENING"`, `"THINKING"`, `"PROCESSING"`, `"SPEAKING"`, `"MUTED"`,
`"INITIALISING"` (any other string is displayed as-is in the HUD).

**HUD face:** loads `face.png` from the project root. If missing, draws an animated orb with
"J.A.R.V.I.S" text. File must be a square-ish image (cropped to circle).

---

## Vault System

The Obsidian vault is Jarvis's external long-term knowledge base. All vault access is
**read-only** — Jarvis never writes to the vault.

### Hardcoded Vault Path

**This path is hardcoded in 6 files:**

```python
VAULT_PATH = Path(r"C:\Werkules\vault")
```

Files that contain it: `vault_search.py`, `vault_read.py`, `vault_graph.py`,
`vault_graph_query.py`, `vault_graph_tool.py`, `vault_index.py`.

If the vault moves, update all six. Consider extracting to config if refactoring.

**Note:** The physical vault content still needs to be moved from
`C:\Jarvis_local_Comp\Jarvis_Brain\Vault` → `C:\Werkules\vault` if not already done.

### What Each Vault File Does

| File | Type | Purpose |
|---|---|---|
| `vault_search.py` | **Live tool** | Keyword search across all .md files. Scores by exact match + word-split tokens. Returns top 8 results with 600-char snippets. Supports `folder` param to scope search. |
| `vault_read.py` | **Live tool** | Reads one note by relative path. Resolves `.md` extension. Truncates at 12,000 chars. Path-traversal safe (checks file stays inside vault root). |
| `vault_graph_tool.py` | **Live tool** | Reads pre-built `vault_graph.json`. Two modes: `hubs` (top linked notes) or `backlinks` (what links to a given note). Returns stale data if graph not rebuilt. |
| `vault_index.py` | **Offline script** | Scans all .md files, extracts `[[wikilinks]]` and `#tags`, saves to `System/vault_index.json`. Run manually to rebuild. |
| `vault_graph.py` | **Offline script** | Reads `vault_index.json`, computes backlink counts + hub notes, saves to `System/vault_graph.json`. Run after `vault_index.py`. |
| `vault_graph_query.py` | **Dev CLI** | Terminal query tool for developers. Not called by Jarvis. |

### How to Rebuild the Graph

```bash
python actions/vault_index.py    # step 1
python actions/vault_graph.py    # step 2
```

The graph is static until rebuilt. `vault_graph_tool.py` reads stale data without warning.

### Vault Tool Declarations in main.py

Three vault tools are registered with Gemini:
- `vault_search` — search by query + optional folder
- `vault_read` — read by relative path (e.g. `System\MISSION.md`)
- `vault_graph_tool` — graph query (hubs or backlinks)

---

## File Controller Safety

`actions/file_controller.py` enforces a whitelist of allowed root paths:

```python
_SAFE_ROOTS = [
    Path.home(),
    Path(r"C:\Jarvis_local_Comp"),
    Path(r"C:\Jarvis_Brain"),
    Path(r"C:\Jarvis_Workspace"),
]
```

Any file operation targeting a path outside these roots is rejected. If Jarvis needs to
operate on a new location, add it to `_SAFE_ROOTS`. Do not remove this check.

---

## Key Dependencies

```
google-genai           # newer SDK — main.py, web_search, screen_processor
google-generativeai    # older SDK — agent/, code_helper, dev_agent, computer_settings
sounddevice            # mic input + speaker output
PyQt6                  # entire UI
playwright             # browser_control (requires: playwright install)
pyautogui              # computer_control, send_message, computer_settings, youtube_video
psutil                 # system metrics in ui.py + environment_scanner
pillow                 # image handling in file_processor + HUD face loading
mss                    # screen capture in screen_processor
opencv-python (cv2)    # webcam access in screen_processor
pyperclip              # clipboard in computer_control, computer_settings
send2trash             # safe delete in file_controller
youtube-transcript-api # YouTube transcript fetching in youtube_video
python-pptx            # PowerPoint processing in file_processor
```

Install everything: `pip install -r requirements.txt && playwright install`

---

## Coding Conventions

### General

- **No comments** unless the WHY is non-obvious. Avoid `# this function does X` —
  the function name does that. Comments are for hidden constraints, workarounds, invariants.
- **No docstrings** on functions. The signature and name should be self-documenting.
- **No type annotations required** but encouraged on public function signatures.
- **No trailing whitespace.** No blank lines at end of file beyond one.
- Line length: aim for 100 characters, not enforced strictly.

### Error Handling

- Only handle errors at system boundaries (user input, external APIs, file I/O).
- Don't wrap internal calls in try/except unless there's a specific recovery action.
- In action files: catch exceptions, log them, return an error string. Never let an action
  crash the main audio loop.
- In main.py `_execute_tool()`: outer try/except catches everything, calls `speak_error()`.

### Adding a New Tool

1. Create `actions/your_tool.py` with the standard function signature (see Action File Contract).
2. Add an import at the top of `main.py`.
3. Add a tool declaration to `TOOL_DECLARATIONS` in `main.py`.
4. Add an `elif name == "your_tool":` branch in `_execute_tool()`.
5. If the agent should also be able to use it: add it to `_call_tool()` in `agent/executor.py`
   and add it to the planner's available tools list in `agent/planner.py`.

### Adding a New Memory Category

Don't. The six categories in `memory_manager.py` cover all cases. Use `notes` for anything
that doesn't fit elsewhere.

### Modifying the System Prompt

Edit `core/prompt.txt`. Changes take effect on the next Gemini session reconnect (not
mid-session). The prompt is injected as part of `system_instruction` in `_build_config()`.
Memory and current date/time are prepended to the prompt automatically — don't add them
to the prompt file.

### UI Changes

- All UI code stays in `ui.py`. Don't add Qt imports or widget code to other files.
- To update the UI from a non-Qt thread: use `player.write_log()` or `player.set_state()`.
  These are thread-safe. Direct widget access from other threads will crash.
- The footer brand line is at `ui.py:1352`. The window title is at `ui.py:993`.

---

## What Not to Touch Without Understanding First

| File | Risk | Reason |
|---|---|---|
| `core/prompt.txt` | High | Changes Jarvis's entire personality and behavior. Test carefully. |
| `main.py` `TOOL_DECLARATIONS` | High | Malformed JSON schema breaks the Gemini session. |
| `main.py` `_build_config()` | High | Breaks session auth, audio config, or tool registration. |
| `memory/memory_manager.py` `_trim_to_limit()` | Medium | Silently deletes oldest memories if logic breaks. |
| `actions/file_controller.py` `_SAFE_ROOTS` | High | Removing the whitelist enables arbitrary file deletion. |
| `ui.py` `_step()` in `HudCanvas` | Low-Med | 60fps animation loop — performance-sensitive. |
| `agent/planner.py` `PLANNER_PROMPT` | Medium | Changes how all multi-step tasks are decomposed. |

---

## Known Inconsistencies (Do Not Make Worse)

1. **Two Gemini SDK clients.** `from google import genai` (new) and `import google.generativeai as genai` (old). They coexist in the same project. A future refactor should pick one — the new SDK (`google-genai`) is preferred.

2. **API key read in every action file.** There is no shared credential layer. Each action that calls Gemini opens `config/api_keys.json` itself. ~10 files do this identically. Centralize in a future refactor.

3. **`config_manager.py` and `config/__init__.py` overlap.** Both read `api_keys.json`. Both exist. Don't add a third.

4. **Vault path hardcoded in 6 files.** Should be read from config. Not a bug unless the vault moves. Currently points to `C:\Werkules\vault`.

---

## Branding

- **Platform name:** Werkules
- **AI assistant name:** Jarvis (full name J.A.R.V.I.S)
- **Owner:** Netwerk Inc / Werkules Inc
- **Website:** werkules.com
- **Attribution line** (bottom of README only): "Werkules is built on open-source foundations including Mark-XXXIX-OR by FatihMakes"
- The AI assistant is always called Jarvis — not Werkules. Werkules is the platform.
- Window title: `"Werkules"` (set in `ui.py:993`)
- Header badge: `"WERKULES"` (set in `ui.py:1138`)
- Startup log message: `"SYS: Werkules online - Jarvis ready."` (set in `main.py:956`)

---

## Environment

- **OS:** Windows 11 (primary). Cross-platform code exists but Windows is the test target.
- **Python:** 3.14 (venv at `C:\Werkules\app\.venv\`)
- **Project root:** `C:\Werkules\app\`
- **Vault:** `C:\Werkules\vault\`
- **Launcher:** `C:\Werkules\app\werkules_launcher.bat` (double-click to start, no console)
- **Config:** `config/api_keys.json` (gitignored)
- **Memory:** `memory/long_term.json` (gitignored)
- **Environment state:** `memory/environment_state.json` (gitignored)
- **Git remote:** github.com/Werkulesinc/Werkules
- **Branch:** main
