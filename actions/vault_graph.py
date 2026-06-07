from pathlib import Path
import json

VAULT = Path(r"C:\Jarvis_local_Comp\Jarvis_Brain\Vault")

INDEX_FILE = VAULT / "System" / "vault_index.json"
OUTPUT_FILE = VAULT / "System" / "vault_graph.json"

def main():

    data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))

    backlinks = {}
    inbound_counts = {}

    for note in data["notes"]:
        source = Path(note["path"]).stem

        for target in note["links"]:

            backlinks.setdefault(target, []).append(source)

            inbound_counts[target] = inbound_counts.get(target, 0) + 1

    hub_notes = sorted(
        inbound_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )

    graph = {
        "hub_notes": [
            {
                "note": note,
                "inbound_links": count
            }
            for note, count in hub_notes
        ],
        "backlinks": backlinks
    }

    OUTPUT_FILE.write_text(
        json.dumps(graph, indent=2),
        encoding="utf-8"
    )

    print("\nHub Notes\n")

    for note, count in hub_notes:
        print(f"{note:<30} {count}")

    print(f"\nSaved: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
