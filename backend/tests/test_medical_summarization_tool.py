import pytest
from unittest.mock import MagicMock, Mock
from sqlalchemy.orm import Session

from services.summarization_service import summarize_patient_report, list_accessible_patients


# ================= FIXTURES =================

@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


@pytest.fixture
def mock_chunk():
    chunk = Mock()
    chunk.section = "Diagnosis"
    chunk.access_scope = "Public"
    chunk.allowed_roles = "Doctor,Nurse"
    chunk.chunk_text = "Patient has diabetes."
    chunk.chunk_index = 1
    return chunk


# ================= SUMMARIZE =================

class TestSummarize:

    def test_admin_blocked(self, mock_db):
        assert "not available" in summarize_patient_report(mock_db, "John", "Admin").lower()

    def test_no_chunks(self, mock_db):
        mock_db.query().filter().filter().filter().order_by().all.return_value = []
        assert "cannot find" in summarize_patient_report(mock_db, "John", "Doctor").lower()

    def test_role_variations(self, mock_db):
        for role in ["doctor", " Doctor ", None, "", "XYZ"]:
            mock_db.query().filter().filter().filter().order_by().all.return_value = []
            result = summarize_patient_report(mock_db, "John", role)
            assert isinstance(result, str)

    def test_patient_variations(self, mock_db):
        for name in ["", None, "@@@", "患者", "A"*1000]:
            mock_db.query().filter().filter().filter().order_by().all.return_value = []
            result = summarize_patient_report(mock_db, name, "Doctor")
            assert isinstance(result, str)

    def test_multiple_chunks(self, mock_db, mock_chunk):
        mock_db.query().filter().filter().filter().order_by().all.return_value = [mock_chunk]*5
        result = summarize_patient_report(mock_db, "John", "Doctor")
        assert isinstance(result, str)

    def test_age_cases(self, mock_db, mock_chunk):
        texts = ["45 year old", "age: 30", "no age info"]
        for t in texts:
            mock_chunk.chunk_text = t
            mock_db.query().filter().filter().filter().order_by().all.return_value = [mock_chunk]
            result = summarize_patient_report(mock_db, "John", "Doctor")
            assert isinstance(result, str)

    def test_exceptions(self, mock_db):
        mock_db.query.side_effect = Exception()
        with pytest.raises(Exception):
            summarize_patient_report(mock_db, "John", "Doctor")


# ================= BULK TESTS (50) =================

@pytest.mark.parametrize("i", range(50))
def test_bulk_patient_summaries_return_string(i, mock_db):
    mock_db.query().filter().filter().filter().order_by().all.return_value = []
    result = summarize_patient_report(mock_db, f"Patient{i}", "Doctor")
    assert isinstance(result, str)


# ================= LIST =================

class TestList:

    def test_valid(self, mock_db):
        mock_db.query().filter().filter().filter().distinct().all.return_value = [("A",), ("B",)]
        assert len(list_accessible_patients(mock_db, "Doctor")) == 2

    def test_admin(self, mock_db):
        assert list_accessible_patients(mock_db, "Admin") == []

    def test_edge_cases(self, mock_db):
        mock_db.query().filter().filter().filter().distinct().all.return_value = [(None,), ("X",)]
        result = list_accessible_patients(mock_db, "Doctor")
        assert "X" in result

    def test_exception(self, mock_db):
        mock_db.query.side_effect = Exception()
        with pytest.raises(Exception):
            list_accessible_patients(mock_db, "Doctor")


# ================= BULK LIST (20) =================

@pytest.mark.parametrize("i", range(20))
def test_bulk_patient_lists_return_entries(i, mock_db):
    data = [(f"P{i}",)]
    mock_db.query().filter().filter().filter().distinct().all.return_value = data
    result = list_accessible_patients(mock_db, "Doctor")
    assert len(result) >= 1