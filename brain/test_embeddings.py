import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brain.embeddings import get_vault_embeddings

if __name__ == "__main__":
    print("Computing vault fingerprints...")
    embeddings, stats = get_vault_embeddings()
    print(f"Done: {stats['fresh']} fresh  |  {stats['cached']} from cache  |  {len(embeddings)} total")
    if embeddings:
        sample_id = next(iter(embeddings))
        dim = len(embeddings[sample_id])
        print(f"Sample — {sample_id}  ({dim}-dim vector)")
