from pathlib import Path
import json

VAULT = Path(r"C:\Werkules\vault")

GRAPH_FILE = VAULT / "System" / "vault_graph.json"

def vault_graph_tool(parameters=None, player=None):

    parameters = parameters or {}

    mode = str(parameters.get("mode", "hubs")).lower()

    graph = json.loads(
        GRAPH_FILE.read_text(encoding="utf-8")
    )

    if mode == "hubs":

        lines = ["Hub Notes"]

        for item in graph["hub_notes"]:
            lines.append(
                f'{item["note"]} ({item["inbound_links"]})'
            )

        return "\n".join(lines)

    if mode == "backlinks":

        note = parameters.get("note", "")

        backlinks = graph.get("backlinks", {})

        if note not in backlinks:
            return f"No backlinks found for: {note}"

        lines = [f"Backlinks for {note}"]

        lines.extend(backlinks[note])

        return "\n".join(lines)

    return "Unknown graph mode."
