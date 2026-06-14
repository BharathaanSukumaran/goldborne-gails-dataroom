from __future__ import annotations

from decimal import Decimal

from .models import FinancialFact, MoneyAmount
from .repository import FinancialFactsRepository


EBITDA_COMPONENTS = ("operating_profit", "depreciation", "amortisation")
EBITDA_FORMULA = "operating_profit + depreciation + amortisation"


def resolve_ebitda(repository: FinancialFactsRepository, period_end: str) -> FinancialFact:
    reported = repository.get_fact("ebitda", period_end, usable_only=True)
    if reported and reported.reported_or_computed == "reported":
        return reported

    components = [repository.get_fact(metric, period_end, usable_only=True) for metric in EBITDA_COMPONENTS]
    if all(component and component.value for component in components):
        assert all(component is not None and component.value is not None for component in components)
        total = sum(component.value.minor_units for component in components if component and component.value)
        component_source_ids = [component.source_document_id for component in components if component]
        source_document_id = (
            component_source_ids[0]
            if len(set(component_source_ids)) == 1
            else ", ".join(component_source_ids)
        )
        return FinancialFact(
            workspace_id=components[0].workspace_id if components[0] else "gails-limited",
            period_end=period_end,
            metric="ebitda",
            value=MoneyAmount(minor_units=total, currency="GBP"),
            unit="minor_units",
            reported_or_computed="computed",
            formula=EBITDA_FORMULA,
            source_document_id=source_document_id,
            source_page=None,
            source_quote="Computed from structured financial_facts components.",
            extraction_confidence=Decimal("1"),
            reviewed=True,
            used_in_answers=True,
        )

    return FinancialFact(
        workspace_id="gails-limited",
        period_end=period_end,
        metric="ebitda",
        value=None,
        unit="minor_units",
        reported_or_computed="unavailable",
        formula=None,
        source_document_id="financial_facts",
        source_page=None,
        source_quote="EBITDA was not reported and the required components were incomplete.",
        extraction_confidence=Decimal("1"),
        reviewed=False,
        used_in_answers=False,
    )
