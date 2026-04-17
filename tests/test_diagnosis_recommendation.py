import sys
import os
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import services.diagnosis_recommendation as dr


# =========================================================
# 1) _is_symptom_query tests -> 30 cases
# =========================================================

@pytest.mark.parametrize("query", [
    "fever and cough",
    "headache and nausea",
    "possible diagnosis",
    "what could this be",
    "likely condition",
    "possible conditions",
    "diagnosis",
    "symptoms of infection",
    "signs of infection",
    "chest pain and shortness of breath",
    "polyuria polydipsia",
    "weight loss and fatigue",
    "fever+cough",
    "some random text +",
    "sore throat and chills",
    "vomiting diarrhea",
    "fatigue?",
    "headache!",
    "vomiting.",
    "rash over body",
])
def test_is_symptom_query_true_cases(query):
    assert dr._is_symptom_query(query) is True


@pytest.mark.parametrize("query", [
    "",
    "   ",
    "hello doctor",
    "please help me with billing",
    "medication refill",
    "exercise advice",
    "I need a referral",
    "chest x-ray report",
    "appointment booking",
    "insurance claim",
])
def test_is_symptom_query_false_cases(query):
    assert dr._is_symptom_query(query) is False


def test_is_symptom_query_true_cough_substring():
    assert dr._is_symptom_query("coughing heavily") is True


def test_is_symptom_query_true_dizziness_phrase():
    assert dr._is_symptom_query("dizziness since morning") is True


def test_is_symptom_query_true_pain_substring_edge():
    # because code checks substring "pain"
    assert dr._is_symptom_query("paint on wall") is True


def test_is_symptom_query_true_none_plus_like_not_needed():
    assert dr._is_symptom_query("A+B") is True


def test_is_symptom_query_true_multiword_symptom():
    assert dr._is_symptom_query("shortness of breath") is True


def test_is_symptom_query_false_sign_without_s():
    assert dr._is_symptom_query("sign") is False


def test_is_symptom_query_true_mixed_case_intent():
    assert dr._is_symptom_query("Likely Condition") is True


def test_is_symptom_query_true_whitespace_trim():
    assert dr._is_symptom_query("   fever   ") is True


# =========================================================
# 2) _check_cache tests -> 5 cases
# =========================================================

def test_check_cache_returns_response_when_entry_exists():
    fake_entry = MagicMock()
    fake_entry.response = "cached diagnosis"

    fake_filter = MagicMock()
    fake_filter.first.return_value = fake_entry

    fake_query = MagicMock()
    fake_query.filter.return_value = fake_filter

    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    result = dr._check_cache("diagnosis::fever and cough", fake_db)
    assert result == "cached diagnosis"


def test_check_cache_returns_none_when_no_entry():
    fake_filter = MagicMock()
    fake_filter.first.return_value = None

    fake_query = MagicMock()
    fake_query.filter.return_value = fake_filter

    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    result = dr._check_cache("diagnosis::fever and cough", fake_db)
    assert result is None


def test_check_cache_returns_none_on_db_query_exception():
    fake_db = MagicMock()
    fake_db.query.side_effect = Exception("db error")

    result = dr._check_cache("diagnosis::fever and cough", fake_db)
    assert result is None


def test_check_cache_calls_query_once():
    fake_filter = MagicMock()
    fake_filter.first.return_value = None

    fake_query = MagicMock()
    fake_query.filter.return_value = fake_filter

    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    dr._check_cache("diagnosis::fever", fake_db)
    fake_db.query.assert_called_once()


def test_check_cache_calls_first_once():
    fake_filter = MagicMock()
    fake_filter.first.return_value = None

    fake_query = MagicMock()
    fake_query.filter.return_value = fake_filter

    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    dr._check_cache("diagnosis::fever", fake_db)
    fake_filter.first.assert_called_once()


# =========================================================
# 3) _save_cache tests -> 4 cases
# =========================================================

def test_save_cache_commits_successfully(monkeypatch):
    class FakeCache:
        def __init__(self, **kwargs):
            self.query = kwargs["query"]
            self.knowledge_type = kwargs["knowledge_type"]
            self.response = kwargs["response"]
            self.source = kwargs["source"]
            self.expires_at = kwargs["expires_at"]

    monkeypatch.setattr(dr, "MedicalKnowledgeCache", FakeCache)
    fake_db = MagicMock()

    dr._save_cache("diagnosis::fever", "result text", fake_db)

    fake_db.add.assert_called_once()
    fake_db.commit.assert_called_once()
    fake_db.rollback.assert_not_called()


