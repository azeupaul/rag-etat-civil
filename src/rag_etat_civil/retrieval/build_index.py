"""Build the vector index of the law.

    make index

Reads data/processed/chunks.jsonl, embeds every chunk with the configured model and writes
the index in data/index/. The first run downloads the model (about 2.2 GB for the default one).
Run it again whenever the chunks or the embedding model change.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from rag_etat_civil.config import Settings
from rag_etat_civil.embeddings.base import Embedder
from rag_etat_civil.embeddings.registry import create_embedder
from rag_etat_civil.ingestion.build import load_chunks
from rag_etat_civil.ingestion.models import Chunk
from rag_etat_civil.retrieval.numpy_index import NumpyIndex


def build_index(chunks: Sequence[Chunk], embedder: Embedder) -> NumpyIndex:
    """Embed the chunks (their `indexed_text`, which includes the context) into an index."""
    vectors = embedder.embed_documents([chunk.indexed_text for chunk in chunks])
    return NumpyIndex([chunk.id for chunk in chunks], vectors, embedder.model_id)


def main() -> None:
    settings = Settings.from_env()
    chunks = load_chunks(settings.data_dir)
    embedder = create_embedder(settings)

    print(f"Embedding {len(chunks)} chunks with {embedder.model_id} (first run downloads it)...")
    started = time.perf_counter()
    index = build_index(chunks, embedder)
    index.save(settings.index_dir)
    elapsed = time.perf_counter() - started
    print(f"Index of {len(index)} vectors written to {settings.index_dir} in {elapsed:.1f} s")


if __name__ == "__main__":
    main()
