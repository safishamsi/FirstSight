from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(slots=True)
class ChecklistTemplateItem:
    id: str
    label: str
    kind: str = "action"
    required: bool = True
    agent_hint: str | None = None
    speak_before: str | None = None
    tool_name: str | None = None
    tool_query: str | None = None
    tool_prompt: str | None = None
    advance_when: str | None = None
    requires_user_confirmation: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "required": self.required,
            "agent_hint": self.agent_hint,
            "speak_before": self.speak_before,
            "tool_name": self.tool_name,
            "tool_query": self.tool_query,
            "tool_prompt": self.tool_prompt,
            "advance_when": self.advance_when,
            "requires_user_confirmation": self.requires_user_confirmation,
        }


@dataclass(slots=True)
class ProtocolPack:
    id: str
    title: str
    summary: str
    severity: str
    incident_type: str | None
    search_terms: list[str]
    activation_triggers: list[str]
    manual_markdown: str
    checklist_template: list[ChecklistTemplateItem]

    @property
    def manual_text(self) -> str:
        return _normalize_text(self.manual_markdown)

    def to_summary(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "severity": self.severity,
            "incident_type": self.incident_type,
            "search_terms": list(self.search_terms),
            "activation_triggers": list(self.activation_triggers),
            "checklist_count": len(self.checklist_template),
        }

    def to_detail(self) -> dict[str, object]:
        return {
            **self.to_summary(),
            "manual_markdown": self.manual_markdown,
            "checklist_template": [item.to_dict() for item in self.checklist_template],
        }


@dataclass(slots=True)
class ProtocolRegistry:
    packs: list[ProtocolPack]

    def get(self, protocol_id: str) -> ProtocolPack | None:
        return next((pack for pack in self.packs if pack.id == protocol_id), None)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "step"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


_SUPPORTED_STEP_KINDS = {
    "action",
    "observe",
    "confirm",
    "user_action",
    "agent_check",
    "agent_tool_call",
    "decision",
}


def _parse_checklist(markdown_text: str) -> list[ChecklistTemplateItem]:
    items: list[ChecklistTemplateItem] = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("- [ ] "):
            continue
        label = line.removeprefix("- [ ] ").strip()
        kind = "action"
        if ":" in label:
            maybe_kind, maybe_label = label.split(":", 1)
            if maybe_kind.strip().lower() in _SUPPORTED_STEP_KINDS:
                kind = maybe_kind.strip().lower()
                label = maybe_label.strip()
        items.append(
            ChecklistTemplateItem(
                id=_slugify(label),
                label=label,
                kind=kind,
                required=True,
            )
        )
    return items


def _apply_step_details(
    items: list[ChecklistTemplateItem],
    step_details: dict[str, object] | None,
) -> list[ChecklistTemplateItem]:
    if not step_details:
        return items

    enriched: list[ChecklistTemplateItem] = []
    for item in items:
        detail = step_details.get(item.id) if isinstance(step_details, dict) else None
        if not isinstance(detail, dict):
            enriched.append(item)
            continue
        enriched.append(
            ChecklistTemplateItem(
                id=item.id,
                label=item.label,
                kind=detail.get("kind", item.kind),
                required=bool(detail.get("required", item.required)),
                agent_hint=detail.get("agent_hint"),
                speak_before=detail.get("speak_before"),
                tool_name=detail.get("tool_name"),
                tool_query=detail.get("tool_query"),
                tool_prompt=detail.get("tool_prompt"),
                advance_when=detail.get("advance_when"),
                requires_user_confirmation=bool(detail.get("requires_user_confirmation", False)),
            )
        )
    return enriched


def _load_pack(pack_dir: Path) -> ProtocolPack:
    metadata = json.loads((pack_dir / "metadata.json").read_text(encoding="utf-8"))
    manual_markdown = (pack_dir / "manual.md").read_text(encoding="utf-8")
    checklist_markdown = (pack_dir / "checklist.md").read_text(encoding="utf-8")
    summary = metadata.get("summary")
    if not summary:
        summary = next(
            (line.strip() for line in manual_markdown.splitlines() if line.strip() and not line.startswith("#")),
            metadata["title"],
        )
    checklist_template = _apply_step_details(
        _parse_checklist(checklist_markdown),
        metadata.get("step_details"),
    )
    return ProtocolPack(
        id=metadata["id"],
        title=metadata["title"],
        summary=summary,
        severity=metadata.get("severity", "medium"),
        incident_type=metadata.get("incident_type"),
        search_terms=list(metadata.get("search_terms", [])),
        activation_triggers=list(metadata.get("activation_triggers", [])),
        manual_markdown=manual_markdown,
        checklist_template=checklist_template,
    )


def load_protocol_packs(root: Path | None = None) -> list[ProtocolPack]:
    base = root or Path(__file__).resolve().parent / "packs"
    packs: list[ProtocolPack] = []
    for pack_dir in sorted(base.iterdir()):
        if not pack_dir.is_dir():
            continue
        packs.append(_load_pack(pack_dir))
    return packs


@lru_cache(maxsize=1)
def get_protocol_registry() -> ProtocolRegistry:
    return ProtocolRegistry(packs=load_protocol_packs())