def test_save_cache_rolls_back_on_commit_exception(monkeypatch):
    class FakeCache:
        def __init__(self, **kwargs):
            self.query = kwargs["query"]
            self.knowledge_type = kwargs["knowledge_type"]
            self.response = kwargs["response"]
            self.source = kwargs["source"]
            self.expires_at = kwargs["expires_at"]

    monkeypatch.setattr(dr, "MedicalKnowledgeCache", FakeCache)
    fake_db = MagicMock()
    fake_db.commit.side_effect = Exception("commit failed")

    dr._save_cache("diagnosis::fever", "result text", fake_db)

    fake_db.add.assert_called_once()
    fake_db.commit.assert_called_once()
    fake_db.rollback.assert_called_once()


def test_save_cache_rolls_back_on_add_exception(monkeypatch):
    class FakeCache:
        def __init__(self, **kwargs):
            self.query = kwargs["query"]
            self.knowledge_type = kwargs["knowledge_type"]
            self.response = kwargs["response"]
            self.source = kwargs["source"]
            self.expires_at = kwargs["expires_at"]

    monkeypatch.setattr(dr, "MedicalKnowledgeCache", FakeCache)
    fake_db = MagicMock()
    fake_db.add.side_effect = Exception("add failed")

    dr._save_cache("diagnosis::fever", "result text", fake_db)

    fake_db.commit.assert_not_called()
    fake_db.rollback.assert_called_once()


def test_save_cache_uses_expected_metadata(monkeypatch):
    captured = {}

    class FakeCache:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(dr, "MedicalKnowledgeCache", FakeCache)
    fake_db = MagicMock()

    dr._save_cache("diagnosis::abc", "hello", fake_db)

    assert captured["query"] == "diagnosis::abc"
    assert captured["knowledge_type"] == "diagnosis_recommendation"
    assert captured["response"] == "hello"
    assert captured["source"] == "RAG + Groq LLM"


# =========================================================
# 4) _generate_diagnosis_response tests -> 3 cases
# =========================================================

def test_generate_diagnosis_response_returns_llm_content(monkeypatch):
    fake_response = MagicMock()
    fake_response.content = "Generated diagnosis output"

    fake_chain = MagicMock()
    fake_chain.invoke.return_value = fake_response

    fake_prompt = MagicMock()
    fake_prompt.__or__.return_value = fake_chain

    monkeypatch.setattr(dr.ChatPromptTemplate, "from_messages", lambda messages: fake_prompt)

    result = dr._generate_diagnosis_response("fever and cough", "clinical context")

    assert result == "Generated diagnosis output"
    fake_chain.invoke.assert_called_once_with({
        "context": "clinical context",
        "question": "fever and cough"
    })


def test_generate_diagnosis_response_passes_question_and_context(monkeypatch):
    captured = {}

    class FakeChain:
        def invoke(self, payload):
            captured.update(payload)
            return type("Resp", (), {"content": "ok"})()

    class FakePrompt:
        def __or__(self, other):
            return FakeChain()

    monkeypatch.setattr(dr.ChatPromptTemplate, "from_messages", lambda messages: FakePrompt())

    result = dr._generate_diagnosis_response("headache", "ctx123")

    assert result == "ok"
    assert captured["question"] == "headache"
    assert captured["context"] == "ctx123"


def test_generate_diagnosis_response_raises_if_invoke_fails(monkeypatch):
    class FakeChain:
        def invoke(self, payload):
            raise Exception("invoke failed")

    class FakePrompt:
        def __or__(self, other):
            return FakeChain()

    monkeypatch.setattr(dr.ChatPromptTemplate, "from_messages", lambda messages: FakePrompt())

    with pytest.raises(Exception, match="invoke failed"):
        dr._generate_diagnosis_response("fever", "ctx")


# =========================================================
# 5) recommend_diagnosis tests -> 28 cases
# =========================================================

def test_recommend_diagnosis_rejects_patient_role():
    result = dr.recommend_diagnosis("fever and cough", user_role="Patient", db=MagicMock())
    assert result == "Diagnosis recommendation tool is available only for Doctor role."


def test_recommend_diagnosis_rejects_nurse_role():
    result = dr.recommend_diagnosis("fever and cough", user_role="Nurse", db=MagicMock())
    assert result == "Diagnosis recommendation tool is available only for Doctor role."


def test_recommend_diagnosis_rejects_dr_role():
    result = dr.recommend_diagnosis("fever and cough", user_role="Dr", db=MagicMock())
    assert result == "Diagnosis recommendation tool is available only for Doctor role."


