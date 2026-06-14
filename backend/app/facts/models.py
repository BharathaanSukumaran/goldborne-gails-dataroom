from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Literal


ReportedOrComputed = Literal["reported", "computed", "unknown"]

MONEY_METRICS = {
    "revenue",
    "ebitda",
    "debt",
    "operating_profit",
    "depreciation",
    "amortisation",
    "impairment",
}


def _reject_float(value: object, field_name: str) -> None:
    if isinstance(value, float):
        raise TypeError(f"{field_name} must be Decimal, int, or str; floats are not allowed")


@dataclass(frozen=True)
class MoneyAmount:
    """Money stored as integer minor units to avoid float rounding."""

    minor_units: int
    currency: str = "GBP"

    @classmethod
    def from_major_units(cls, value: Decimal | int | str, currency: str = "GBP") -> "MoneyAmount":
        _reject_float(value, "money value")
        try:
            decimal_value = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Invalid money value: {value!r}") from exc

        minor_units = int((decimal_value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return cls(minor_units=minor_units, currency=currency)

    def to_major_decimal(self) -> Decimal:
        return Decimal(self.minor_units) / Decimal("100")

    def format(self) -> str:
        symbol = "£" if self.currency == "GBP" else f"{self.currency} "
        return f"{symbol}{self.to_major_decimal():,.2f}"


@dataclass(frozen=True)
class FinancialFact:
    period_end: str
    metric: str
    value: MoneyAmount | None
    unit: str
    reported_or_computed: ReportedOrComputed
    formula: str | None
    source_document_id: str
    source_page: int | None
    source_quote: str
    extraction_confidence: Decimal
    reviewed: bool

    def __post_init__(self) -> None:
        if self.metric in MONEY_METRICS and self.value is not None and not isinstance(self.value, MoneyAmount):
            raise TypeError("money facts must use MoneyAmount integer minor units")
        if isinstance(self.extraction_confidence, float):
            raise TypeError("extraction_confidence must be Decimal, int, or str; floats are not allowed")
        confidence = Decimal(self.extraction_confidence)
        if confidence < Decimal("0") or confidence > Decimal("1"):
            raise ValueError("extraction_confidence must be between 0 and 1")
        object.__setattr__(self, "extraction_confidence", confidence)
        if self.reported_or_computed not in {"reported", "computed", "unknown"}:
            raise ValueError("reported_or_computed must be reported, computed, or unknown")
        if self.reported_or_computed == "computed" and not self.formula:
            raise ValueError("computed facts require a formula")
        if self.reported_or_computed != "unknown" and self.value is None:
            raise ValueError("reported or computed facts require a value")
