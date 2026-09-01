from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.isr import ISRPeriod, ISRTariff, ISRTariffLegalMetadata
from app.domain.normative import NormativeValidityStatus
from calculators.isr import ISRCalculationError, validate_tariff


class ISRTariffRegistryError(ISRCalculationError):
    """Error controlado del registro versionado de tarifas ISR."""


class ISRTariffRegistry:
    """Registro determinístico de tarifas ISR por ejercicio y periodicidad."""

    def __init__(self, tariffs: list[ISRTariff]) -> None:
        if not tariffs:
            raise ISRTariffRegistryError(
                "El registro de tarifas ISR no puede estar vacío."
            )

        by_key: dict[tuple[int, ISRPeriod], ISRTariff] = {}
        for tariff in tariffs:
            validate_tariff(tariff)
            key = (tariff.fiscal_year, tariff.period)
            if key in by_key:
                raise ISRTariffRegistryError(
                    "Existe más de una tarifa ISR para el mismo ejercicio y periodicidad."
                )
            by_key[key] = tariff

        self._by_key = by_key

    def get(self, fiscal_year: int, period: ISRPeriod) -> ISRTariff:
        """Obtiene una tarifa exacta; nunca sustituye silenciosamente otro ejercicio."""
        try:
            return self._by_key[(fiscal_year, period)]
        except KeyError as exc:
            raise ISRTariffRegistryError(
                "No existe una tarifa ISR verificada para el ejercicio y periodicidad "
                "solicitados."
            ) from exc

    def select_for_fiscal_use(
        self,
        fiscal_year: int,
        period: ISRPeriod,
    ) -> ISRTariff:
        """Selecciona tarifa exacta con sustento jurídico temporal verificable."""
        tariff = self.get(fiscal_year, period)
        metadata = require_tariff_legal_metadata(tariff)

        if metadata.validity_status != NormativeValidityStatus.VERIFIED_IN_FORCE:
            raise ISRTariffRegistryError(
                "La tarifa ISR existe en la base controlada, pero su vigencia no está "
                "verificada para uso fiscal."
            )

        if metadata.effective_from is None:
            raise ISRTariffRegistryError(
                "La tarifa ISR no tiene fecha inicial de vigencia verificable para uso "
                "fiscal."
            )

        return tariff

    @property
    def tariffs(self) -> list[ISRTariff]:
        """Devuelve las tarifas en orden estable para auditoría."""
        return [
            self._by_key[key]
            for key in sorted(self._by_key, key=lambda item: (item[0], item[1].value))
        ]


def require_tariff_legal_metadata(tariff: ISRTariff) -> ISRTariffLegalMetadata:
    """Exige metadatos jurídicos antes de promover una tarifa a uso fiscal real."""
    if tariff.legal_metadata is None:
        raise ISRTariffRegistryError(
            "La tarifa ISR no contiene metadatos jurídicos suficientes para uso fiscal "
            "real."
        )
    return tariff.legal_metadata


def load_isr_tariff(path: str | Path) -> ISRTariff:
    """Carga una tarifa JSON bajo el contrato ISRTariff y valida sus rangos."""
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        tariff = ISRTariff.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ISRTariffRegistryError(
            f"No fue posible cargar una tarifa ISR válida desde {source}."
        ) from exc

    validate_tariff(tariff)
    return tariff


def load_isr_tariff_registry(paths: list[str | Path]) -> ISRTariffRegistry:
    """Construye el registro únicamente con tarifas explícitamente proporcionadas."""
    return ISRTariffRegistry([load_isr_tariff(path) for path in paths])