def test_recommend_diagnosis_accepts_lowercase_doctor(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: "cached result")

    result = dr.recommend_diagnosis("fever and cough", user_role="doctor", db=MagicMock())
    assert result == "cached result"


def test_recommend_diagnosis_accepts_whitespace_doctor(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: "cached result")

    result = dr.recommend_diagnosis("fever and cough", user_role="  doctor  ", db=MagicMock())
    assert result == "cached result"


def test_recommend_diagnosis_defaults_none_role_to_doctor(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: "cached result")

    result = dr.recommend_diagnosis("fever and cough", user_role=None, db=MagicMock())
    assert result == "cached result"


def test_recommend_diagnosis_rejects_non_symptom_query(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: False)

    result = dr.recommend_diagnosis("hello", user_role="Doctor", db=MagicMock())
    assert result == "This is not related to a symptom-based diagnosis recommendation question."


def test_recommend_diagnosis_returns_cached_result(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: "cached result")

    result = dr.recommend_diagnosis("fever and cough", user_role="Doctor", db=MagicMock())
    assert result == "cached result"


def test_recommend_diagnosis_does_not_retrieve_when_cache_hit(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: "cached result")

    called = {"retrieve": False}

    def fake_retrieve(*args, **kwargs):
        called["retrieve"] = True
        return "ctx"

    monkeypatch.setattr(dr, "retrieve_clinical_context", fake_retrieve)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())

    assert result == "cached result"
    assert called["retrieve"] is False


def test_recommend_diagnosis_access_restricted(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: "ACCESS_RESTRICTED: restricted")

    result = dr.recommend_diagnosis("fever and cough", user_role="Doctor", db=MagicMock())
    assert result == "Relevant diagnostic context exists but is restricted."


def test_recommend_diagnosis_no_relevant_data(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: "NO_RELEVANT_DATA: nothing")

    result = dr.recommend_diagnosis("fever and cough", user_role="Doctor", db=MagicMock())
    assert result == "No relevant symptom-based diagnostic context found in the knowledge base."


def test_recommend_diagnosis_cleans_br_and_tags(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: "clinical context")
    monkeypatch.setattr(dr, "_generate_diagnosis_response", lambda q, c: "<div>Line1<br>Line2</div>")

    saved = {}
    monkeypatch.setattr(dr, "_save_cache", lambda query, response, db: saved.update({"query": query, "response": response}))

    result = dr.recommend_diagnosis("fever and cough", user_role="Doctor", db=MagicMock())

    assert result == "Line1\nLine2"
    assert saved["response"] == "Line1\nLine2"


def test_recommend_diagnosis_cleans_uppercase_br(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: "clinical context")
    monkeypatch.setattr(dr, "_generate_diagnosis_response", lambda q, c: "A<BR>B")

    monkeypatch.setattr(dr, "_save_cache", lambda *args, **kwargs: None)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())
    assert result == "A\nB"


def test_recommend_diagnosis_collapses_multiple_blank_lines(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: "clinical context")
    monkeypatch.setattr(dr, "_generate_diagnosis_response", lambda q, c: "A\n\n\n\nB")

    monkeypatch.setattr(dr, "_save_cache", lambda *args, **kwargs: None)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())
    assert result == "A\n\nB"


def test_recommend_diagnosis_strips_outer_html(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: "clinical context")
    monkeypatch.setattr(dr, "_generate_diagnosis_response", lambda q, c: "<p>Hello</p>")

    monkeypatch.setattr(dr, "_save_cache", lambda *args, **kwargs: None)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())
    assert result == "Hello"


def test_recommend_diagnosis_preserves_plain_text(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: "clinical context")
    monkeypatch.setattr(dr, "_generate_diagnosis_response", lambda q, c: "Plain text output")

    monkeypatch.setattr(dr, "_save_cache", lambda *args, **kwargs: None)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())
    assert result == "Plain text output"


def test_recommend_diagnosis_passes_doctor_to_retrieval(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)

    captured = {}

    def fake_retrieve(query, user_role, top_k):
        captured["query"] = query
        captured["user_role"] = user_role
        captured["top_k"] = top_k
        return "clinical context"

    monkeypatch.setattr(dr, "retrieve_clinical_context", fake_retrieve)
    monkeypatch.setattr(dr, "_generate_diagnosis_response", lambda q, c: "ok")
    monkeypatch.setattr(dr, "_save_cache", lambda *args, **kwargs: None)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())

    assert result == "ok"
    assert captured["query"] == "fever"
    assert captured["user_role"] == "Doctor"
    assert captured["top_k"] == 6


