from __future__ import annotations

import re
import sqlite3
import threading
from dataclasses import dataclass
from functools import lru_cache

from .loader import ProtocolPack, get_protocol_registry


@dataclass(slots=True)
class ProtocolSearchHit:
    protocol_id: str
    title: str
    score: float
    matched_excerpt: str
    severity: str

    def to_dict(self) -> dict[str, object]:
        return {
            "protocol_id": self.protocol_id,
            "title": self.title,
            "score": self.score,
            "matched_excerpt": self.matched_excerpt,
            "severity": self.severity,
        }


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _excerpt_for(pack: ProtocolPack, query: str) -> str:
    lowered = query.lower().strip()
    if lowered:
        for line in pack.manual_markdown.splitlines():
            if lowered in line.lower():
                return line.strip()
    query_tokens = set(_tokenize(query))
    if query_tokens:
        for line in pack.manual_markdown.splitlines():
            if query_tokens & set(_tokenize(line)):
                return line.strip()
    for line in pack.manual_markdown.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return pack.summary


def _score_pack(pack: ProtocolPack, query: str, incident_type: str | None) -> float:
    score = 0.0
    query_lower = query.lower().strip()
    query_tokens = set(_tokenize(query))
    if not query_tokens and not query_lower:
        return 0.0

    title_tokens = set(_tokenize(pack.title))
    summary_tokens = set(_tokenize(pack.summary))
    search_tokens = set().union(*(_tokenize(term) for term in pack.search_terms)) if pack.search_terms else set()
    trigger_tokens = set().union(*(_tokenize(term) for term in pack.activation_triggers)) if pack.activation_triggers else set()
    manual_tokens = set(_tokenize(pack.manual_markdown))

    if query_lower and (query_lower in pack.title.lower() or query_lower in pack.id.lower()):
        score += 8.0
    if query_lower and query_lower in pack.summary.lower():
        score += 5.0
    if incident_type and pack.incident_type and incident_type.lower() == pack.incident_type.lower():
        score += 5.0

    score += len(query_tokens & title_tokens) * 3.0
    score += len(query_tokens & summary_tokens) * 2.5
    score += len(query_tokens & search_tokens) * 2.5
    score += len(query_tokens & trigger_tokens) * 2.0
    score += len(query_tokens & manual_tokens) * 0.5
    return score


class ProtocolSearchIndex:
    def __init__(self, packs: list[ProtocolPack]) -> None:
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._lock = threading.Lock()
        self._packs = {pack.id: pack for pack in packs}
        try:
            with self._lock:
                self._conn.execute(
                    """
                    CREATE VIRTUAL TABLE protocol_fts USING fts5(
                        protocol_id UNINDEXED,
                        title,
                        summary,
                        manual,
                        search_terms,
                        activation_triggers
                    )
                    """
                )
            self._fts_enabled = True
        except sqlite3.OperationalError:
            self._fts_enabled = False
            return

        with self._lock:
            self._conn.executemany(
                """
                INSERT INTO protocol_fts(protocol_id, title, summary, manual, search_terms, activation_triggers)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        pack.id,
                        pack.title,
                        pack.summary,
                        pack.manual_markdown,
                        " ".join(pack.search_terms),
                        " ".join(pack.activation_triggers),
                    )
                    for pack in packs
                ],
            )

    def match_scores(self, query: str, limit: int = 20) -> dict[str, float]:
        if not self._fts_enabled:
            return {}
        tokens = _tokenize(query)
        if not tokens:
            return {}
        fts_query = " OR ".join(dict.fromkeys(tokens))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT protocol_id, bm25(protocol_fts)
                FROM protocol_fts
                WHERE protocol_fts MATCH ?
                ORDER BY bm25(protocol_fts)
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
        scores: dict[str, float] = {}
        for protocol_id, bm25_score in rows:
            scores[str(protocol_id)] = max(0.0, 12.0 - float(bm25_score))
        return scores


@lru_cache(maxsize=1)
def get_protocol_search_index() -> ProtocolSearchIndex:
    return ProtocolSearchIndex(get_protocol_registry().packs)


def search_protocols(
    packs: list[ProtocolPack],
    *,
    query: str,
    incident_type: str | None = None,
    limit: int = 5,
) -> list[ProtocolSearchHit]:
    fts_scores = get_protocol_search_index().match_scores(query, limit=max(limit * 3, 20))
    hits: list[ProtocolSearchHit] = []
    for pack in packs:
        score = _score_pack(pack, query, incident_type)
        score += fts_scores.get(pack.id, 0.0)
        if score <= 0:
            continue
        hits.append(
            ProtocolSearchHit(
                protocol_id=pack.id,
                title=pack.title,
                score=score,
                matched_excerpt=_excerpt_for(pack, query),
                severity=pack.severity,
            )
        )
    return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]
