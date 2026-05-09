"""
Pinecone setup — create the index used by this project if it doesn't exist.

Run once after first cloning, or any time the index needs to be recreated:

    python -m uv run scripts/pinecone_setup.py

Idempotent: if the index already exists, prints its config and exits without
making changes.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

from pinecone import Pinecone, ServerlessSpec  # noqa: E402


# These match our embedding model (text-embedding-3-small).
INDEX_DIMENSION = 1536
INDEX_METRIC = "cosine"
CLOUD = "aws"
REGION = "us-east-1"


def main() -> int:
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME")
    if not api_key or not index_name:
        print("FAIL: PINECONE_API_KEY and PINECONE_INDEX_NAME must be set in .env")
        return 1

    pc = Pinecone(api_key=api_key)

    existing = [idx["name"] for idx in pc.list_indexes()]
    if index_name in existing:
        info = pc.describe_index(index_name)
        print(f"Index {index_name!r} already exists. Nothing to do.")
        print(f"  dimension: {info.dimension}")
        print(f"  metric:    {info.metric}")
        print(f"  host:      {info.host}")
        return 0

    print(f"Creating index {index_name!r} ...")
    print(f"  dimension={INDEX_DIMENSION}, metric={INDEX_METRIC}, cloud={CLOUD}/{REGION}")
    pc.create_index(
        name=index_name,
        dimension=INDEX_DIMENSION,
        metric=INDEX_METRIC,
        spec=ServerlessSpec(cloud=CLOUD, region=REGION),
    )
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
