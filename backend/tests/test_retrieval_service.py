import os
import sys
import pytest
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import services.retrieval_service as rs


class FakeEmbedding:
    def cosine_distance(self, vector):
        return self

    def label(self, name):
        return self


class FakeDocumentChunk:
    embedding = FakeEmbedding()

    class AllowedRolesField:
        def ilike(self, pattern):
            return ("ILIKE", pattern)

    allowed_roles = AllowedRolesField()


def chunk(text="text", roles="Doctor", source="PDF", category="Protocol", section="A"):
    return SimpleNamespace(
        chunk_text=text,
        allowed_roles=roles,
        source_type=source,
        document_category=category,
        section=section,
    )


class FakeQuery:
    def __init__(self, result):
        self.result = result
        self.filter_args = None
        self.limit_value = None

    def order_by(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        self.filter_args = args
        return self

    def limit(self, n):
        self.limit_value = n
        return self

    def all(self):
        return self.result


class FakeDB:
    def __init__(self, unrestricted, role_filtered, fail=False):
        self.unrestricted = unrestricted
        self.role_filtered = role_filtered
        self.fail = fail
        self.calls = 0
        self.closed = False
        self.queries = []

    def query(self, *args, **kwargs):
        if self.fail:
            raise Exception("db failed")
        self.calls += 1
        result = self.unrestricted if self.calls == 1 else self.role_filtered
        q = FakeQuery(result)
        self.queries.append(q)
        return q

    def close(self):
        self.closed = True


def setup_common(monkeypatch, db, embedded=None):
    monkeypatch.setattr(rs, "DocumentChunk", FakeDocumentChunk)
    monkeypatch.setattr(rs, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        type(rs.embeddings),
        "embed_query",
        lambda self, q: embedded if embedded is not None else [0.1, 0.2]
    )


# -------------------------------------------------
# 1) Basic success / formatting / role handling = 20
# -------------------------------------------------

@pytest.mark.parametrize("role", ["Doctor", "doctor", "  doctor  ", None, "DOCTOR"])
def test_success_role_variants(monkeypatch, role):
    db = FakeDB(
        unrestricted=[(chunk("resp care", "Doctor"), 0.20)],
        role_filtered=[(chunk("resp care", "Doctor"), 0.20)]
    )
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context("resp infection", role, top_k=3)
    assert "[Source:" in out
    assert "resp care" in out
    assert db.closed is True


@pytest.mark.parametrize("top_k, expected", [(1, 1), (2, 2), (3, 3), (5, 3)])
def test_returns_top_k_results(monkeypatch, top_k, expected):
    rows = [
        (chunk("t1", "Doctor", section="S1"), 0.10),
        (chunk("t2", "Doctor", section="S2"), 0.11),
        (chunk("t3", "Doctor", section="S3"), 0.12),
    ]
    db = FakeDB(unrestricted=rows, role_filtered=rows)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context("query", "Doctor", top_k=top_k)
    assert out.count("[Source:") == expected


def test_context_format_single(monkeypatch):
    db = FakeDB(
        unrestricted=[(chunk("abc", "Doctor", "PDF", "Guide", "Intro"), 0.2)],
        role_filtered=[(chunk("abc", "Doctor", "PDF", "Guide", "Intro"), 0.2)]
    )
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context("abc", "Doctor")
    assert "[Source: PDF | Category: Guide | Section: Intro | Allowed: Doctor]" in out
    assert out.endswith("abc")


def test_context_format_multiple_joined(monkeypatch):
    rows = [
        (chunk("one", "Doctor", section="A"), 0.10),
        (chunk("two", "Doctor", section="B"), 0.11),
    ]
    db = FakeDB(unrestricted=rows, role_filtered=rows)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context("query", "Doctor", top_k=2)
    assert "one" in out and "two" in out
    assert "\n\n" in out


@pytest.mark.parametrize(
    "query,text",
    [
        ("icu protocol", "icu care protocol"),
        ("nephritis pathway", "nephritis care"),
        ("respiratory infection", "severe respiratory infection management"),
        ("audit logs", "audit logs handling"),
        ("record access", "record access policy"),
    ]
)
def test_success_with_lexical_overlap(monkeypatch, query, text):
    db = FakeDB(
        unrestricted=[(chunk(text, "Doctor"), 0.39)],
        role_filtered=[(chunk(text, "Doctor"), 0.39)]
    )
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context(query, "Doctor")
    assert text in out


@pytest.mark.parametrize("role", ["Admin", "admin", "  admin  ", "ADMIN"])
def test_admin_role_visible_content(monkeypatch, role):
    db = FakeDB(
        unrestricted=[(chunk("governance policy", "Admin"), 0.22)],
        role_filtered=[(chunk("governance policy", "Admin"), 0.22)]
    )
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context("governance policy", role)
    assert "governance policy" in out


# -------------------------------------------------
# 2) Admin-intent restriction paths = 12
# -------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "audit policy",
        "audit logs access",
        "compliance procedure",
        "governance framework",
        "data security policy",
        "access control policy",
        "record access review",
        "modifications audit",
    ]
)
def test_admin_intent_non_admin_restricted(monkeypatch, query):
    unrestricted = [(chunk("admin secret", "Admin"), 0.30)]
    role_filtered = [(chunk("general doctor note", "Doctor"), 0.50)]
    db = FakeDB(unrestricted=unrestricted, role_filtered=role_filtered)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context(query, "Doctor")
    assert out == "ACCESS_RESTRICTED: Relevant content exists but is restricted by your role permissions."


