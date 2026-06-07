import json
import platform
from datetime import datetime
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "memory" / "environment_state.json"

def environment_scanner(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:

    data = {
        "scan_time": datetime.now().isoformat(),
        "computer": {
            "hostname": platform.node(),
            "os": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": psutil.cpu_count(logical=True) if psutil else None,
            "memory_gb": round(
                psutil.virtual_memory().total / (1024**3), 2
            ) if psutil else None,
        },
        "drives": [],
    }

    if psutil:
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                data["drives"].append({
                    "device": part.device,
                    "mount": part.mountpoint,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                })
            except Exception:
                pass

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return f"Environment scan completed. Saved to {OUTPUT_FILE}"
