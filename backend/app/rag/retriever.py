from __future__ import annotations

from collections.abc import Callable

import numpy as np

from . import ScoredNode
from .graph import ClinicalGraph
from .index import FaissIndex

_SEED_K = 15
_HOP_DECAY: dict[str, float] = {
    "PART_OF": 0.8,
    "SIBLING": 0.7,
    "MENTIONED_IN": 0.6,
    "CROSS_REF": 0.5,
}
# Max MENTIONED_IN results per entity to avoid hub explosion
_MAX_ENTITY_MENTIONS = 20


def _normalise(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


class GraphRetriever:
    def __init__(
        self,
        graph: ClinicalGraph,
        index: FaissIndex,
        embed_fn: Callable[[list[str]], list[list[float]]],
        top_k: int = 6,
    ) -> None:
        self._graph = graph
        self._index = index
        self._embed_fn = embed_fn
        self._top_k = top_k

    def retrieve(self, query: str) -> list[ScoredNode]:
        query_vec = np.array(self._embed_fn([query])[0], dtype=np.float32)
        query_vec = _normalise(query_vec)

        seeds = self._index.search(query_vec, k=_SEED_K)

        # scored: node_id → (score, via)  — keeps max score per node
        scored: dict[str, tuple[float, str]] = {}

        def _add(node_id: str, score: float, via: str) -> None:
            existing = scored.get(node_id)
            if existing is None or score > existing[0]:
                scored[node_id] = (score, via)

        for node_id, seed_score in seeds:
            if self._graph.node(node_id) is None:
                continue
            _add(node_id, seed_score, "direct")

            # Parent context (depth 1)
            for parent_id, _ in self._graph.neighbors(node_id, ["PART_OF"], depth=1):
                _add(parent_id, seed_score * _HOP_DECAY["PART_OF"], "PART_OF")

            # Sibling chunks in same section (depth 1)
            for sibling_id, _ in self._graph.neighbors(node_id, ["SIBLING"], depth=1):
                _add(sibling_id, seed_score * _HOP_DECAY["SIBLING"], "SIBLING")

            # Entity traversal: drug/condition across all chapters
            for entity_id, _ in self._graph.neighbors(node_id, ["MENTIONS"], depth=1):
                mentions = self._graph.neighbors(entity_id, ["MENTIONED_IN"], depth=1)
                for mention_id, _ in mentions[:_MAX_ENTITY_MENTIONS]:
                    if mention_id != node_id:
                        _add(mention_id, seed_score * _HOP_DECAY["MENTIONED_IN"], "MENTIONED_IN")

            # Explicit cross-references
            for ref_id, _ in self._graph.neighbors(node_id, ["CROSS_REF"], depth=1):
                _add(ref_id, seed_score * _HOP_DECAY["CROSS_REF"], "CROSS_REF")

        results: list[ScoredNode] = []
        for node_id, (score, via) in scored.items():
            node = self._graph.node(node_id)
            if node is None:
                continue
            meta = node.metadata
            path_parts = [
                meta.get("part", ""),
                meta.get("chapter", ""),
                meta.get("section", ""),
                meta.get("subsection", ""),
                node.type,
            ]
            path = " > ".join(p for p in path_parts if p)
            results.append(ScoredNode(node=node, score=score, path=path, via=via))

        results.sort(key=lambda x: -x.score)
        return results[: self._top_k]