@pytest.mark.parametrize("query", ["audit", "compliance", "policy", "modification"])
def test_admin_intent_nurse_restricted(monkeypatch, query):
    unrestricted = [(chunk("admin only", "Admin"), 0.31)]
    role_filtered = []
    db = FakeDB(unrestricted=unrestricted, role_filtered=role_filtered)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context(query, "Nurse")
    assert out.startswith("ACCESS_RESTRICTED:")


# -------------------------------------------------
# 3) Strong unrestricted match but role mismatch = 10
# -------------------------------------------------

@pytest.mark.parametrize(
    "best_any,best_role",
    [
        (0.20, 0.30),
        (0.25, 0.35),
        (0.30, 0.40),
        (0.35, 0.45),
        (0.40, 0.50),
    ]
)
def test_strong_match_restricted_with_much_weaker_role(monkeypatch, best_any, best_role):
    unrestricted = [(chunk("restricted protocol", "Admin"), best_any)]
    role_filtered = [(chunk("weak doctor item unrelated", "Doctor"), best_role)]
    db = FakeDB(unrestricted=unrestricted, role_filtered=role_filtered)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context("sensitive protocol", "Doctor")
    assert out.startswith("ACCESS_RESTRICTED:")


@pytest.mark.parametrize("role", ["Doctor", "Nurse", "doctor", "nurse", "  Doctor  "])
def test_strong_match_restricted_when_no_role_candidates(monkeypatch, role):
    unrestricted = [(chunk("restricted protocol", "Admin"), 0.22)]
    role_filtered = []
    db = FakeDB(unrestricted=unrestricted, role_filtered=role_filtered)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context("sensitive protocol", role)
    assert out.startswith("ACCESS_RESTRICTED:")


# -------------------------------------------------
# 4) Viable role match avoids restriction = 8
# -------------------------------------------------

@pytest.mark.parametrize(
    "query,text,dist",
    [
        ("nephritis protocol", "nephritis doctor protocol", 0.58),
        ("resp infection", "resp infection care", 0.50),
    ]
)
def test_viable_role_match_prevents_restriction(monkeypatch, query, text, dist):
    unrestricted = [(chunk("admin restricted", "Admin"), 0.30)]
    role_filtered = [(chunk(text, "Doctor"), dist)]
    db = FakeDB(unrestricted=unrestricted, role_filtered=role_filtered)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context(query, "Doctor")
    assert out.startswith("[Source:")
    assert text in out


def test_icu_policy_still_restricted_due_to_admin_bias(monkeypatch):
    unrestricted = [(chunk("admin restricted", "Admin"), 0.30)]
    role_filtered = [(chunk("icu doctor workflow", "Doctor"), 0.55)]
    db = FakeDB(unrestricted=unrestricted, role_filtered=role_filtered)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context("icu policy", "Doctor")
    assert out == "ACCESS_RESTRICTED: Relevant content exists but is restricted by your role permissions."


def test_record_access_doctor_still_restricted_due_to_admin_intent(monkeypatch):
    unrestricted = [(chunk("admin restricted", "Admin"), 0.30)]
    role_filtered = [(chunk("doctor record access note", "Doctor"), 0.60)]
    db = FakeDB(unrestricted=unrestricted, role_filtered=role_filtered)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context("record access doctor", "Doctor")
    assert out == "ACCESS_RESTRICTED: Relevant content exists but is restricted by your role permissions."


@pytest.mark.parametrize(
    "query,text,dist",
    [
        ("icu plan", "icu nurse checklist", 0.55),
        ("infection pathway", "infection nurse pathway", 0.59),
        ("resp care", "resp care nurse", 0.60),
        ("fever protocol", "nurse fever protocol", 0.51),
    ]
)
def test_viable_nurse_match_prevents_restriction(monkeypatch, query, text, dist):
    unrestricted = [(chunk("admin restricted", "Admin"), 0.29)]
    role_filtered = [(chunk(text, "Nurse"), dist)]
    db = FakeDB(unrestricted=unrestricted, role_filtered=role_filtered)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context(query, "Nurse")
    assert text in out


