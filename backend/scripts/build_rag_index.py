"""Build the JRCALC Graph RAG index from an EPUB file.

Usage:
    python -m scripts.build_rag_index \\
        --epub data/jrcalc-clinical-guidelines-2022.epub \\
        --out rag_index \\
        --gemini-api-key $GEMINI_API_KEY
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _build_embed_fn(api_key: str):
    import time
    from google import genai
    from google.genai import errors as genai_errors

    client = genai.Client(api_key=api_key)

    def embed(texts: list[str]) -> list[list[float]]:
        max_retries = 8
        delay = 10.0
        for attempt in range(max_retries):
            try:
                result = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=texts,
                )
                time.sleep(0.7)  # stay under 100 RPM free tier
                return [list(e.values) for e in result.embeddings]
            except genai_errors.ClientError as exc:
                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                    wait = delay * (2 ** attempt)
                    print(f"  Rate limited, waiting {wait:.0f}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("Embedding failed after max retries")

    return embed


def main() -> None:
    parser = argparse.ArgumentParser(description="Build JRCALC Graph RAG index")
    parser.add_argument("--epub", required=True, help="Path to JRCALC EPUB file")
    parser.add_argument("--out", required=True, help="Output directory for index artefacts")
    parser.add_argument("--gemini-api-key", required=True, help="Google Gemini API key")
    args = parser.parse_args()

    epub_path = Path(args.epub)
    if not epub_path.exists():
        print(f"ERROR: EPUB not found: {epub_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Imports after arg validation so --help works without heavy deps
    from app.rag.graph import ClinicalGraph
    from app.rag.index import FaissIndex
    from app.rag.ingest import load_epub

    print(f"Ingesting EPUB: {epub_path}")
    t0 = time.monotonic()
    nodes, edges = load_epub(str(epub_path))
    elapsed = time.monotonic() - t0
    print(f"  Ingestion done in {elapsed:.1f}s")

    node_type_counts: dict[str, int] = {}
    for n in nodes:
        node_type_counts[n.type] = node_type_counts.get(n.type, 0) + 1

    edge_type_counts: dict[str, int] = {}
    for e in edges:
        edge_type_counts[e.type] = edge_type_counts.get(e.type, 0) + 1

    print(f"  Nodes total: {len(nodes)}")
    for ntype, count in sorted(node_type_counts.items()):
        print(f"    {ntype}: {count}")
    print(f"  Edges total: {len(edges)}")
    for etype, count in sorted(edge_type_counts.items()):
        print(f"    {etype}: {count}")

    print("Building NetworkX graph...")
    t1 = time.monotonic()
    graph = ClinicalGraph.build(nodes, edges)
    graph.save(str(out_dir))
    print(f"  Graph saved in {time.monotonic() - t1:.1f}s → {out_dir}/graph.pkl")

    print("Building FAISS index (embedding via Google text-embedding-004)...")
    embed_fn = _build_embed_fn(args.gemini_api_key)
    t2 = time.monotonic()
    index = FaissIndex.build(nodes, embed_fn)
    index.save(str(out_dir))
    print(
        f"  FAISS index saved in {time.monotonic() - t2:.1f}s"
        f" → {out_dir}/faiss.index  ({index.total()} vectors)"
    )

    print(f"\nDone. Total time: {time.monotonic() - t0:.1f}s")
    print(f"Index directory: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
