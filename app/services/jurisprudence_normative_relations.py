from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from app.domain.jurisprudence import NormRelationType
from app.domain.jurisprudence_document import JurisprudenceDocumentRepresentation
from app.domain.jurisprudence_metadata import JurisprudenceMetadataRecord
from app.domain.jurisprudence_normative_relations import (
    JurisprudenceNormativeLinkBasis,
    JurisprudenceNormativeMention,
    JurisprudenceNormativeRelationRecord,
    JurisprudenceNormativeUnitType,
)

_RESOURCE_ROOT = Path(__file__).resolve().parents[1] / "resources"
_DEFAULT_MANIFEST = _RESOURCE_ROOT / "primary_legal_knowledge_manifest.json"
_DEFAULT_CATALOG = _RESOURCE_ROOT / "fiscal_corpus_15_catalog.json"

_ARTICLE_RE = re.compile(
    r"(?i)\b(?:art[ií]culo|art\.)\s*(?P<unit>\d+(?:-[A-Za-z0-9]+)?)"
)
_RULE_RE = re.compile(
    r"(?i)\bregla\s*(?P<unit>\d+(?:\.\d+){1,6})"
)
_SPACE_RE = re.compile(r"\s+")

_RELATION_PATTERNS: tuple[tuple[NormRelationType, re.Pattern[str]], ...] = (
    (
        NormRelationType.INTERPRETS,
        re.compile(
            r"(?i)\b(?:interpreta(?:r|do|da|n)?|interpretaci[oó]n|"
            r"debe\s+interpretarse|debe\s+leerse\s+en\s+el\s+sentido|"
            r"sentido\s+y\s+alcance|alcance\s+del)\b"
        ),
    ),
    (
        NormRelationType.DISTINGUISHES,
        re.compile(
            r"(?i)\b(?:distingue|distinci[oó]n|supuesto\s+distinto|"
            r"no\s+resulta\s+aplicable|no\s+es\s+aplicable)\b"
        ),
    ),
    (
        NormRelationType.CONFLICTS,
        re.compile(
            r"(?i)\b(?:contradice|contradicci[oó]n|conflicto|incompatible|"
            r"incompatibilidad|se\s+opone\s+a)\b"
        ),
    ),
    (
        NormRelationType.COMPLEMENTS,
        re.compile(
            r"(?i)\b(?:complementa|complementario|integra(?:r|do|da)?|"
            r"debe\s+leerse\s+conjuntamente)\b"
        ),
    ),
)


class JurisprudenceNormativeRelationError(RuntimeError):
    """No puede construirse de forma segura el registro jurisprudencial E.3."""


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return _SPACE_RE.sub(" ", without_marks).strip()


def _load_json(path: Path, *, expected: type[list[Any]] | type[dict[str, Any]]) -> Any:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise JurisprudenceNormativeRelationError(
            f"No pudo leerse el recurso E.3 requerido: {path.name}."
        ) from exc
    if not isinstance(payload, expected):
        raise JurisprudenceNormativeRelationError(
            f"El recurso E.3 {path.name} tiene una estructura inválida."
        )
    return payload