# -------------------------------------------------
# 5) No results / not found / weak match fallback = 10
# -------------------------------------------------

def test_no_role_results_but_unrestricted_exists_means_restricted(monkeypatch):
    db = FakeDB(
        unrestricted=[(chunk("something", "Admin"), 0.5)],
        role_filtered=[]
    )
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context("query", "Doctor")
    assert out.startswith("ACCESS_RESTRICTED:")


def test_no_results_anywhere_returns_no_relevant(monkeypatch):
    db = FakeDB(unrestricted=[], role_filtered=[])
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context("query", "Doctor")
    assert out == "NO_RELEVANT_DATA: No relevant medical protocols found in the knowledge base."


@pytest.mark.parametrize(
    "query,text",
    [
        ("abc xyz", "totally unrelated tokens"),
        ("renal stone", "random nursing workflow"),
        ("heart valve", "general admin note"),
        ("sepsis severe", "mild headache guide"),
    ]
)
def test_weak_role_match_without_overlap_returns_no_relevant(monkeypatch, query, text):
    unrestricted = [(chunk(text, "Doctor"), 0.50)]
    role_filtered = [(chunk(text, "Doctor"), 0.50)]
    db = FakeDB(unrestricted=unrestricted, role_filtered=role_filtered)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context(query, "Doctor")
    assert out == "NO_RELEVANT_DATA: No relevant medical protocols found in the knowledge base."


@pytest.mark.parametrize(
    "query,text",
    [
        ("icu audit", "icu process"),
        ("renal protocol", "renal nursing"),
        ("stroke pathway", "stroke care"),
        ("infection policy", "infection response"),
    ]
)
def test_weak_role_match_with_overlap_still_returns_context(monkeypatch, query, text):
    unrestricted = [(chunk(text, "Doctor"), 0.50)]
    role_filtered = [(chunk(text, "Doctor"), 0.50)]
    db = FakeDB(unrestricted=unrestricted, role_filtered=role_filtered)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context(query, "Doctor")
    assert text in out


# -------------------------------------------------
# 6) Query embedding / DB lifecycle / limits = 6
# -------------------------------------------------

@pytest.mark.parametrize("query", ["fever care", "", "audit logs"])
def test_embed_query_called(monkeypatch, query):
    called = {"q": None}
    db = FakeDB(
        unrestricted=[(chunk("x", "Doctor"), 0.2)],
        role_filtered=[(chunk("x", "Doctor"), 0.2)]
    )
    monkeypatch.setattr(rs, "DocumentChunk", FakeDocumentChunk)
    monkeypatch.setattr(rs, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        type(rs.embeddings),
        "embed_query",
        lambda self, q: called.update(q=q) or [1, 2]
    )

    rs.retrieve_clinical_context(query, "Doctor")
    assert called["q"] == query
    assert db.closed is True


@pytest.mark.parametrize("top_k, limit_expected", [(1, 8), (2, 8), (3, 9)])
def test_limit_uses_max_formula(monkeypatch, top_k, limit_expected):
    rows = [(chunk("x", "Doctor"), 0.2)]
    db = FakeDB(unrestricted=rows, role_filtered=rows)
    setup_common(monkeypatch, db)
    rs.retrieve_clinical_context("query", "Doctor", top_k=top_k)
    assert db.queries[0].limit_value == limit_expected
    assert db.queries[1].limit_value == limit_expected


# -------------------------------------------------
# 7) Exception handling and close = 4
# -------------------------------------------------

def test_db_query_exception_returns_error_message(monkeypatch):
    db = FakeDB(unrestricted=[], role_filtered=[], fail=True)
    setup_common(monkeypatch, db)
    out = rs.retrieve_clinical_context("query", "Doctor")
    assert out == "An error occurred while retrieving medical knowledge."
    assert db.closed is True


def test_embed_exception_propagates_before_db_creation(monkeypatch):
    monkeypatch.setattr(
        type(rs.embeddings),
        "embed_query",
        lambda self, q: (_ for _ in ()).throw(Exception("embed fail"))
    )
    with pytest.raises(Exception, match="embed fail"):
        rs.retrieve_clinical_context("query", "Doctor")


def test_close_called_on_success(monkeypatch):
    db = FakeDB(
        unrestricted=[(chunk("x", "Doctor"), 0.2)],
        role_filtered=[(chunk("x", "Doctor"), 0.2)]
    )
    setup_common(monkeypatch, db)
    rs.retrieve_clinical_context("query", "Doctor")
    assert db.closed is True


def test_close_called_on_handled_exception(monkeypatch):
    db = FakeDB(unrestricted=[], role_filtered=[], fail=True)
    setup_common(monkeypatch, db)
    rs.retrieve_clinical_context("query", "Doctor")
    assert db.closed is True