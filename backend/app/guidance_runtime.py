from __future__ import annotations

from dataclasses import dataclass

from .incident_state import ProtocolHit
from .protocols import get_protocol_registry, search_protocols
from .session_manager import session_manager

_MIN_MANUAL_ACTIVATION_SCORE = 4.0
_MIN_SPEECH_ACTIVATION_SCORE = 8.0
_GENERIC_QUERY_TOKENS = {
    "a",
    "an",
    "any",
    "check",
    "friend",
    "help",
    "i",
    "me",
    "my",
    "patient",
    "person",
    "please",
    "someone",
    "something",
    "the",
    "them",
    "they",
    "this",
}


def _has_meaningful_activation_language(query: str) -> bool:
    from .protocols.search import _tokenize

    meaningful_tokens = [token for token in _tokenize(query) if token not in _GENERIC_QUERY_TOKENS]
    return len(meaningful_tokens) >= 1


@dataclass(slots=True)
class ProtocolSearchOutcome:
    hits: list[ProtocolHit]
    activated_title: str | None = None


def _build_protocol_hits(query: str, incident_type: str | None = None) -> list[ProtocolHit]:
    registry = get_protocol_registry()
    search_hits = search_protocols(
        registry.packs,
        query=query,
        incident_type=incident_type,
    )
    return [
        ProtocolHit(
            protocol_id=hit.protocol_id,
            title=hit.title,
            score=hit.score,
            matched_excerpt=hit.matched_excerpt,
            severity=hit.severity,
        )
        for hit in search_hits
    ]


def search_and_optionally_activate_protocol(
    session_id: str,
    *,
    query: str,
    incident_type: str | None = None,
    auto_activate: bool = True,
    allow_replace_active: bool = False,
    min_score: float | None = None,
) -> ProtocolSearchOutcome:
    protocol_hits = _build_protocol_hits(query=query, incident_type=incident_type)
    session_manager.set_protocol_hits(session_id, protocol_hits)
    if not auto_activate or not protocol_hits:
        return ProtocolSearchOutcome(hits=protocol_hits)

    required_score = _MIN_MANUAL_ACTIVATION_SCORE if allow_replace_active else _MIN_SPEECH_ACTIVATION_SCORE
    if min_score is not None:
        required_score = min_score

    best = protocol_hits[0]
    if best.score < required_score:
        session_manager.append_debug_event(
            session_id,
            "protocol_activation_skipped_low_score",
            {
                "protocol_id": best.protocol_id,
                "score": best.score,
                "required_score": required_score,
                "query": query,
            },
        )
        return ProtocolSearchOutcome(hits=protocol_hits)

    if not allow_replace_active and not _has_meaningful_activation_language(query):
        session_manager.append_debug_event(
            session_id,
            "protocol_activation_skipped_generic_query",
            {
                "protocol_id": best.protocol_id,
                "score": best.score,
                "query": query,
            },
        )
        return ProtocolSearchOutcome(hits=protocol_hits)

    current_record = session_manager.get(session_id)
    if current_record is None:
        return ProtocolSearchOutcome(hits=protocol_hits)

    active_protocol_id = current_record.incident_state.active_protocol_id
    if active_protocol_id == best.protocol_id:
        session_manager.append_debug_event(
            session_id,
            "protocol_activation_skipped_already_active",
            {"protocol_id": best.protocol_id, "query": query},
        )
        return ProtocolSearchOutcome(hits=protocol_hits)

    if active_protocol_id and not allow_replace_active:
        session_manager.append_debug_event(
            session_id,
            "protocol_activation_skipped_active_lock",
            {
                "active_protocol_id": active_protocol_id,
                "candidate_protocol_id": best.protocol_id,
                "query": query,
            },
        )
        return ProtocolSearchOutcome(hits=protocol_hits)

    registry = get_protocol_registry()
    protocol = registry.get(best.protocol_id)
    if protocol is None:
        return ProtocolSearchOutcome(hits=protocol_hits)

    session_manager.set_checklist_from_protocol(session_id, protocol, matched_query=query)
    session_manager.append_debug_event(
        session_id,
        "protocol_activated",
        {
            "protocol_id": protocol.id,
            "title": protocol.title,
            "query": query,
            "allow_replace_active": allow_replace_active,
            "score": best.score,
        },
    )
    return ProtocolSearchOutcome(hits=protocol_hits, activated_title=protocol.title)