def test_recommend_diagnosis_passes_context_to_generation(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: "ctx-xyz")

    captured = {}

    def fake_generate(query, context):
        captured["query"] = query
        captured["context"] = context
        return "generated"

    monkeypatch.setattr(dr, "_generate_diagnosis_response", fake_generate)
    monkeypatch.setattr(dr, "_save_cache", lambda *args, **kwargs: None)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())

    assert result == "generated"
    assert captured["query"] == "fever"
    assert captured["context"] == "ctx-xyz"


def test_recommend_diagnosis_calls_save_cache(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: "clinical context")
    monkeypatch.setattr(dr, "_generate_diagnosis_response", lambda q, c: "final output")

    captured = {}

    def fake_save(query, response, db):
        captured["query"] = query
        captured["response"] = response

    monkeypatch.setattr(dr, "_save_cache", fake_save)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())

    assert result == "final output"
    assert captured["query"] == "diagnosis::fever"
    assert captured["response"] == "final output"


def test_recommend_diagnosis_normalizes_cache_key(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)

    captured = {}

    def fake_check_cache(query, db):
        captured["cache_key"] = query
        return "cached"

    monkeypatch.setattr(dr, "_check_cache", fake_check_cache)

    result = dr.recommend_diagnosis("  Fever And COUGH  ", user_role="Doctor", db=MagicMock())

    assert result == "cached"
    assert captured["cache_key"] == "diagnosis::fever and cough"


def test_recommend_diagnosis_handles_generation_exception(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: "clinical context")

    def fake_generate(query, context):
        raise Exception("LLM failed")

    monkeypatch.setattr(dr, "_generate_diagnosis_response", fake_generate)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())
    assert result == "Error generating diagnosis recommendation: LLM failed"


def test_recommend_diagnosis_handles_retrieval_exception(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)

    def fake_retrieve(query, user_role, top_k):
        raise Exception("retrieval failed")

    monkeypatch.setattr(dr, "retrieve_clinical_context", fake_retrieve)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())
    assert result == "Error generating diagnosis recommendation: retrieval failed"


def test_recommend_diagnosis_handles_non_string_context(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: None)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())
    assert "Error generating diagnosis recommendation:" in result


def test_recommend_diagnosis_creates_internal_db_if_none(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: "cached internal")

    fake_db = MagicMock()
    monkeypatch.setattr(dr, "SessionLocal", lambda: fake_db)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=None)

    assert result == "cached internal"


def test_recommend_diagnosis_closes_internal_db(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: "cached internal")

    fake_db = MagicMock()
    monkeypatch.setattr(dr, "SessionLocal", lambda: fake_db)

    dr.recommend_diagnosis("fever", user_role="Doctor", db=None)

    fake_db.close.assert_called_once()


def test_recommend_diagnosis_does_not_close_external_db(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: "cached external")

    fake_db = MagicMock()
    dr.recommend_diagnosis("fever", user_role="Doctor", db=fake_db)

    fake_db.close.assert_not_called()


def test_recommend_diagnosis_returns_cached_html_unchanged(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: "<div>cached</div>")

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())
    assert result == "<div>cached</div>"


def test_recommend_diagnosis_with_empty_query_and_mocked_symptom(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: "cached result")

    result = dr.recommend_diagnosis("", user_role="Doctor", db=MagicMock())
    assert result == "cached result"


def test_recommend_diagnosis_save_cache_exception_does_not_break(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: "ctx")
    monkeypatch.setattr(dr, "_generate_diagnosis_response", lambda q, c: "done")

    def fake_save(query, response, db):
        raise Exception("save broke")

    monkeypatch.setattr(dr, "_save_cache", fake_save)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())
    assert result == "Error generating diagnosis recommendation: save broke"


def test_recommend_diagnosis_result_strip_whitespace(monkeypatch):
    monkeypatch.setattr(dr, "_is_symptom_query", lambda q: True)
    monkeypatch.setattr(dr, "_check_cache", lambda q, db: None)
    monkeypatch.setattr(dr, "retrieve_clinical_context", lambda q, user_role, top_k: "ctx")
    monkeypatch.setattr(dr, "_generate_diagnosis_response", lambda q, c: "   <b>Hello</b>   ")
    monkeypatch.setattr(dr, "_save_cache", lambda *args, **kwargs: None)

    result = dr.recommend_diagnosis("fever", user_role="Doctor", db=MagicMock())
    assert result == "Hello"