def _corpus_aliases(
    *,
    manifest_path: Path,
    catalog_path: Path,
) -> tuple[list[str], dict[str, set[str]], dict[str, str]]:
    manifest = _load_json(manifest_path, expected=dict)
    catalog = _load_json(catalog_path, expected=list)
    raw_ids = manifest.get("normative_corpus_ids")
    if not isinstance(raw_ids, list) or len(raw_ids) != 12 or not all(
        isinstance(item, str) for item in raw_ids
    ):
        raise JurisprudenceNormativeRelationError(
            "El manifiesto A.8 no expone exactamente los 12 corpus normativos."
        )
    corpus_ids = list(raw_ids)
    catalog_by_id = {
        str(item.get("canonical_id")): item
        for item in catalog
        if isinstance(item, dict)
    }
    if not set(corpus_ids) <= set(catalog_by_id):
        raise JurisprudenceNormativeRelationError(
            "El catálogo fiscal no contiene todos los corpus A.8."
        )

    aliases: dict[str, set[str]] = {}
    all_catalog_aliases: dict[str, str] = {}
    for canonical_id, item in catalog_by_id.items():
        title = str(item.get("title") or "").strip()
        filename = str(item.get("filename") or "").strip()
        stem = Path(filename).stem
        values = {canonical_id, stem, title}
        values = {value for value in values if value}
        normalized = {_normalize(value) for value in values}
        for alias in normalized:
            all_catalog_aliases[alias] = canonical_id
        if canonical_id in corpus_ids:
            aliases[canonical_id] = normalized

    # Formas jurídicas usuales cuyo texto puede diferir del filename técnico.
    extras = {
        "cpeum": {"constitucion politica de los estados unidos mexicanos", "cpeum"},
        "cff": {"codigo fiscal de la federacion", "cff"},
        "lfdc": {"ley federal de los derechos del contribuyente", "lfdc"},
        "lfpca": {"ley federal de procedimiento contencioso administrativo", "lfpca"},
        "lfisan": {"ley federal del impuesto sobre automoviles nuevos", "lfisan"},
        "lieps": {"ley del impuesto especial sobre produccion y servicios", "lieps"},
        "lisr": {"ley del impuesto sobre la renta", "lisr"},
        "liva": {"ley del impuesto al valor agregado", "liva"},
        "lotfja": {"ley organica del tribunal federal de justicia administrativa", "lotfja"},
        "reg_lisr_060516": {
            "reglamento de la ley del impuesto sobre la renta",
            "reg lisr",
            "rlisr",
        },
        "reg_liva_250914": {
            "reglamento de la ley del impuesto al valor agregado",
            "reg liva",
            "rliva",
        },
        "rmf_2026": {"resolucion miscelanea fiscal para 2026", "rmf 2026", "rmf"},
    }
    for canonical_id, values in extras.items():
        aliases.setdefault(canonical_id, set()).update(values)
    return corpus_ids, aliases, all_catalog_aliases


def _instrument_after_unit(
    page_text: str,
    *,
    match_end: int,
    aliases: dict[str, set[str]],
    all_catalog_aliases: dict[str, str],
) -> tuple[str | None, str | None, bool]:
    sentence_end_candidates = [
        pos for mark in (".", ";", "\n")
        if (pos := page_text.find(mark, match_end)) >= 0
    ]
    sentence_end = min(sentence_end_candidates) if sentence_end_candidates else len(page_text)
    tail = page_text[match_end:sentence_end]
    normalized_tail = _normalize(tail)

    # Priorizar el alias más largo evita que "lisr" gane sobre el nombre completo.
    candidates: list[tuple[int, str, str, bool]] = []
    for canonical_id, values in aliases.items():
        for alias in values:
            pos = normalized_tail.find(alias)
            if pos >= 0:
                candidates.append((pos, alias, canonical_id, True))
    for alias, canonical_id in all_catalog_aliases.items():
        if canonical_id in aliases:
            continue
        pos = normalized_tail.find(alias)
        if pos >= 0:
            candidates.append((pos, alias, canonical_id, False))
    if not candidates:
        return None, None, False
    candidates.sort(key=lambda item: (item[0], -len(item[1])))
    _, alias, canonical_id, in_primary = candidates[0]
    return alias, canonical_id, in_primary


def _relation_for_excerpt(excerpt: str) -> tuple[NormRelationType, bool]:
    for relation, pattern in _RELATION_PATTERNS:
        if pattern.search(excerpt):
            return relation, True
    return NormRelationType.CITES, False


def _relation_context(text: str, *, start: int, end: int) -> str:
    left_candidates = [text.rfind(mark, 0, start) for mark in (".", ";", "\n")]
    left = max(left_candidates) + 1
    right_candidates = [
        pos for mark in (".", ";", "\n")
        if (pos := text.find(mark, end)) >= 0
    ]
    right = min(right_candidates) if right_candidates else len(text)
    return _SPACE_RE.sub(" ", text[left:right]).strip()


def _excerpt(text: str, *, start: int, end: int) -> str:
    left = max(0, start - 220)
    right = min(len(text), end + 320)
    value = _SPACE_RE.sub(" ", text[left:right]).strip()
    return value[:1200]


def _candidate_ref(
    *,
    corpus_id: str,
    unit_type: JurisprudenceNormativeUnitType,
    unit: str,
) -> str:
    normalized_unit = unit.casefold().replace("-", "_")
    if unit_type is JurisprudenceNormativeUnitType.ARTICLE:
        return f"{corpus_id}:articulo_{normalized_unit}"
    normalized_rule = normalized_unit.replace(".", "_")
    return f"{corpus_id}:regla_{normalized_rule}"


