from __future__ import annotations

import pickle
from collections import deque
from pathlib import Path

import networkx as nx

from . import Edge, Node

_GRAPH_FILE = "graph.pkl"
_NODES_FILE = "nodes.pkl"


class ClinicalGraph:
    def __init__(self, g: nx.DiGraph, node_map: dict[str, Node]) -> None:
        self._g = g
        self._nodes = node_map

    @classmethod
    def build(cls, nodes: list[Node], edges: list[Edge]) -> "ClinicalGraph":
        g: nx.DiGraph = nx.DiGraph()
        node_map: dict[str, Node] = {}

        for n in nodes:
            g.add_node(n.id, node_type=n.type)
            node_map[n.id] = n

        for e in edges:
            if e.src in node_map and e.dst in node_map:
                g.add_edge(e.src, e.dst, edge_type=e.type)

        return cls(g, node_map)

    def save(self, directory: str) -> None:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        with open(path / _GRAPH_FILE, "wb") as f:
            pickle.dump(self._g, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(path / _NODES_FILE, "wb") as f:
            pickle.dump(self._nodes, f, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load(cls, directory: str) -> "ClinicalGraph":
        path = Path(directory)
        with open(path / _GRAPH_FILE, "rb") as f:
            g: nx.DiGraph = pickle.load(f)
        with open(path / _NODES_FILE, "rb") as f:
            node_map: dict[str, Node] = pickle.load(f)
        return cls(g, node_map)

    def node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def neighbors(
        self,
        node_id: str,
        edge_types: list[str],
        depth: int = 1,
    ) -> list[tuple[str, int]]:
        """BFS from node_id following only edges of the given types.

        Returns list of (neighbor_node_id, hop_distance) tuples.
        Excludes the starting node itself.
        """
        if node_id not in self._g:
            return []

        edge_type_set = set(edge_types)
        visited: dict[str, int] = {}  # node_id → hop distance
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current_id, hop = queue.popleft()
            if hop >= depth:
                continue
            for successor in self._g.successors(current_id):
                edge_data = self._g[current_id][successor]
                if edge_data.get("edge_type") not in edge_type_set:
                    continue
                if successor in visited or successor == node_id:
                    continue
                visited[successor] = hop + 1
                queue.append((successor, hop + 1))

        return list(visited.items())

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return self._g.number_of_edges()

    def node_type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for n in self._nodes.values():
            counts[n.type] = counts.get(n.type, 0) + 1
        return counts

    def edge_type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for _, _, data in self._g.edges(data=True):
            et = data.get("edge_type", "unknown")
            counts[et] = counts.get(et, 0) + 1
        return counts
