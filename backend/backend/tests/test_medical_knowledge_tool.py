import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from services.medical_knowledge_service import (
    _check_cache,
    _augment_with_rag,
    _cache_result,
    get_medical_knowledge
)

# ---------- FIXTURE ----------
@pytest.fixture
def db():
    return MagicMock(spec=Session)

# ---------- CACHE ----------
def test_cache_hit(db):
    obj = Mock()
    obj.response = "cached"
    db.query().filter().first.return_value = obj
    assert _check_cache("q", "drug", db) == "cached"

def test_cache_miss(db):
    db.query().filter().first.return_value = None
    assert _check_cache("q", "drug", db) is None

@pytest.mark.parametrize("q", ["", "test", "x"*1000])
def test_cache_edge(db, q):
    db.query().filter().first.return_value = None
    assert _check_cache(q, "drug", db) is None

# ---------- RAG ----------
@patch("services.medical_knowledge_service.retrieve_clinical_context")
@patch("services.medical_knowledge_service.ChatPromptTemplate.from_messages")
def test_rag_added(mock_prompt, mock_rag):
    mock_rag.return_value = "context"

    fake_response = Mock()
    fake_response.content = "refined answer"
    fake_chain = Mock()
    fake_chain.invoke.return_value = fake_response
    fake_prompt = Mock()
    fake_prompt.__or__ = Mock(return_value=fake_chain)
    mock_prompt.return_value = fake_prompt

    res = _augment_with_rag("q", "drug", "base", "Doctor")
    assert res == "refined answer"

@patch("services.medical_knowledge_service.retrieve_clinical_context")
def test_rag_not_added(mock_rag):
    mock_rag.return_value = "No relevant"
    assert _augment_with_rag("q", "drug", "base", "Doctor") == "base"

# ---------- CACHE STORE ----------
def test_cache_store(db):
    db.query().filter().first.return_value = None
    _cache_result("q", "drug", "resp", "src", db)
    db.add.assert_called_once()
    db.commit.assert_called_once()

# ---------- MAIN ----------
@patch("services.medical_knowledge_service._query_groq_for_knowledge")
@patch("services.medical_knowledge_service._check_cache")
def test_main_basic(mock_cache, mock_q, db):
    mock_cache.return_value = None
    mock_q.return_value = "resp"
    res = get_medical_knowledge("q", "drug", db, False)
    assert res["response"] == "resp"

@patch("services.medical_knowledge_service._check_cache")
def test_main_cache(mock_cache, db):
    mock_cache.return_value = "cached"
    res = get_medical_knowledge("q", "drug", db)
    assert res["source"] == "cache"

@patch("services.medical_knowledge_service._query_groq_for_knowledge")
@patch("services.medical_knowledge_service._augment_with_rag")
@patch("services.medical_knowledge_service._check_cache")
def test_main_rag(mock_cache, mock_aug, mock_q, db):
    mock_cache.return_value = None
    mock_q.return_value = "resp"
    mock_aug.return_value = "ctx-refined"
    res = get_medical_knowledge("q", "drug", db, True)
    assert "ctx-refined" == res["response"]

# ---------- BULK ----------
@pytest.mark.parametrize("i", range(40))  # 40 tests
@patch("services.medical_knowledge_service._query_groq_for_knowledge")
@patch("services.medical_knowledge_service._check_cache")
def test_bulk_queries_return_response(mock_cache, mock_q, db, i):
    mock_cache.return_value = None
    mock_q.return_value = f"resp{i}"
    res = get_medical_knowledge(f"q{i}", "drug", db, False)
    assert res["response"] == f"resp{i}"

# ---------- EDGE ----------
@pytest.mark.parametrize("q", ["", "test", " "*5, "x"*1000])
@patch("services.medical_knowledge_service._query_groq_for_knowledge")
@patch("services.medical_knowledge_service._check_cache")
def test_edge_queries_return_dict(mock_cache, mock_q, db, q):
    mock_cache.return_value = None
    mock_q.return_value = "resp"
    res = get_medical_knowledge(q, "drug", db, False)
    assert isinstance(res, dict)

# ---------- TYPES ----------
@pytest.mark.parametrize("kt", ["drug", "disease", "symptom"])
@patch("services.medical_knowledge_service._query_groq_for_knowledge")
@patch("services.medical_knowledge_service._check_cache")
def test_knowledge_types_preserved(mock_cache, mock_q, db, kt):
    mock_cache.return_value = None
    mock_q.return_value = "resp"
    res = get_medical_knowledge("q", kt, db, False)
    assert res["knowledge_type"] == kt

# ---------- EXTRA ----------
@pytest.mark.parametrize("i", range(20))  # 20 tests
@patch("services.medical_knowledge_service._query_groq_for_knowledge")
@patch("services.medical_knowledge_service._check_cache")
def test_additional_queries_return_ok(mock_cache, mock_q, db, i):
    mock_cache.return_value = None
    mock_q.return_value = "ok"
    assert get_medical_knowledge("q", "drug", db)["response"] == "ok"