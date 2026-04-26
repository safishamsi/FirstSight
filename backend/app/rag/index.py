from __future__ import annotations

import pickle
from collections.abc import Callable
from pathlib import Path

import faiss
import numpy as np

from . import Node

_INDEX_FILE = "faiss.index"
_IDMAP_FILE = "id_map.pkl"

_EMBEDDABLE_TYPES = {"text_chunk", "table", "table_row", "section", "entity"}
_EMBED_BATCH_SIZE = 100


def _normalise(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return vecs / norms


class FaissIndex:
    def __init__(
        self,
        index: faiss.IndexFlatIP,
        id_map: dict[int, str],
    ) -> None:
        self._index = index
        self._id_map = id_map

    @classmethod
    def build(
        cls,
        nodes: list[Node],
        embed_fn: Callable[[list[str]], list[list[float]]],
    ) -> "FaissIndex":
        embeddable = [n for n in nodes if n.type in _EMBEDDABLE_TYPES]

        all_vecs: list[list[float]] = []
        for i in range(0, len(embeddable), _EMBED_BATCH_SIZE):
            batch = embeddable[i : i + _EMBED_BATCH_SIZE]
            texts = [n.embed_text for n in batch]
            vecs = embed_fn(texts)
            all_vecs.extend(vecs)

        dim = len(all_vecs[0]) if all_vecs else 768
        matrix = np.array(all_vecs, dtype=np.float32)
        matrix = _normalise(matrix)

        index = faiss.IndexFlatIP(dim)
        index.add(matrix)

        id_map: dict[int, str] = {i: n.id for i, n in enumerate(embeddable)}

        return cls(index, id_map)

    def save(self, directory: str) -> None:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(path / _INDEX_FILE))
        with open(path / _IDMAP_FILE, "wb") as f:
            pickle.dump(self._id_map, f, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load(cls, directory: str) -> "FaissIndex":
        path = Path(directory)
        index = faiss.read_index(str(path / _INDEX_FILE))
        with open(path / _IDMAP_FILE, "rb") as f:
            id_map: dict[int, str] = pickle.load(f)
        return cls(index, id_map)

    def search(
        self,
        query_vec: np.ndarray,
        k: int,
    ) -> list[tuple[str, float]]:
        """Return list of (node_id, cosine_score) for the top-k nearest nodes."""
        vec = _normalise(query_vec.reshape(1, -1).astype(np.float32))
        k = min(k, self._index.ntotal)
        scores, indices = self._index.search(vec, k)
        results: list[tuple[str, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            node_id = self._id_map.get(int(idx))
            if node_id is not None:
                results.append((node_id, float(score)))
        return results

    def total(self) -> int:
        return self._index.ntotal
