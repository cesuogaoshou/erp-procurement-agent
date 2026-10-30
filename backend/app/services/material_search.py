"""Bounded, data-driven material name resolution.

The model may understand a short name or alias, but the server decides which
database rows are plausible. Candidates always come from the database, so a
database switch does not require putting a material list into the prompt.
"""
from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Material, MaterialAlias

MIN_CANDIDATE_SCORE = 0.6
AUTO_RESOLVE_SCORE = 0.9
AMBIGUITY_MARGIN = 0.04


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    return " ".join(text.split())


def _score_text(query: str, text: str) -> tuple[float, str]:
    if not query or not text:
        return 0.0, "none"
    if query == text:
        return 1.0, "exact"
    if query in text:
        return 0.9, "substring"
    if text in query:
        return 0.75, "superset"
    ratio = SequenceMatcher(None, query, text).ratio()
    if ratio >= 0.65:
        return round(ratio * 0.8, 4), "fuzzy"
    return 0.0, "none"


def search_materials(session: Session, query: str, limit: int = 5) -> list[dict]:
    """Return plausible materials ordered by score.

    The result is intentionally a candidate list, not a silent final choice.
    Callers decide whether the top score is strong enough and whether the
    original source text supports it.
    """
    normalized_query = normalize_name(query)
    if not normalized_query:
        return []
    materials = list(session.scalars(select(Material).order_by(Material.id)))
    aliases = list(session.scalars(select(MaterialAlias).where(MaterialAlias.active.is_(True))))
    aliases_by_material: dict[int, list[str]] = {}
    for alias in aliases:
        aliases_by_material.setdefault(alias.material_id, []).append(alias.alias)

    best_by_material: dict[int, dict] = {}
    for material in materials:
        candidates: list[tuple[float, str, str | None]] = []
        code = normalize_name(material.code)
        name = normalize_name(material.name)
        score, match_type = _score_text(normalized_query, code)
        if score:
            candidates.append((score, f"code_{match_type}", None))
        score, match_type = _score_text(normalized_query, name)
        if score:
            candidates.append((score, f"name_{match_type}", None))
        for alias in aliases_by_material.get(material.id, []):
            score, match_type = _score_text(normalized_query, normalize_name(alias))
            if score:
                candidates.append((score, f"alias_{match_type}", alias))
        if not candidates:
            continue
        score, match_type, matched_alias = max(candidates, key=lambda item: (item[0], item[2] or ""))
        if score < MIN_CANDIDATE_SCORE:
            continue
        best_by_material[material.id] = {
            "material_id": material.id,
            "code": material.code,
            "name": material.name,
            "unit": material.unit,
            "score": round(score, 4),
            "match_type": match_type,
            "matched_alias": matched_alias,
        }

    ranked = sorted(best_by_material.values(), key=lambda item: (-item["score"], item["name"], item["material_id"]))
    if not ranked:
        return []
    top_score = ranked[0]["score"]
    for item in ranked:
        item["requires_confirmation"] = item["score"] < AUTO_RESOLVE_SCORE or (
            item is not ranked[0] and top_score - item["score"] < AMBIGUITY_MARGIN
        )
    return ranked[:limit]


def source_mentions_material(session: Session, material: Material, source: str | None) -> bool:
    if not source:
        return True
    haystack = source.lower()
    if material.name.lower() in haystack or material.code.lower() in haystack:
        return True
    aliases = session.scalars(
        select(MaterialAlias.alias).where(
            MaterialAlias.material_id == material.id,
            MaterialAlias.active.is_(True),
        )
    )
    return any(alias_appears_standalone(str(alias), source) for alias in aliases)


_STANDALONE_BEFORE = set(" \t\r\n，。；;、,.!?！？:：()（）-—/买采购需要要点些的个件套用拿取订做请帮我给再来拿")
_STANDALONE_AFTER = set(" \t\r\n，。；;、,.!?！？:：()（）-—/件个套台箱")


def alias_appears_standalone(alias: str, text: str) -> bool:
    """Avoid accepting an alias embedded in a longer unknown product name.

    For example, "轴承" is a valid alias, but it must not turn
    "火星牌超导轴承" into "标准轴承". A full material name is checked before
    this helper, so normal full-name inputs are unaffected.
    """
    if not alias or not text:
        return False
    alias_lower = alias.lower()
    text_lower = text.lower()
    for match in re.finditer(re.escape(alias_lower), text_lower):
        before = text_lower[match.start() - 1] if match.start() > 0 else ""
        after = text_lower[match.end()] if match.end() < len(text_lower) else ""
        before_ok = not before or before in _STANDALONE_BEFORE or before.isdigit()
        after_ok = not after or after in _STANDALONE_AFTER or after.isdigit()
        if before_ok and after_ok:
            return True
    return False
