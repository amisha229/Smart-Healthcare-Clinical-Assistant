import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.treatment_comparison_tool import (
    _cache_treatment_result,
    _build_query_focus_instruction,
    _check_treatment_cache,
    _get_role_guidance,
    _sanitize_treatment_output,
    compare_treatments,
)


@pytest.fixture
def db():
    return MagicMock(spec=Session)


def test_cache_hit(db):
    entry = MagicMock()
    entry.response = "cached"
    db.query().filter().first.return_value = entry
    assert _check_treatment_cache("q", db) == "cached"


def test_cache_miss(db):
    db.query().filter().first.return_value = None
    assert _check_treatment_cache("q", db) is None


def test_cache_error_returns_none(db):
    db.query.side_effect = Exception("db error")
    assert _check_treatment_cache("q", db) is None


@pytest.mark.parametrize(
    "query",
    [
        "",
        "x",
        "compare insulin",
        "compare metformin vs insulin",
        "with newline\ntext",
        "with\ttab",
        " " * 10,
        "x" * 200,
    ],
)
def test_cache_query_shapes_return_none_on_miss(db, query):
    db.query().filter().first.return_value = None
    assert _check_treatment_cache(query, db) is None


@pytest.mark.parametrize(
    "role",
    ["Doctor", "Nurse", "Admin", "doctor", "", None],
)
def test_role_guidance(role):
    out = _get_role_guidance(role)
    assert isinstance(out, str)
    assert len(out) > 0


@pytest.mark.parametrize(
    "role, expected_token",
    [
        ("Doctor", "clinical"),
        ("doctor", "clinical"),
        ("Nurse", "nursing"),
        ("nurse", "nursing"),
        ("Admin", "administrative"),
        ("admin", "administrative"),
        (None, "clinical"),
        ("", "clinical"),
        ("  Nurse  ", "nursing"),
        ("unknown", "clinical"),
    ],
)
def test_role_guidance_content(role, expected_token):
    out = _get_role_guidance(role).lower()
    assert expected_token in out


def test_cache_store_success(db):
    _cache_treatment_result("q", "resp", "src", db)
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_cache_store_failure_rolls_back(db):
    db.add.side_effect = Exception("add fail")
    _cache_treatment_result("q", "resp", "src", db)
    db.rollback.assert_called_once()


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("A<br>B", "A\nB"),
        ("A<BR/>B", "A\nB"),
        ("<p>Hello</p>", "Hello"),
        ("<div>X</div>\n\n\nY", "X\n\nY"),
        ("No tags", "No tags"),
        ("", ""),
        ("   spaced   ", "spaced"),
        ("<table><tr><td>T</td></tr></table>", "T"),
    ],
)
def test_sanitize_output(raw, expected):
    assert _sanitize_treatment_output(raw) == expected


@pytest.mark.parametrize(
    "query, expected_contains",
    [
        ("compare side effect burden", "side-effect burden"),
        ("monitoring requirements", "monitoring needs"),
        ("mild vs severe strategy", "mild versus severe"),
        ("cost comparison", "cost/resource"),
        ("tabular format", "compact markdown tables"),
        (
            "side effects and monitoring",
            "side-effect burden",
        ),
        ("plain query", "Answer the exact comparison asked"),
        ("resource affordability", "cost/resource"),
        ("follow-up lab cadence", "monitoring needs"),
        ("adverse profile", "side-effect burden"),
        ("table output", "compact markdown tables"),
        ("format please", "compact markdown tables"),
    ],
)
def test_build_query_focus_instruction(query, expected_contains):
    out = _build_query_focus_instruction(query)
    assert expected_contains in out


@patch("services.treatment_comparison_tool._cache_treatment_result")
@patch("services.treatment_comparison_tool._generate_treatment_comparison", return_value="final comparison")
@patch("services.treatment_comparison_tool._retrieve_treatment_context", return_value="clinical context")
def test_compare_success(mock_ctx, mock_gen, mock_cache, db):
    result = compare_treatments(
        query="compare options",
        disease_name="Type 2 Diabetes Mellitus",
        user_role="Doctor",
        db=db,
    )
    assert result == "final comparison"
    mock_ctx.assert_called_once()
    mock_gen.assert_called_once()
    mock_cache.assert_called_once()


