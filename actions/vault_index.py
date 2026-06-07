from pathlib import Path
import re
import json

VAULT = Path(r"C:\Werkules\vault")

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_\-]+)")

def main():
    notes_data = []

    notes = list(VAULT.rglob("*.md"))

    for note in notes:
        text = note.read_text(encoding="utf-8", errors="ignore")

        links = WIKILINK_RE.findall(text)
        tags = TAG_RE.findall(text)

        notes_data.append({
            "path": str(note.relative_to(VAULT)),
            "links": links,
            "tags": tags
        })

    output = {
        "note_count": len(notes_data),
        "notes": notes_data
    }

    output_path = VAULT / "System" / "vault_index.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Indexed {len(notes_data)} notes")
    print(f"Saved: {output_path}")

if __name__ == "__main__":
    main()
