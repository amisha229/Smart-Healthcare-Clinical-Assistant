import os
import sys
import re
from typing import Dict, List, Tuple

# Add the backend directory to the Python path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models.document_chunk import DocumentChunk, Base
from models.patient_report import PatientReport

# Ensure path to documents is correct
DOCS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../documents"))


def _normalize_lines(text_content: str) -> List[str]:
    return [line.strip() for line in text_content.splitlines() if line.strip()]


def _extract_metadata(lines: List[str]) -> Dict[str, str]:
    metadata = {
        "patient_name": "",
        "report_id": "",
        "report_date": "",
        "department": "",
        "hospital": "",
        "attending_doctor": "",
    }

    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key in metadata:
            metadata[key] = value

    return metadata


def _extract_report_sections(text_content: str) -> List[Tuple[str, str, str, str]]:
    """
    Returns tuples: (section_name, section_text, allowed_roles, access_scope)
    """
    sections: List[Tuple[str, str, str, str]] = []

    pattern = r"(SECTION_A_PUBLIC|SECTION_B_PRIVATE)"
    parts = re.split(pattern, text_content)

    # parts format: [prefix, marker, content, marker, content, ...]
    for i in range(1, len(parts), 2):
        marker = parts[i]
        section_text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if not section_text:
            continue

        if marker == "SECTION_A_PUBLIC":
            sections.append(("SECTION_A_PUBLIC", section_text, "Nurse,Doctor", "public"))
        elif marker == "SECTION_B_PRIVATE":
            sections.append(("SECTION_B_PRIVATE", section_text, "Doctor", "private"))

    return sections


def _extract_policy_sections(text_content: str) -> List[Tuple[str, str, str, str]]:
    """
    Parse non-report docs into role-scoped blocks.
    Returns tuples: (section_name, section_text, allowed_roles, access_scope)
    """
    sections: List[Tuple[str, str, str, str]] = []
    marker_pattern = r"(PUBLIC \(Nurse \+ Doctor \+ Admin\)|PRIVATE \(Doctor \+ Admin\)|ADMIN ONLY)"
    parts = re.split(marker_pattern, text_content)

    # Default scope for leading content before explicit markers.
    current_roles = "Nurse,Doctor,Admin"
    current_scope = "public"
    current_section = "General"

    if parts and parts[0].strip():
        sections.append((current_section, parts[0].strip(), current_roles, current_scope))

    for i in range(1, len(parts), 2):
        marker = parts[i].strip() if i < len(parts) else ""
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if not content:
            continue

        if marker == "PUBLIC (Nurse + Doctor + Admin)":
            current_roles, current_scope = "Nurse,Doctor,Admin", "public"
            current_section = "PUBLIC_SECTION"
        elif marker == "PRIVATE (Doctor + Admin)":
            current_roles, current_scope = "Doctor,Admin", "private"
            current_section = "PRIVATE_SECTION"
        elif marker == "ADMIN ONLY":
            current_roles, current_scope = "Admin", "admin"
            current_section = "ADMIN_SECTION"

        sections.append((current_section, content, current_roles, current_scope))

    return sections


def _insert_or_update_report(db: Session, report_meta: Dict[str, str], source_file: str) -> None:
    if not report_meta.get("report_id") or not report_meta.get("patient_name"):
        return

    existing = db.query(PatientReport).filter(PatientReport.report_id == report_meta["report_id"]).first()
    if existing:
        existing.patient_name = report_meta.get("patient_name") or existing.patient_name
        existing.report_date = report_meta.get("report_date") or existing.report_date
        existing.department = report_meta.get("department") or existing.department
        existing.hospital = report_meta.get("hospital") or existing.hospital
        existing.attending_doctor = report_meta.get("attending_doctor") or existing.attending_doctor
        existing.source_file = source_file
        return

    db.add(
        PatientReport(
            report_id=report_meta.get("report_id", ""),
            patient_name=report_meta.get("patient_name", ""),
            report_date=report_meta.get("report_date", ""),
            department=report_meta.get("department", ""),
            hospital=report_meta.get("hospital", ""),
            attending_doctor=report_meta.get("attending_doctor", ""),
            source_file=source_file,
        )
    )


