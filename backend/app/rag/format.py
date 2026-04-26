from __future__ import annotations

import tiktoken

from . import ScoredNode

_TOKENIZER = tiktoken.get_encoding("cl100k_base")
_MAX_NODE_TOKENS = 300


def _truncate(text: str, max_tokens: int) -> str:
    tokens = _TOKENIZER.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return _TOKENIZER.decode(tokens[:max_tokens]) + "…"


def format_rag_context(scored_nodes: list[ScoredNode], max_tokens: int = 1200) -> str:
    if not scored_nodes:
        return ""

    lines: list[str] = ["Retrieved clinical guidance (JRCALC 2022):"]
    budget = max_tokens - len(_TOKENIZER.encode(lines[0]))

    for sn in scored_nodes:
        text = _truncate(sn.node.text, _MAX_NODE_TOKENS)
        line = f"[{sn.path}] {text}  (via: {sn.via})"
        line_tokens = len(_TOKENIZER.encode(line))
        if budget - line_tokens < 0:
            break
        lines.append(line)
        budget -= line_tokens

    return "\n".join(lines)
