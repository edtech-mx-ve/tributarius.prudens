from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.domain.primary_rbs_corpus_validation import PrimaryRBSCorpusValidationReport
from app.domain.primary_rbs_deduplication import PrimaryRBSDeduplicationMap
from app.domain.primary_rbs_existing_integration import ExistingRBSRuleIntegrationMap
from app.domain.primary_rbs_inventory import CurrentRBSInventory
from app.domain.rules import RuleDefinition, RuleEvaluationResult, RuleSet
from app.services.rbr_reasoning import infer_rule_facts
from app.services.rule_loader import RuleLoadError, load_rule_set


class ExistingRBSRuleIntegrationError(RuntimeError):
    """Error controlado de integración B.9."""


def load_existing_rbs_rule_integration_map(
    path: Path,
) -> ExistingRBSRuleIntegrationMap:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ExistingRBSRuleIntegrationError(
            f"No existe el mapa de integración B.9: {resolved}"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return ExistingRBSRuleIntegrationMap.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        raise ExistingRBSRuleIntegrationError(
            "El mapa de integración B.9 no es válido."
        ) from exc


def validate_existing_rbs_rule_integration(
    integration_map: ExistingRBSRuleIntegrationMap,
    inventory: CurrentRBSInventory,
    deduplication: PrimaryRBSDeduplicationMap,
    corpus_validation: PrimaryRBSCorpusValidationReport,
) -> None:
    """Valida que B.9 conecte B.1 con B.5/B.8 sin alterar ejecución."""
    integrations = {
        (item.rule_id, item.version): item
        for item in integration_map.integrations
    }
    inventory_rules = {
        (item.rule_id, item.version): item
        for item in inventory.rules
    }
    if set(integrations) != set(inventory_rules):
        raise ExistingRBSRuleIntegrationError(
            "B.9 debe integrar exactamente las 14 reglas inventariadas en B.1."
        )
    if set(integration_map.production_rule_files) != set(
        inventory.production_rule_files
    ):
        raise ExistingRBSRuleIntegrationError(
            "B.9 debe preservar los archivos productivos inventariados en B.1."
        )

    relations = {
        relation.canonical_id: relation for relation in deduplication.relations
    }
    relation_validations = {
        item.relation_id: item for item in corpus_validation.relation_validations
    }
    rule_validations = {
        (item.rule_id, item.version): item
        for item in corpus_validation.existing_rule_validations
    }

    for key, integration in integrations.items():
        inventory_rule = inventory_rules[key]
        if integration.source_file != inventory_rule.source_file:
            raise ExistingRBSRuleIntegrationError(
                f"{integration.rule_id} altera su archivo productivo de B.1."
            )
        if integration.normative_refs != inventory_rule.normative_refs:
            raise ExistingRBSRuleIntegrationError(
                f"{integration.rule_id} altera sus referencias normativas de B.1."
            )

        linked_relations = []
        for relation_id in integration.primary_relation_ids:
            relation = relations.get(relation_id)
            if relation is None:
                raise ExistingRBSRuleIntegrationError(
                    f"{integration.rule_id} referencia una relación B.5 inexistente."
                )
            linked_relations.append(relation)
            relation_validation = relation_validations.get(relation_id)
            if relation_validation is None:
                raise ExistingRBSRuleIntegrationError(
                    f"{relation_id} carece de validación B.8."
                )
            if relation_validation.determination_ready:
                raise ExistingRBSRuleIntegrationError(
                    f"{relation_id} no debe quedar determination_ready en B.9."
                )

        supported_families = {
            family
            for relation in linked_relations
            for family in relation.rbs_families
        }
        if not set(integration.rbs_family_ids) <= supported_families:
            raise ExistingRBSRuleIntegrationError(
                f"{integration.rule_id} introduce familias no sustentadas por B.5."
            )

        supported_sources = {
            source
            for relation in linked_relations
            for source in relation.candidate_normative_sources
        }
        rule_sources = {
            ref.split(":", 1)[0] for ref in integration.normative_refs
        }
        if not rule_sources <= supported_sources:
            raise ExistingRBSRuleIntegrationError(
                f"{integration.rule_id} no queda sustentada por las fuentes B.5 enlazadas."
            )

        validation = rule_validations.get(key)
        if validation is None:
            raise ExistingRBSRuleIntegrationError(
                f"{integration.rule_id} carece de validación de regla en B.8."
            )
        if validation.normative_refs != integration.normative_refs:
            raise ExistingRBSRuleIntegrationError(
                f"{integration.rule_id} altera las referencias validadas en B.8."
            )
        if not validation.corpus_reference_validated:
            raise ExistingRBSRuleIntegrationError(
                f"{integration.rule_id} no tiene referencia validada contra corpus."
            )
        if validation.temporal_validity_confirmed:
            raise ExistingRBSRuleIntegrationError(
                f"{integration.rule_id} no puede presumir vigencia temporal."
            )
        if not validation.requires_case_date_validation:
            raise ExistingRBSRuleIntegrationError(
                f"{integration.rule_id} debe conservar validación temporal por caso."
            )
        if not validation.execution_contract_unchanged:
            raise ExistingRBSRuleIntegrationError(
                f"{integration.rule_id} alteró su contrato de ejecución."
            )


def load_integrated_existing_rule_set(
    production_dir: Path,
    integration_map: ExistingRBSRuleIntegrationMap,
    inventory: CurrentRBSInventory,
    deduplication: PrimaryRBSDeduplicationMap,
    corpus_validation: PrimaryRBSCorpusValidationReport,
) -> RuleSet:
    """Carga las reglas existentes como un único RuleSet sin redefinirlas."""
    validate_existing_rbs_rule_integration(
        integration_map,
        inventory,
        deduplication,
        corpus_validation,
    )
    resolved = production_dir.expanduser().resolve()
    actual_rules: dict[tuple[str, str], RuleDefinition] = {}
    actual_source_files: dict[tuple[str, str], str] = {}

    try:
        for filename in integration_map.production_rule_files:
            rule_set = load_rule_set(resolved / filename)
            for rule in rule_set.rules:
                key = (rule.rule_id, rule.version)
                if key in actual_rules:
                    raise ExistingRBSRuleIntegrationError(
                        f"Regla productiva duplicada: {rule.rule_id}/{rule.version}."
                    )
                actual_rules[key] = rule
                actual_source_files[key] = filename
    except RuleLoadError as exc:
        raise ExistingRBSRuleIntegrationError(
            "No fue posible cargar las reglas productivas para B.9."
        ) from exc

    expected_keys = {
        (item.rule_id, item.version) for item in integration_map.integrations
    }
    if set(actual_rules) != expected_keys:
        raise ExistingRBSRuleIntegrationError(
            "El RuleSet productivo no coincide con las 14 integraciones B.9."
        )

    ordered_rules: list[RuleDefinition] = []
    for inventory_rule in inventory.rules:
        key = (inventory_rule.rule_id, inventory_rule.version)
        rule = actual_rules[key]
        integration = next(
            item
            for item in integration_map.integrations
            if (item.rule_id, item.version) == key
        )
        if actual_source_files[key] != integration.source_file:
            raise ExistingRBSRuleIntegrationError(
                f"{rule.rule_id} proviene de un archivo distinto al registrado en B.9."
            )
        if rule.normative_refs != integration.normative_refs:
            raise ExistingRBSRuleIntegrationError(
                f"{rule.rule_id} difiere de sus referencias normativas B.9."
            )
        if rule.conclusion_code != inventory_rule.conclusion_code:
            raise ExistingRBSRuleIntegrationError(
                f"{rule.rule_id} difiere de la conclusión inventariada en B.1."
            )
        ordered_rules.append(rule)

    return RuleSet(schema_version="1.0", rules=ordered_rules)


def infer_integrated_existing_rule_facts(
    production_dir: Path,
    integration_map: ExistingRBSRuleIntegrationMap,
    inventory: CurrentRBSInventory,
    deduplication: PrimaryRBSDeduplicationMap,
    corpus_validation: PrimaryRBSCorpusValidationReport,
    facts: Mapping[str, Any],
    applicable_normative_refs: set[str] | None = None,
    *,
    max_cycles: int = 20,
) -> RuleEvaluationResult:
    """Ejecuta B.9 exclusivamente mediante el razonador RBR ya existente."""
    rule_set = load_integrated_existing_rule_set(
        production_dir,
        integration_map,
        inventory,
        deduplication,
        corpus_validation,
    )
    return infer_rule_facts(
        rule_set,
        facts,
        applicable_normative_refs,
        max_cycles=max_cycles,
    )