def _ensure_phase1_schema(db: Session) -> None:
    # Validate required Phase 1 columns. We avoid ALTER TABLE here because
    # this app DB user may not be the owner of document_chunks.
    required_columns = {
        "document_type",
        "report_id",
        "patient_name",
        "hospital",
        "attending_doctor",
        "access_scope",
    }

    result = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'document_chunks'
            """
        )
    )
    existing_columns = {row[0] for row in result.fetchall()}
    missing = sorted(required_columns - existing_columns)

    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(
            "Phase 1 schema missing in document_chunks: "
            f"{missing_text}. Please run owner-level SQL migration once."
        )

def ingest_documents():
    print("Setting up database tables if they don't exist...")
    # This creates the table if it's missing, using the models attached to Base
    Base.metadata.create_all(bind=engine)

    print(f"Loading text files from {DOCS_DIR}...")
    loader = DirectoryLoader(DOCS_DIR, glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'})
    documents = loader.load()

    if not documents:
        print("No documents found in the directory.")
        return

    print(f"Loaded {len(documents)} documents.")

    # Split documents into smaller, more granular chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80
    )

    # Initialize the embedding model
    print("Initializing HuggingFace Embedding model (all-MiniLM-L6-v2)...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    print(f"Generating vectors and inserting into PostgreSQL database...")
    db: Session = SessionLocal()
    
    try:
        _ensure_phase1_schema(db)

        # Clear existing data using DELETE to avoid TRUNCATE ownership issues
        db.query(DocumentChunk).delete()
        db.query(PatientReport).delete()
        db.commit()
        
        # Reset the sequence using setval (works with the UPDATE permissions we gave earlier)
        db.execute(text("SELECT setval('document_chunks_chunk_id_seq', 1, false)"))
        db.commit()
        
        inserted_count = 0
        prepared_chunks: List[Document] = []
        
        for doc in documents:
            source_file = os.path.basename(doc.metadata.get("source", "unknown"))
            text_content = doc.page_content

            is_report = "REPORT_START" in text_content and "REPORT_END" in text_content

            if is_report:
                lines = _normalize_lines(text_content)
                report_meta = _extract_metadata(lines)
                _insert_or_update_report(db, report_meta, source_file)

                section_blocks = _extract_report_sections(text_content)
                for section_name, section_text, allowed_roles, access_scope in section_blocks:
                    section_docs = text_splitter.split_documents(
                        [
                            Document(
                                page_content=section_text,
                                metadata={
                                    "source": source_file,
                                    "document_type": "patient_report",
                                    "document_category": "Patient Report",
                                    "section": section_name,
                                    "allowed_roles": allowed_roles,
                                    "access_scope": access_scope,
                                    "report_id": report_meta.get("report_id", ""),
                                    "patient_name": report_meta.get("patient_name", ""),
                                    "hospital": report_meta.get("hospital", ""),
                                    "attending_doctor": report_meta.get("attending_doctor", ""),
                                    "medical_condition": "General",
                                    "content_type": "Report Summary",
                                },
                            )
                        ]
                    )
                    prepared_chunks.extend(section_docs)
                continue

            # Non-report documents (protocols / guidelines)
            category = "General"
            doc_type = "guideline"

            if "Clinical" in source_file:
                category = "Clinical Protocols"
                doc_type = "guideline"
            elif "Treatment" in source_file:
                category = "Treatment Protocols"
                doc_type = "protocol"

            policy_sections = _extract_policy_sections(text_content)
            for section_name, section_text, allowed_roles, access_scope in policy_sections:
                section_docs = text_splitter.split_documents(
                    [
                        Document(
                            page_content=section_text,
                            metadata={
                                "source": source_file,
                                "document_type": doc_type,
                                "document_category": category,
                                "section": section_name,
                                "allowed_roles": allowed_roles,
                                "access_scope": access_scope,
                                "report_id": None,
                                "patient_name": None,
                                "hospital": None,
                                "attending_doctor": None,
                                "medical_condition": "General",
                                "content_type": "General",
                            },
                        )
                    ]
                )
                prepared_chunks.extend(section_docs)

        print(f"Prepared {len(prepared_chunks)} chunks for embedding and insertion.")

        for i, chunk in enumerate(prepared_chunks):
            text_content = chunk.page_content
            chunk_embedding = embeddings.embed_query(text_content)

            new_doc_chunk = DocumentChunk(
                chunk_text=text_content,
                chunk_index=i,
                source_type=chunk.metadata.get("source", "unknown")[:50],
                reference_id=0,
                document_type=chunk.metadata.get("document_type"),
                report_id=chunk.metadata.get("report_id"),
                patient_name=chunk.metadata.get("patient_name"),
                hospital=chunk.metadata.get("hospital"),
                attending_doctor=chunk.metadata.get("attending_doctor"),
                access_scope=chunk.metadata.get("access_scope"),
                allowed_roles=chunk.metadata.get("allowed_roles", "Admin"),
                document_category=chunk.metadata.get("document_category", "General"),
                section=chunk.metadata.get("section", "General"),
                medical_condition=chunk.metadata.get("medical_condition", "General"),
                content_type=chunk.metadata.get("content_type", "General"),
                embedding=chunk_embedding,
            )

            db.add(new_doc_chunk)
            inserted_count += 1

            if inserted_count % 50 == 0:
                db.commit()
                print(f"Inserted {inserted_count}/{len(prepared_chunks)} chunks...")
        
        # Final commit for the remaining chunks
        db.commit()
        print(f"Successfully processed and stored all {inserted_count} text chunks into PostgreSQL!")

    except Exception as e:
        db.rollback()
        print(f"An error occurred during DB insertion: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    ingest_documents()
