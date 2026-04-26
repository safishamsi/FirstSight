from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    id: str
    type: str  # chapter | section | text_chunk | table | table_row | entity
    text: str
    embed_text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Edge:
    src: str
    dst: str
    type: str  # CONTAINS | PART_OF | MENTIONS | MENTIONED_IN | CROSS_REF | SIBLING


@dataclass
class ScoredNode:
    node: Node
    score: float
    path: str   # e.g. "Cardiac Arrest > Drug Doses > table_row"
    via: str    # "direct" | "PART_OF" | "SIBLING" | "MENTIONED_IN" | "CROSS_REF"
