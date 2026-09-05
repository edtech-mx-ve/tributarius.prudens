from __future__ import annotations

import importlib
import inspect
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from app.domain.hybrid_contract_baseline import (
    HybridContractAudit,
    HybridContractBaseline,
    HybridContractCheck,
    HybridContractKind,
)

_DEFAULT_BASELINE_PATH = (
    Path(__file__).resolve().parents[1] / "resources" / "hybrid_contract_baseline.json"
)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class HybridContractBaselineError(ValueError):
    """El baseline F.1 es inválido o el runtime rompió un contrato preservado."""


def load_hybrid_contract_baseline(
    path: Path | None = None,
) -> HybridContractBaseline:
    baseline_path = path or _DEFAULT_BASELINE_PATH
    try:
        return HybridContractBaseline.model_validate_json(
            baseline_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValidationError) as exc:
        raise HybridContractBaselineError("El baseline contractual F.1 es inválido.") from exc


def _resolve(import_path: str) -> Any:
    module_name, separator, symbol_path = import_path.partition(":")
    if not separator:
        raise HybridContractBaselineError(f"Import path F.1 inválido: {import_path}")
    try:
        value: Any = importlib.import_module(module_name)
    except ImportError as exc:
        raise HybridContractBaselineError(
            f"No se pudo importar el módulo contractual {module_name}."
        ) from exc
    for part in symbol_path.split("."):
        try:
            value = getattr(value, part)
        except AttributeError as exc:
            raise HybridContractBaselineError(
                f"No existe el símbolo contractual {import_path}."
            ) from exc
    return value


def _audit_model(spec_import_path: str, required_fields: list[str]) -> tuple[bool, str]:
    symbol = _resolve(spec_import_path)
    if not inspect.isclass(symbol) or not issubclass(symbol, BaseModel):
        return False, "El símbolo ya no es un modelo Pydantic."
    current_fields = set(symbol.model_fields)
    missing = [field for field in required_fields if field not in current_fields]
    if missing:
        return False, "Campos eliminados: " + ", ".join(missing)
    return True, f"Campos preservados: {len(required_fields)}."


def _audit_enum(spec_import_path: str, required_values: list[str]) -> tuple[bool, str]:
    symbol = _resolve(spec_import_path)
    if not inspect.isclass(symbol) or not issubclass(symbol, Enum):
        return False, "El símbolo ya no es un enum."
    current_values = {str(item.value) for item in symbol}
    missing = [value for value in required_values if value not in current_values]
    if missing:
        return False, "Valores eliminados: " + ", ".join(missing)
    return True, f"Valores preservados: {len(required_values)}."


def _audit_callable(
    spec_import_path: str,
    required_parameters: list[str],
) -> tuple[bool, str]:
    symbol = _resolve(spec_import_path)
    if not callable(symbol):
        return False, "El símbolo contractual dejó de ser invocable."
    parameters = list(inspect.signature(symbol).parameters)
    missing = [name for name in required_parameters if name not in parameters]
    if missing:
        return False, "Parámetros eliminados: " + ", ".join(missing)
    positions = [parameters.index(name) for name in required_parameters]
    if positions != sorted(positions):
        return False, "El orden relativo de los parámetros preservados cambió."
    return True, f"Parámetros preservados: {len(required_parameters)}."