def build_jurisprudence_normative_relation_record(
    document: JurisprudenceDocumentRepresentation,
    *,
    metadata_record: JurisprudenceMetadataRecord,
    manifest_path: Path = _DEFAULT_MANIFEST,
    catalog_path: Path = _DEFAULT_CATALOG,
) -> JurisprudenceNormativeRelationRecord:
    """E.3: vincula sólo menciones normativas explícitas con el corpus cerrado A.8.

    No usa similitud temática, no verifica todavía vigencia ni aplicabilidad y no
    convierte una cita de norma en una ratio decidendi aplicable al caso consultado.
    """
    if metadata_record.document_id != document.document_id:
        raise JurisprudenceNormativeRelationError(
            "E.3 recibió metadatos de un documento jurisprudencial distinto."
        )
    if metadata_record.source_sha256 != document.source_sha256:
        raise JurisprudenceNormativeRelationError(
            "E.3 recibió metadatos con una huella documental distinta."
        )

    corpus_ids, aliases, all_catalog_aliases = _corpus_aliases(
        manifest_path=manifest_path,
        catalog_path=catalog_path,
    )
    mentions: list[JurisprudenceNormativeMention] = []

    for page in document.pages:
        if not page.has_extractable_text:
            continue
        for unit_type, pattern in (
            (JurisprudenceNormativeUnitType.ARTICLE, _ARTICLE_RE),
            (JurisprudenceNormativeUnitType.RULE, _RULE_RE),
        ):
            for match in pattern.finditer(page.text):
                unit = match.group("unit")
                instrument, catalog_id, in_primary = _instrument_after_unit(
                    page.text,
                    match_end=match.end(),
                    aliases=aliases,
                    all_catalog_aliases=all_catalog_aliases,
                )
                excerpt = _excerpt(page.text, start=match.start(), end=match.end())
                relation_context = _relation_context(
                    page.text, start=match.start(), end=match.end()
                )
                relation, material_explicit = _relation_for_excerpt(relation_context)
                candidate_corpus_id = catalog_id if in_primary else None
                candidate_ref = (
                    _candidate_ref(
                        corpus_id=candidate_corpus_id,
                        unit_type=unit_type,
                        unit=unit,
                    )
                    if candidate_corpus_id is not None
                    else None
                )
                mentions.append(
                    JurisprudenceNormativeMention(
                        mention_id=f"E3-NORM-{len(mentions) + 1:03d}",
                        source_page=page.number,
                        source_excerpt=excerpt,
                        legal_unit_type=unit_type,
                        legal_unit=unit,
                        instrument_match=instrument,
                        candidate_corpus_id=candidate_corpus_id,
                        candidate_normative_ref=candidate_ref,
                        corpus_in_primary_manifest=in_primary,
                        relation_type=relation,
                        linkage_basis=(
                            JurisprudenceNormativeLinkBasis.EXPLICIT_RELATION_LANGUAGE
                            if material_explicit
                            else JurisprudenceNormativeLinkBasis.EXPLICIT_NORMATIVE_MENTION
                        ),
                        material_relation_explicit=material_explicit,
                    )
                )

    resolved_mentions: list[JurisprudenceNormativeMention] = []
    for mention in mentions:
        if mention.candidate_normative_ref is not None or not mention.material_relation_explicit:
            resolved_mentions.append(mention)
            continue
        candidates = {
            item.candidate_corpus_id
            for item in mentions
            if item.source_page == mention.source_page
            and item.legal_unit_type is mention.legal_unit_type
            and item.legal_unit.casefold() == mention.legal_unit.casefold()
            and item.candidate_corpus_id is not None
        }
        if len(candidates) != 1:
            resolved_mentions.append(mention)
            continue
        corpus_id = next(iter(candidates))
        if corpus_id is None:
            resolved_mentions.append(mention)
            continue
        resolved_mentions.append(
            mention.model_copy(
                update={
                    "candidate_corpus_id": corpus_id,
                    "candidate_normative_ref": _candidate_ref(
                        corpus_id=corpus_id,
                        unit_type=mention.legal_unit_type,
                        unit=mention.legal_unit,
                    ),
                    "corpus_in_primary_manifest": True,
                }
            )
        )
    mentions = resolved_mentions

    linked = sum(item.corpus_in_primary_manifest for item in mentions)
    material = sum(item.material_relation_explicit for item in mentions)
    return JurisprudenceNormativeRelationRecord(
        document_id=document.document_id,
        source_sha256=document.source_sha256,
        normative_corpus_ids=corpus_ids,
        mentions=mentions,
        mention_count=len(mentions),
        linked_to_primary_corpus_count=linked,
        unresolved_or_external_count=len(mentions) - linked,
        explicit_material_relation_count=material,
    )