@pytest.mark.parametrize(
    "query,disease,user_role",
    [
        ("compare oral agents", "Type 2 Diabetes Mellitus", "Doctor"),
        ("compare insulin regimens", "Type 1 Diabetes Mellitus", "Doctor"),
        ("monitoring burden", "Hypertension", "Doctor"),
        ("cost and efficacy", "Asthma", "Doctor"),
        ("adverse effects", "COPD", "Doctor"),
        ("compare options", "Chronic Kidney Disease", "Doctor"),
        ("mild vs severe", "Pneumonia", "Doctor"),
        ("tabular summary", "Heart Failure", "Doctor"),
        ("compare options", "Sepsis", "Doctor"),
        ("best regimen", "Tuberculosis", "Doctor"),
        ("compare options", "Migraine", "Nurse"),
        ("care implications", "Epilepsy", "Nurse"),
        ("simplified comparison", "Hypothyroidism", "Nurse"),
        ("compare treatments", "Hyperthyroidism", "Nurse"),
        ("resource planning", "GERD", "Admin"),
        ("policy impact", "Anemia", "Admin"),
        ("compare therapy", "Osteoarthritis", "Doctor"),
        ("long term plans", "Rheumatoid Arthritis", "Doctor"),
        ("burden profile", "Psoriasis", "Doctor"),
        ("efficacy summary", "Dyslipidemia", "Doctor"),
    ],
)
@patch("services.treatment_comparison_tool._cache_treatment_result")
@patch("services.treatment_comparison_tool._generate_treatment_comparison", return_value="ok")
@patch("services.treatment_comparison_tool._retrieve_treatment_context", return_value="clinical context")
def test_compare_success_matrix(mock_ctx, mock_gen, mock_cache, query, disease, user_role, db):
    result = compare_treatments(query=query, disease_name=disease, user_role=user_role, db=db)
    assert result == "ok"
    mock_ctx.assert_called_once()
    mock_gen.assert_called_once_with(query, "clinical context", user_role)
    mock_cache.assert_called_once()


@patch("services.treatment_comparison_tool._retrieve_treatment_context", return_value="ACCESS_RESTRICTED: blocked")
def test_compare_access_restricted(mock_ctx, db):
    result = compare_treatments(
        query="compare options",
        disease_name="Type 2 Diabetes Mellitus",
        user_role="Nurse",
        db=db,
    )
    assert "not accessible" in result.lower()


@pytest.mark.parametrize(
    "role",
    ["Doctor", "Nurse", "Admin", "doctor"],
)
@patch("services.treatment_comparison_tool._retrieve_treatment_context", return_value="ACCESS_RESTRICTED: blocked")
def test_compare_access_restricted_matrix(mock_ctx, role, db):
    result = compare_treatments(
        query="compare options",
        disease_name="Type 2 Diabetes Mellitus",
        user_role=role,
        db=db,
    )
    assert "not accessible" in result.lower()


@patch("services.treatment_comparison_tool._retrieve_treatment_context", return_value="NO_RELEVANT_DATA: none")
def test_compare_no_data(mock_ctx, db):
    result = compare_treatments(
        query="compare options",
        disease_name="Unknown Disease",
        user_role="Doctor",
        db=db,
    )
    assert "no treatment comparison data found" in result.lower()


@pytest.mark.parametrize(
    "no_data_signal",
    [
        "NO_RELEVANT_DATA: none",
        "No relevant treatment protocols found",
        "NO_RELEVANT_DATA: missing context",
        "No relevant",
    ],
)
@patch("services.treatment_comparison_tool._retrieve_treatment_context")
def test_compare_no_data_matrix(mock_ctx, no_data_signal, db):
    mock_ctx.return_value = no_data_signal
    result = compare_treatments(
        query="compare options",
        disease_name="Unknown Disease",
        user_role="Doctor",
        db=db,
    )
    assert "no treatment comparison data found" in result.lower()


@patch("services.treatment_comparison_tool._retrieve_treatment_context", side_effect=Exception("boom"))
def test_compare_handles_exception(mock_ctx, db):
    result = compare_treatments(
        query="compare options",
        disease_name="Type 2 Diabetes Mellitus",
        user_role="Doctor",
        db=db,
    )
    assert "error generating treatment comparison" in result.lower()


@pytest.mark.parametrize(
    "error_msg",
    ["boom", "db failed", "unexpected", "timeout"],
)
@patch("services.treatment_comparison_tool._retrieve_treatment_context")
def test_compare_handles_exception_matrix(mock_ctx, error_msg, db):
    mock_ctx.side_effect = Exception(error_msg)
    result = compare_treatments(
        query="compare options",
        disease_name="Type 2 Diabetes Mellitus",
        user_role="Doctor",
        db=db,
    )
    assert "error generating treatment comparison" in result.lower()


@patch("services.treatment_comparison_tool.SessionLocal")
@patch("services.treatment_comparison_tool._cache_treatment_result")
@patch("services.treatment_comparison_tool._generate_treatment_comparison", return_value="ok")
@patch("services.treatment_comparison_tool._retrieve_treatment_context", return_value="context")
def test_compare_creates_and_closes_db_when_not_provided(mock_ctx, mock_gen, mock_cache, mock_session_local):
    fake_db = MagicMock(spec=Session)
    mock_session_local.return_value = fake_db

    result = compare_treatments(
        query="compare options",
        disease_name="Type 2 Diabetes Mellitus",
        user_role="Doctor",
        db=None,
    )

    assert result == "ok"
    fake_db.close.assert_called_once()


@patch("services.treatment_comparison_tool._cache_treatment_result")
@patch("services.treatment_comparison_tool._generate_treatment_comparison", return_value="done")
@patch("services.treatment_comparison_tool._retrieve_treatment_context", return_value="context")
def test_compare_passes_correct_cache_key(mock_ctx, mock_gen, mock_cache, db):
    result = compare_treatments(
        query="compare options",
        disease_name="Type 2 Diabetes Mellitus",
        user_role="Doctor",
        db=db,
    )
    assert result == "done"
    cache_query = mock_cache.call_args.args[0]
    assert cache_query == "Compare treatments for Type 2 Diabetes Mellitus: compare options"