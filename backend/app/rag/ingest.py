from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Iterator

import warnings

import tiktoken
from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning
from ebooklib import ITEM_DOCUMENT, epub

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from . import Edge, Node
from .entities import extract_entities

_TOKENIZER = tiktoken.get_encoding("cl100k_base")
_MAX_CHUNK_TOKENS = 450
_MIN_CHUNK_TOKENS = 60
_OVERLAP_TOKENS = 50

_FOOTNOTE_RE = re.compile(r"\[\d+\]|†|\*(?!\s*\w)")
_CROSSREF_RE = re.compile(r"[Ss]ee\s+([A-Z][a-zA-Z\s\-]+?)(?:\.|,|$)", re.MULTILINE)


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _FOOTNOTE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _token_count(text: str) -> int:
    return len(_TOKENIZER.encode(text))


def _split_tokens(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        stokens = _token_count(sentence)
        if current_tokens + stokens > max_tokens and current:
            chunk = " ".join(current)
            if _token_count(chunk) >= _MIN_CHUNK_TOKENS:
                chunks.append(chunk)
            # overlap: keep last sentence(s) up to overlap_tokens
            overlap: list[str] = []
            overlap_count = 0
            for s in reversed(current):
                st = _token_count(s)
                if overlap_count + st > overlap_tokens:
                    break
                overlap.insert(0, s)
                overlap_count += st
            current = overlap
            current_tokens = overlap_count
        current.append(sentence)
        current_tokens += stokens

    if current:
        chunk = " ".join(current)
        if _token_count(chunk) >= _MIN_CHUNK_TOKENS:
            chunks.append(chunk)

    return chunks if chunks else [text]


def _node_id(*parts: str) -> str:
    slug = "__".join(re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_") for p in parts if p)
    return slug[:120] or str(uuid.uuid4())[:8]


def _context_prefix(part: str, chapter: str, section: str, subsection: str = "") -> str:
    parts = [p for p in [part, chapter, section, subsection] if p]
    return "[" + " > ".join(parts) + "]"


def _serialise_table(table: Tag) -> list[tuple[str, str]]:
    """Return (header_row_text, [(row_text, row_dict)]) for a <table>."""
    rows = table.find_all("tr")
    if not rows:
        return []

    headers: list[str] = []
    first_row = rows[0]
    header_cells = first_row.find_all(["th", "td"])
    headers = [_clean(c.get_text(" ", strip=True)) for c in header_cells]

    result: list[tuple[str, str]] = []
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        values = [_clean(c.get_text(" ", strip=True)) for c in cells]
        if not any(values):
            continue
        if headers:
            parts = [
                f"{h}: {v}" for h, v in zip(headers, values, strict=False) if v
            ]
        else:
            parts = [v for v in values if v]
        result.append(" | ".join(parts))

    return result


def _iter_spine_docs(book: epub.EpubBook) -> Iterator[epub.EpubItem]:
    spine_ids = {item_id for item_id, _ in book.spine}
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        if item.get_id() in spine_ids:
            yield item


def load_epub(path: str) -> tuple[list[Node], list[Edge]]:
    book = epub.read_epub(path, options={"ignore_ncx": True})
    nodes: list[Node] = []
    edges: list[Edge] = []
    entity_nodes: dict[str, Node] = {}  # entity_id → Node

    def _add_entity_link(src_id: str, text: str) -> None:
        for eid in extract_entities(text):
            if eid not in entity_nodes:
                entity_nodes[eid] = Node(
                    id=eid,
                    type="entity",
                    text=eid.replace("entity_", "").replace("_", " ").title(),
                    embed_text=eid.replace("entity_", "").replace("_", " ").title(),
                    metadata={"category": "drug"},
                )
            edges.append(Edge(src=src_id, dst=eid, type="MENTIONS"))
            edges.append(Edge(src=eid, dst=src_id, type="MENTIONED_IN"))

    current_part = ""
    current_chapter = ""
    current_section = ""
    current_subsection = ""
    current_chapter_id = ""
    current_section_id = ""
    last_chunk_id_in_section: str | None = None

    for item in _iter_spine_docs(book):
        soup = BeautifulSoup(item.get_content(), "lxml")

        # Remove nav elements
        for nav in soup.find_all(["nav", "aside"]):
            nav.decompose()

        for element in soup.find_all(["h1", "h2", "h3", "h4", "p", "table"]):
            tag = element.name
            text = _clean(element.get_text(" ", strip=True))

            if not text:
                continue

            if tag == "h1":
                current_part = text
                current_chapter = ""
                current_section = ""
                current_subsection = ""
                current_chapter_id = ""
                current_section_id = ""
                last_chunk_id_in_section = None
                continue

            if tag == "h2":
                current_chapter = text
                current_section = ""
                current_subsection = ""
                last_chunk_id_in_section = None

                nid = _node_id(current_part, current_chapter)
                prefix = _context_prefix(current_part, current_chapter, "")
                node = Node(
                    id=nid,
                    type="chapter",
                    text=text,
                    embed_text=f"{prefix}\n{text}",
                    metadata={"part": current_part, "chapter": current_chapter},
                )
                nodes.append(node)
                current_chapter_id = nid
                current_section_id = ""
                continue

            if tag == "h3":
                current_section = text
                current_subsection = ""
                last_chunk_id_in_section = None

                nid = _node_id(current_part, current_chapter, current_section)
                prefix = _context_prefix(current_part, current_chapter, current_section)
                node = Node(
                    id=nid,
                    type="section",
                    text=text,
                    embed_text=f"{prefix}\n{text}",
                    metadata={
                        "part": current_part,
                        "chapter": current_chapter,
                        "section": current_section,
                    },
                )
                nodes.append(node)
                current_section_id = nid

                if current_chapter_id:
                    edges.append(Edge(src=current_chapter_id, dst=nid, type="CONTAINS"))
                    edges.append(Edge(src=nid, dst=current_chapter_id, type="PART_OF"))
                continue

            if tag == "h4":
                current_subsection = text
                last_chunk_id_in_section = None
                continue

            if tag == "table":
                table_text = _clean(element.get_text(" ", strip=True))
                if not table_text:
                    continue

                headers_row = element.find("tr")
                headers_text = (
                    _clean(headers_row.get_text(" ", strip=True)) if headers_row else ""
                )
                table_id = _node_id(
                    current_part, current_chapter, current_section, current_subsection, "table"
                )
                prefix = _context_prefix(
                    current_part, current_chapter, current_section, current_subsection
                )
                row_texts = _serialise_table(element)
                table_summary = f"Table with {len(row_texts)} rows. Headers: {headers_text}"
                table_node = Node(
                    id=table_id,
                    type="table",
                    text=table_summary,
                    embed_text=f"{prefix}\n{table_summary}",
                    metadata={
                        "part": current_part,
                        "chapter": current_chapter,
                        "section": current_section,
                        "subsection": current_subsection,
                    },
                )
                nodes.append(table_node)

                if current_section_id:
                    edges.append(Edge(src=current_section_id, dst=table_id, type="CONTAINS"))
                    edges.append(Edge(src=table_id, dst=current_section_id, type="PART_OF"))
                elif current_chapter_id:
                    edges.append(Edge(src=current_chapter_id, dst=table_id, type="CONTAINS"))
                    edges.append(Edge(src=table_id, dst=current_chapter_id, type="PART_OF"))

                for i, row_text in enumerate(row_texts):
                    row_id = f"{table_id}__row_{i}"
                    row_node = Node(
                        id=row_id,
                        type="table_row",
                        text=row_text,
                        embed_text=f"{prefix}\n{row_text}",
                        metadata={
                            "part": current_part,
                            "chapter": current_chapter,
                            "section": current_section,
                            "subsection": current_subsection,
                            "table_id": table_id,
                            "row_index": i,
                        },
                    )
                    nodes.append(row_node)
                    edges.append(Edge(src=table_id, dst=row_id, type="CONTAINS"))
                    edges.append(Edge(src=row_id, dst=table_id, type="PART_OF"))
                    _add_entity_link(row_id, row_text)

                _add_entity_link(table_id, table_text)
                continue

            # Prose paragraph
            if tag == "p" and _token_count(text) >= _MIN_CHUNK_TOKENS:
                chunks = _split_tokens(text, _MAX_CHUNK_TOKENS, _OVERLAP_TOKENS)
                for ci, chunk_text in enumerate(chunks):
                    prefix = _context_prefix(
                        current_part, current_chapter, current_section, current_subsection
                    )
                    chunk_id = _node_id(
                        current_part,
                        current_chapter,
                        current_section,
                        current_subsection,
                        f"chunk_{ci}",
                    )
                    chunk_node = Node(
                        id=chunk_id,
                        type="text_chunk",
                        text=chunk_text,
                        embed_text=f"{prefix}\n{chunk_text}",
                        metadata={
                            "part": current_part,
                            "chapter": current_chapter,
                            "section": current_section,
                            "subsection": current_subsection,
                            "chunk_index": ci,
                        },
                    )
                    nodes.append(chunk_node)

                    parent_id = current_section_id or current_chapter_id
                    if parent_id:
                        edges.append(Edge(src=parent_id, dst=chunk_id, type="CONTAINS"))
                        edges.append(Edge(src=chunk_id, dst=parent_id, type="PART_OF"))

                    if last_chunk_id_in_section:
                        edges.append(
                            Edge(src=last_chunk_id_in_section, dst=chunk_id, type="SIBLING")
                        )
                        edges.append(
                            Edge(src=chunk_id, dst=last_chunk_id_in_section, type="SIBLING")
                        )
                    last_chunk_id_in_section = chunk_id

                    _add_entity_link(chunk_id, chunk_text)

                    # Detect cross-references
                    for match in _CROSSREF_RE.finditer(chunk_text):
                        ref_target = _clean(match.group(1))
                        ref_target_id = _node_id(ref_target)
                        edges.append(Edge(src=chunk_id, dst=ref_target_id, type="CROSS_REF"))

    # Add entity nodes to node list
    nodes.extend(entity_nodes.values())

    return nodes, edges
