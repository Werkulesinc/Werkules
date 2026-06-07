from pathlib import Path
import json
import sys

VAULT = Path(r"C:\Jarvis_local_Comp\Jarvis_Brain\Vault")

GRAPH_FILE = VAULT / "System" / "vault_graph.json"

def load_graph():
    return json.loads(GRAPH_FILE.read_text(encoding="utf-8"))

def show_hubs(graph):

    print("\nHub Notes\n")

    for item in graph["hub_notes"]:
        print(f'{item["note"]:<30} {item["inbound_links"]}')

def show_backlinks(graph, note_name):

    backlinks = graph.get("backlinks", {})

    if note_name not in backlinks:
        print(f"No backlinks found for: {note_name}")
        return

    print(f"\nBacklinks for {note_name}\n")

    for note in backlinks[note_name]:
        print(note)

def main():

    graph = load_graph()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python vault_graph_query.py hubs")
        print("  python vault_graph_query.py backlinks NOTE")
        return

    command = sys.argv[1].lower()

    if command == "hubs":

        show_hubs(graph)

    elif command == "backlinks":

        if len(sys.argv) < 3:
            print("Specify a note name.")
            return

        show_backlinks(graph, sys.argv[2])

    else:
        print("Unknown command")

if __name__ == "__main__":
    main()
