import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models.document_chunk import DocumentChunk as DocumentChunkModel

# Treatment documents directory
TREATMENT_DOCS_DIR = Path(__file__).parent.parent.parent / "documents" / "treatments"


def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

def parse_treatment_document(file_path: str) -> Dict:
    """
    Parse a treatment document and extract structured sections.
    Returns dictionary with disease info and patient cases.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract disease metadata (between DISEASE_START and disease overview)
    disease_match = re.search(r'disease_name:\s*(.+?)(?:\n|$)', content)
    disease_code_match = re.search(r'disease_code:\s*(.+?)(?:\n|$)', content)
    icd_code_match = re.search(r'icd_code:\s*(.+?)(?:\n|$)', content)
    severity_match = re.search(r'severity_spectrum:\s*(.+?)(?:\n|$)', content)
    treatment_tags_match = re.search(r'treatment_tags:\s*(.+?)(?:\n|$)', content, re.DOTALL)
    
    disease_name = disease_match.group(1).strip() if disease_match else "Unknown Disease"
    disease_code = disease_code_match.group(1).strip() if disease_code_match else ""
    icd_code = icd_code_match.group(1).strip() if icd_code_match else ""
    severity_spectrum = severity_match.group(1).strip() if severity_match else ""
    
    treatment_tags = ""
    if treatment_tags_match:
        tags_text = treatment_tags_match.group(1).strip()
        treatment_tags = tags_text.split('\n')[0].replace(',', ', ').strip()
    
    # Extract disease overview section
    overview_match = re.search(
        r'SECTION_A_PUBLIC\s*\n(.*?)(?=---|\nPATIENT_CASE_|\nSECTION_B_)',
        content,
        re.DOTALL
    )
    disease_overview = overview_match.group(1).strip() if overview_match else ""
    
    # Extract all patient cases
    patient_cases = []
    case_pattern = r'PATIENT_CASE_(\d+)\s*\n(.*?)(?=\n---\n|PATIENT_CASE_|SECTION_B_|DISEASE_END)'
    for match in re.finditer(case_pattern, content, re.DOTALL):
        case_num = match.group(1)
        case_content = match.group(2)
        patient_cases.append({
            'case_id': case_num,
            'content': case_content
        })
    
    # Extract comparative analysis
    comparative_match = re.search(
        r'SECTION_B_PRIVATE.*?(?=---|\nDECISION_FRAMEWORK|SECTION_C_)',
        content,
        re.DOTALL
    )
    comparative_analysis = comparative_match.group(0).strip() if comparative_match else ""
    
    # Extract decision framework
    framework_match = re.search(
        r'DECISION_FRAMEWORK FOR CLINICIANS(.*?)(?=---|\nSECTION_C_|DISEASE_END)',
        content,
        re.DOTALL
    )
    decision_framework = framework_match.group(1).strip() if framework_match else ""
    
    # Extract evidence section
    evidence_match = re.search(
        r'SECTION_C_TREATMENT_EVIDENCE(.*?)(?=---|\nDISEASE_END)',
        content,
        re.DOTALL
    )
    evidence_section = evidence_match.group(1).strip() if evidence_match else ""
    
    return {
        'disease_name': disease_name,
        'disease_code': disease_code,
        'icd_code': icd_code,
        'severity_spectrum': severity_spectrum,
        'treatment_tags': treatment_tags,
        'overview': disease_overview,
        'patient_cases': patient_cases,
        'comparative_analysis': comparative_analysis,
        'decision_framework': decision_framework,
        'evidence_section': evidence_section
    }


def extract_patient_details(case_content: str) -> Dict:
    """
    Extract structured details from a patient case.
    """
    patient_id_match = re.search(r'case_id:\s*(.+?)(?:\n|$)', case_content)
    diagnosis_match = re.search(r'primary_diagnosis:\s*(.+?)(?:\n|$)', case_content)
    severity_match = re.search(r'baseline_.*?_score.*?:\s*([0-9.]+).*?(?:\n|$)', case_content)
    
    # Extract symptoms section
    symptoms_match = re.search(
        r'Clinical Presentation - Symptoms\n(.*?)(?=Clinical Context|Treatment Regimen)',
        case_content,
        re.DOTALL
    )
    symptoms = symptoms_match.group(1).strip() if symptoms_match else ""
    
    # Extract treatment regimen
    treatment_match = re.search(
        r'Treatment Regimen\n(.*?)(?=Rationale|Treatment Advantages)',
        case_content,
        re.DOTALL
    )
    treatment_regimen = treatment_match.group(1).strip() if treatment_match else ""
    
    # Extract advantages
    advantages_match = re.search(
        r'Treatment Advantages \(Pros\)(.*?)(?=Treatment Disadvantages)',
        case_content,
        re.DOTALL
    )
    advantages = advantages_match.group(1).strip() if advantages_match else ""
    
    # Extract risks/disadvantages
    risks_match = re.search(
        r'Treatment Disadvantages \(Cons\)(.*?)(?=Clinical Outcome|Assessment)',
        case_content,
        re.DOTALL
    )
    risks = risks_match.group(1).strip() if risks_match else ""
    
    # Extract outcomes
    outcome_match = re.search(
        r'(?:Clinical Outcome|Assessment:)(.*?)(?=$|\n---)',
        case_content,
        re.DOTALL
    )
    outcomes = outcome_match.group(1).strip() if outcome_match else ""
    
    return {
        'patient_id': patient_id_match.group(1).strip() if patient_id_match else "",
        'diagnosis': diagnosis_match.group(1).strip() if diagnosis_match else "",
        'symptoms': symptoms,
        'treatment_regimen': treatment_regimen,
        'advantages': advantages,
        'risks': risks,
        'outcomes': outcomes
    }


def create_treatment_chunks(parsed_data: Dict) -> List[Dict]:
    """
    Create individual chunks from parsed treatment document.
    Each chunk is searchable and embedable.
    """
    chunks = []
    disease_name = parsed_data['disease_name']
    disease_code = parsed_data['disease_code']
    icd_code = parsed_data['icd_code']
    treatment_tags = parsed_data['treatment_tags']
    
    # Chunk 1: Disease Overview
    if parsed_data['overview']:
        chunks.append({
            'chunk_type': 'section',
            'section': 'OVERVIEW',
            'text': parsed_data['overview'][:2000],  # Limit chunk size
            'disease_name': disease_name,
            'disease_code': disease_code,
            'icd_code': icd_code,
            'patient_case_id': None,
            'severity_stage': None,
            'treatment_regimen': None,
            'key_advantages': None,
            'key_risks': None,
            'clinical_outcomes': None,
            'content_type': 'Overview',
            'treatment_tags': treatment_tags
        })
    
    # Chunk 2-4: Patient Cases (3 cases per disease)
    for idx, case in enumerate(parsed_data['patient_cases']):
        patient_details = extract_patient_details(case['content'])
        
        # Infer severity from case order (assumption: escalating severity)
        severity_stages = ['mild', 'moderate', 'severe']
        severity = severity_stages[min(idx, len(severity_stages)-1)]
        
        chunks.append({
            'chunk_type': 'patient_case',
            'section': f'PATIENT_CASE_{case["case_id"]}',
            'text': case['content'][:2000],
            'disease_name': disease_name,
            'disease_code': disease_code,
            'icd_code': icd_code,
            'patient_case_id': patient_details['patient_id'],
            'severity_stage': severity,
            'treatment_regimen': patient_details['treatment_regimen'][:500] if patient_details['treatment_regimen'] else None,
            'key_advantages': patient_details['advantages'][:300] if patient_details['advantages'] else None,
            'key_risks': patient_details['risks'][:300] if patient_details['risks'] else None,
            'clinical_outcomes': patient_details['outcomes'][:300] if patient_details['outcomes'] else None,
            'content_type': 'Treatment Case',
            'treatment_tags': treatment_tags
        })
    
    # Chunk 5: Comparative Analysis
    if parsed_data['comparative_analysis']:
        chunks.append({
            'chunk_type': 'section',
            'section': 'COMPARATIVE_ANALYSIS',
            'text': parsed_data['comparative_analysis'][:2000],
            'disease_name': disease_name,
            'disease_code': disease_code,
            'icd_code': icd_code,
            'patient_case_id': None,
            'severity_stage': None,
            'treatment_regimen': None,
            'key_advantages': None,
            'key_risks': None,
            'clinical_outcomes': None,
            'content_type': 'Comparison',
            'treatment_tags': treatment_tags
        })
    
    # Chunk 6: Decision Framework
    if parsed_data['decision_framework']:
        chunks.append({
            'chunk_type': 'section',
            'section': 'DECISION_FRAMEWORK',
            'text': parsed_data['decision_framework'][:2000],
            'disease_name': disease_name,
            'disease_code': disease_code,
            'icd_code': icd_code,
            'patient_case_id': None,
            'severity_stage': None,
            'treatment_regimen': None,
            'key_advantages': None,
            'key_risks': None,
            'clinical_outcomes': None,
            'content_type': 'Clinical Decision',
            'treatment_tags': treatment_tags
        })
    
    # Chunk 7: Evidence Section
    if parsed_data['evidence_section']:
        chunks.append({
            'chunk_type': 'section',
            'section': 'EVIDENCE_BASED_OUTCOMES',
            'text': parsed_data['evidence_section'][:2000],
            'disease_name': disease_name,
            'disease_code': disease_code,
            'icd_code': icd_code,
            'patient_case_id': None,
            'severity_stage': None,
            'treatment_regimen': None,
            'key_advantages': None,
            'key_risks': None,
            'clinical_outcomes': None,
            'content_type': 'Evidence',
            'treatment_tags': treatment_tags
        })
    
    return chunks


def ingest_treatment_documents(db: Session):
    """
    Main ingestion function: 
    1. Parse all treatment documents
    2. Create chunks
    3. Generate embeddings
    4. Store in database
    """
    treatment_files = list(TREATMENT_DOCS_DIR.glob("TREATMENT_*.txt"))
    
    if not treatment_files:
        print(f"❌ No treatment files found in {TREATMENT_DOCS_DIR}")
        return
    
    print(f"📄 Found {len(treatment_files)} treatment documents")

    force_ingestion = os.getenv("FORCE_TREATMENT_INGESTION", "false").strip().lower() in {"1", "true", "yes", "on"}
    existing_count = db.query(DocumentChunkModel).filter(
        DocumentChunkModel.document_type == 'treatment'
    ).count()

    if existing_count > 0 and not force_ingestion:
        print("Treatment data already exists. Skipping treatment ingestion.")
        return

    embedding_model = get_embedding_model()
    
    # First, delete existing treatment chunks (fresh ingestion)
    if existing_count > 0:
        print(f"🗑️ Removing {existing_count} existing treatment chunks...")
        db.query(DocumentChunkModel).filter(
            DocumentChunkModel.document_type == 'treatment'
        ).delete()
        db.commit()
    
    total_chunks_stored = 0
    
    for file_path in treatment_files:
        print(f"\n📖 Processing: {file_path.name}")
        
        try:
            # Parse document
            parsed_data = parse_treatment_document(str(file_path))
            print(f"   ✓ Disease: {parsed_data['disease_name']}")
            print(f"   ✓ Found {len(parsed_data['patient_cases'])} patient cases")
            
            # Create chunks
            chunks = create_treatment_chunks(parsed_data)
            print(f"   ✓ Created {len(chunks)} chunks")
            
            # Store chunks in database
            for chunk_idx, chunk in enumerate(chunks):
                try:
                    # Generate embedding
                    embedding_vector = embedding_model.encode(chunk['text'])
                    
                    # Create database record
                    db_chunk = DocumentChunkModel(
                        chunk_text=chunk['text'],
                        chunk_index=chunk_idx,
                        source_type='treatment_document',
                        document_type='treatment',
                        document_category='Treatment Comparison',
                        section=chunk['section'],
                        content_type=chunk['content_type'],
                        access_scope='public',
                        allowed_roles='Nurse,Doctor,Admin',
                        
                        # Treatment-specific fields
                        disease_name=chunk['disease_name'],
                        disease_code=chunk['disease_code'],
                        icd_code=chunk['icd_code'],
                        patient_case_id=chunk['patient_case_id'],
                        severity_stage=chunk['severity_stage'],
                        treatment_regimen=chunk['treatment_regimen'],
                        key_advantages=chunk['key_advantages'],
                        key_risks=chunk['key_risks'],
                        clinical_outcomes=chunk['clinical_outcomes'],
                        treatment_tags=chunk['treatment_tags'],
                        
                        # Embedding
                        embedding=embedding_vector
                    )
                    
                    db.add(db_chunk)
                    total_chunks_stored += 1
                    
                except Exception as e:
                    print(f"   ⚠️ Error storing chunk {chunk_idx}: {e}")
                    db.rollback()
                    continue
            
            # Commit all chunks for this document
            db.commit()
            print(f"   ✅ Stored {len(chunks)} chunks to database")
            
        except Exception as e:
            print(f"   ❌ Error processing file: {e}")
            continue
    
    print(f"\n{'='*60}")
    print(f"✅ INGESTION COMPLETE")
    print(f"   Total chunks stored: {total_chunks_stored}")
    print(f"   Documents processed: {len(treatment_files)}")
    print(f"{'='*60}")


def main():
    """
    Entry point for treatment document ingestion.
    """
    print("🚀 Starting Treatment Document Ingestion Pipeline")
    print(f"📁 Treatment documents directory: {TREATMENT_DOCS_DIR}")
    
    # Create session
    db = SessionLocal()
    
    try:
        ingest_treatment_documents(db)
    except Exception as e:
        print(f"❌ Fatal error during ingestion: {e}")
    finally:
        db.close()
        print("📊 Database session closed")


if __name__ == "__main__":
    main()