def _runtime_checks(baseline: HybridContractBaseline) -> list[HybridContractCheck]:
    """Audita compatibilidad del baseline, permitiendo activaciones aditivas posteriores.

    F.1 congeló el contrato de producción de E como punto de partida. F.11 puede
    activar Llama real siempre que el mock histórico siga disponible sólo como
    doble de pruebas y los contratos públicos preservados no sean reemplazados.
    """

    runtime_factory = (_PROJECT_ROOT / "app" / "services" / "runtime_factory.py").read_text(
        encoding="utf-8"
    )
    checks: list[HybridContractCheck] = []

    mock_module = _PROJECT_ROOT / "llm" / "providers" / "mock.py"
    f11_real_runtime = (
        "build_real_llama_provider(settings)" in runtime_factory
        and "provider_is_test_double=False" in runtime_factory
        and "MockLLMProvider" not in runtime_factory
    )
    mock_contract_preserved = mock_module.is_file()
    checks.append(
        HybridContractCheck(
            contract_id="F1-RUNTIME-MOCK",
            component="runtime_factory",
            preserved=mock_contract_preserved and f11_real_runtime,
            detail=(
                "El mock histórico se conserva para tests y F.11 usa Llama real en runtime."
                if mock_contract_preserved and f11_real_runtime
                else "F.11 no preservó la separación test-mock/runtime-real exigida."
            ),
        )
    )

    baseline_label = baseline.runtime.explanation_runtime
    label_preserved_or_evolved = (
        f'explanation_runtime="{baseline_label}"' in runtime_factory
        or 'explanation_runtime=f"llama_cpp_real:' in runtime_factory
        or (
            'f"llama_cpp_real:' in runtime_factory
            and "explanation_runtime=explanation_runtime" in runtime_factory
        )
    )
    checks.append(
        HybridContractCheck(
            contract_id="F1-RUNTIME-LABEL",
            component="WebHybridRunner",
            preserved=label_preserved_or_evolved,
            detail=(
                "La etiqueta heredada permanece compatible o evolucionó aditivamente a F.11."
                if label_preserved_or_evolved
                else "El runtime de explicación perdió una identidad trazable."
            ),
        )
    )

    orchestrator_call = runtime_factory.split("orchestrator = HybridOrchestrator(", 1)
    legal_hypothesis_configured = False
    if len(orchestrator_call) == 2:
        constructor_body = orchestrator_call[1].split(")\n", 1)[0]
        legal_hypothesis_configured = "legal_hypothesis_service=" in constructor_body
    expected_hypothesis = baseline.runtime.legal_hypothesis_service_configured
    checks.append(
        HybridContractCheck(
            contract_id="F1-RUNTIME-HYPOTHESIS",
            component="runtime_factory",
            preserved=legal_hypothesis_configured == expected_hypothesis,
            detail=(
                "La hipótesis LLM heredada sigue opcional; F.11 usa el canal H1 aditivo."
                if not legal_hypothesis_configured
                else "El runtime activó indebidamente la hipótesis heredada."
            ),
        )
    )

    real_provider_markers = (
        "LlamaCppProvider(",
        "build_real_llama_provider(settings)",
    )
    real_llm_active = any(marker in runtime_factory for marker in real_provider_markers)
    real_llm_compatible = (
        real_llm_active
        and f11_real_runtime
        or real_llm_active == baseline.runtime.real_llm_active
    )
    checks.append(
        HybridContractCheck(
            contract_id="F1-RUNTIME-REAL-LLM",
            component="runtime_factory",
            preserved=real_llm_compatible,
            detail=(
                "F.11 activó Llama real como evolución autorizada posterior a F.1."
                if real_llm_active
                else "El estado LLM coincide con el baseline F.1."
            ),
        )
    )
    return checks


def audit_current_hybrid_contracts(
    baseline: HybridContractBaseline | None = None,
) -> HybridContractAudit:
    """Audita contratos actuales sin ejecutar ni reordenar el razonamiento jurídico."""
    active_baseline = baseline or load_hybrid_contract_baseline()
    checks: list[HybridContractCheck] = []
    for spec in active_baseline.contracts:
        if spec.kind is HybridContractKind.PYDANTIC_MODEL:
            preserved, detail = _audit_model(spec.import_path, spec.required_fields)
        elif spec.kind is HybridContractKind.ENUM:
            preserved, detail = _audit_enum(spec.import_path, spec.required_values)
        else:
            preserved, detail = _audit_callable(
                spec.import_path,
                spec.required_parameters,
            )
        checks.append(
            HybridContractCheck(
                contract_id=spec.contract_id,
                component=spec.component,
                preserved=preserved,
                detail=detail,
            )
        )

    runtime_checks = _runtime_checks(active_baseline)
    all_preserved = all(item.preserved for item in [*checks, *runtime_checks])
    return HybridContractAudit(
        baseline_commit=active_baseline.baseline_commit,
        checks=checks,
        runtime_checks=runtime_checks,
        all_contracts_preserved=all_preserved,
    )
