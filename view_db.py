"""View all data stored in the configured Qdrant collection."""
from pathlib import Path
import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "jira_copilot")

c = QdrantClient(url=QDRANT_URL)
points, _ = c.scroll(
    collection_name=QDRANT_COLLECTION,
    limit=20,
    with_payload=True,
    with_vectors=False,
)

print("=" * 70)
print(f"  QDRANT URL: {QDRANT_URL}")
print(f"  QDRANT COLLECTION: {QDRANT_COLLECTION}  |  Total chunks: {len(points)}")
print("=" * 70)

for i, point in enumerate(points, 1):
    meta = point.payload.get("metadata", point.payload)
    content = point.payload.get("page_content", "")
    preview = content[:200].replace("\n", " ")

    print(f"\n--- Chunk {i} (ID: {str(point.id)[:12]}...) ---")
    print(f"  Source:   {meta.get('source_filename', '?')}")
    print(f"  Type:     {meta.get('document_type', '?')}")
    print(f"  Project:  {meta.get('project', '?')}")
    print(f"  Chars:    {meta.get('char_count', '?')}")
    print(f"  Ingested: {meta.get('ingestion_date', '?')}")
    print(f"  Preview:  {preview}...")

print("\n" + "=" * 70)
