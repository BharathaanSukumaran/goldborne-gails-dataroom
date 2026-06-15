from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from backend.app.facts.charges import (
    ChargeFact,
    SourceCitation,
    build_charges_answer,
    load_charge_facts_json,
)
from backend.app.facts.ownership import (
    ManagementChangeFact,
    OfficerFact,
    PscFact,
    build_current_directors_answer,
    build_ownership_answer,
    build_recent_changes_answer,
)


def citation(source_id: str = "companies_house_charge_register_profile_06055393") -> SourceCitation:
    return SourceCitation(
        source_id=source_id,
        title="Companies House register extract",
        url=f"https://find-and-update.company-information.service.gov.uk/company/06055393/{source_id}",
        page=1,
        quote="Structured extract used for test citation.",
    )


def test_charges_answer_lists_holders_status_and_citations() -> None:
    charge = ChargeFact(
        charge_id="060553930001",
        created_on=date(2011, 7, 1),
        registered_on=date(2011, 7, 8),
        status="outstanding",
        persons_entitled=("Example Bank PLC",),
        classification="debenture",
        description="Fixed and floating charge over assets.",
        field_review={"description": True},
        citations=(citation(),),
    )

    answer = build_charges_answer([charge]).to_dict()

    assert answer["answer_type"] == "structured_charges"
    assert "Example Bank PLC" in answer["answer"]
    assert "outstanding" in answer["answer"]
    assert answer["missing_information"] == []
    assert answer["citations"][0]["source_id"] == "companies_house_charge_register_profile_06055393"
    assert answer["facts_used"][0]["persons_entitled"] == ["Example Bank PLC"]


def test_charge_facts_require_citations_and_holders() -> None:
    with pytest.raises(ValueError, match="source citation"):
        ChargeFact(
            charge_id="missing-citation",
            created_on=None,
            registered_on=None,
            status="unknown",
            persons_entitled=("Example Bank PLC",),
        )

    with pytest.raises(ValueError, match="holder/person entitled"):
        ChargeFact(
            charge_id="missing-holder",
            created_on=None,
            registered_on=None,
            status="unknown",
            persons_entitled=(),
            citations=(citation(),),
        )


def test_empty_charges_answer_reports_unknown_not_no_charges() -> None:
    answer = build_charges_answer([]).to_dict()

    assert answer["confidence"] == "low"
    assert "cannot identify registered charges" in answer["answer"]
    assert "Companies House charge register facts" in answer["missing_information"]


def test_unreviewed_charge_fields_are_not_answerable() -> None:
    charge = ChargeFact(
        charge_id="0605 5393 0006",
        short_code="0006",
        created_on=date(2022, 6, 6),
        registered_on=None,
        status="outstanding",
        persons_entitled=("Glas Trust Corporation Limited",),
        description="Candidate description that has not been reviewed.",
        secured_assets="Candidate all-assets wording that has not been reviewed.",
        citations=(citation("ch-charge-0006"),),
    )

    assert charge.is_field_answerable("holder") is True
    assert charge.reviewed_value("holder") == ("Glas Trust Corporation Limited",)
    assert charge.is_field_answerable("description") is False
    assert charge.reviewed_value("description") is None
    assert charge.is_field_answerable("securedAssets") is False

    answer = build_charges_answer([charge]).to_dict()
    assert "Candidate description" not in answer["answer"]


def test_charge_facts_json_has_field_level_review_gates() -> None:
    facts = load_charge_facts_json(Path("backend/data/charge_facts.json"))

    charge_0006 = next(fact for fact in facts if fact.short_code == "0006")
    assert charge_0006.reviewed_value("holder") == ("Glas Trust Corporation Limited",)
    assert charge_0006.reviewed_value("createdDate") == "2022-06-06"
    assert charge_0006.reviewed_value("description") is None
    assert charge_0006.reviewed_value("securedAssets") is None
    assert charge_0006.field_review["description"] is False
    assert charge_0006.field_review["securedAssets"] is False


def test_current_directors_filters_resigned_officers_and_cites_sources() -> None:
    active_director = OfficerFact(
        name="Jane Director",
        role="Director",
        appointed_on=date(2024, 1, 3),
        status="active",
        occupation="Company director",
        citations=(citation("companies_house_officers_06055393"),),
    )
    resigned_director = OfficerFact(
        name="John Former",
        role="Director",
        appointed_on=date(2020, 2, 1),
        status="resigned",
        resigned_on=date(2023, 12, 31),
        citations=(citation("companies_house_officers_06055393"),),
    )

    answer = build_current_directors_answer([resigned_director, active_director]).to_dict()

    assert answer["answer_type"] == "structured_directors"
    assert "Jane Director" in answer["answer"]
    assert "John Former" not in answer["answer"]
    assert answer["citations"][0]["source_id"] == "companies_house_officers_06055393"


def test_ownership_answer_uses_active_psc_facts() -> None:
    active_psc = PscFact(
        name="Example Holdings Limited",
        kind="corporate",
        notified_on=date(2022, 6, 1),
        natures_of_control=(
            "Ownership of shares - more than 75%",
            "Voting rights - more than 75%",
        ),
        citations=(citation("companies_house_psc_register_06055393"),),
    )
    ceased_psc = PscFact(
        name="Old Owner Limited",
        kind="corporate",
        notified_on=date(2019, 1, 1),
        ceased_on=date(2022, 5, 31),
        natures_of_control=("Ownership of shares - more than 50% but less than 75%",),
        citations=(citation("companies_house_psc_register_06055393"),),
    )

    answer = build_ownership_answer([ceased_psc, active_psc]).to_dict()

    assert answer["answer_type"] == "structured_ownership"
    assert "Example Holdings Limited" in answer["answer"]
    assert "Old Owner Limited" not in answer["answer"]
    assert answer["facts_used"][0]["natures_of_control"] == [
        "Ownership of shares - more than 75%",
        "Voting rights - more than 75%",
    ]


def test_recent_changes_answer_orders_latest_first_and_limits_results() -> None:
    changes = [
        ManagementChangeFact(
            change_type="appointment",
            effective_on=date(2025, 1, 5),
            subject_name="New Director",
            subject_role="Director",
            details="Appointment filed at Companies House.",
            citations=(citation("companies_house_filing_history_appointments_resignations_06055393"),),
        ),
        ManagementChangeFact(
            change_type="psc_ceased",
            effective_on=date(2024, 4, 2),
            subject_name="Old Owner Limited",
            subject_role="PSC",
            details="PSC ceased to be registrable.",
            citations=(citation("companies_house_psc_register_06055393"),),
        ),
    ]

    answer = build_recent_changes_answer(changes, limit=1).to_dict()

    assert answer["answer_type"] == "structured_recent_changes"
    assert "New Director" in answer["answer"]
    assert "Old Owner Limited" not in answer["answer"]
    assert answer["facts_used"][0]["change_type"] == "appointment"
