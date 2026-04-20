# Smart Healthcare Clinical Assistant - Test Cases Documentation

## Table of Contents
1. [Documents Available](#documents-available)
2. [5 Core Tools Overview](#5-core-tools-overview)
3. [Test Cases for Each Tool](#test-cases-for-each-tool)

---

## Documents Available

### Text Files (.txt)
1. **Clinical_Protocols.txt** - PUBLIC (Nurse + Doctor + Admin)
   - Emergency Department Initial Stabilization protocols
   - General Medicine Ward Care procedures
   - Respiratory Care Supportive Management
   - Infectious Disease Management
   - Surgical Care Post-operative protocols
   - ICU Critical Care protocols

2. **Treatment_Protocols.txt** - PUBLIC (Nurse + Doctor + Admin)
   - Emergency Care guidelines
   - General Medicine treatment procedures
   - Respiratory Support protocols
   - Medication administration standards
   - Patient monitoring requirements

### PDF Files
1. **medical_report_updated.pdf** - Medical report documentation
2. **treatment_comparison_tool.pdf** - Treatment comparison guidelines
3. **treatment_guidelines_updated.pdf** - Updated treatment guidelines

### Patient Report Files (reports/ directory)
1. MR-2024-00312_Arjun_Sharma.txt
2. MR-2024-00389_Meera_Nair.txt
3. MR-2024-00421_Rohan_Desai.txt
4. MR-2024-00478_Sunita_Rao.txt
5. MR-2024-00519_Farhan_Sheikh.txt
6. MR-2024-00553_Lakshmi_Venkataraman.txt
7. MR-2024-00645_Ananya_Krishnan.txt
8. MR-2024-00698_Deepak_Malhotra.txt
9. MR-2024-00734_Priya_Subramaniam.txt

### Treatment Files (treatments/ directory)
1. **TREATMENT_CAP.txt** - Community Acquired Pneumonia treatments
2. **TREATMENT_HYPERTENSIVE_HEART_DISEASE.txt** - Hypertensive Heart Disease treatments
3. **TREATMENT_MDD.txt** - Major Depressive Disorder treatments
4. **TREATMENT_RA.txt** - Rheumatoid Arthritis treatments
5. **TREATMENT_TYPE2_DIABETES.txt** - Type 2 Diabetes treatments

---

## 5 Core Tools Overview

### 1. **Diagnosis Recommendation Tool**
**File:** `services/diagnosis_recommendation.py`

**Purpose:** Generates differential diagnoses based on patient symptoms (Doctor role only)

**Key Features:**
- Detects symptom-based queries (checks for symptom keywords or "+" separator)
- Uses RAG (Retrieval-Augmented Generation) to fetch clinical context
- Caches results for 30 days
- Returns structured differential diagnosis with confidence levels
- Enforces doctor-only access

**Main Function:**
```python
recommend_diagnosis(query: str, user_role: str = "Doctor", db: Optional[Session] = None) -> str
```

---

### 2. **Medical Knowledge Service**
**File:** `services/medical_knowledge_service.py`

**Purpose:** Provides general medical knowledge on conditions, drugs, procedures, and guidelines

**Key Features:**
- Supports multiple knowledge types (condition, symptom, drug, procedure, guideline)
- Role-based response formatting (Doctor, Nurse, Admin)
- Caches results with version control (v2)
- Augments answers with RAG when applicable
- Normalizes queries and knowledge types for consistent caching

**Main Function:**
```python
get_medical_knowledge(query: str, knowledge_type: str, user_role: str, db: Session) -> str
```

---

### 3. **Retrieval Service**
**File:** `services/retrieval_service.py`

**Purpose:** Performs vector similarity search on clinical documents with role-based access control

**Key Features:**
- Uses HuggingFace embeddings (all-MiniLM-L6-v2)
- Implements sophisticated role-based access control
- Detects access restrictions vs. no relevant data
- Supports Admin intent detection
- Returns top_k similar results

**Main Function:**
```python
retrieve_clinical_context(query: str, user_role: str, top_k: int = 3) -> str
```

---

### 4. **Summarization Service**
**File:** `services/summarization_service.py`

**Purpose:** Summarizes patient reports with role-based access control

**Key Features:**
- Role-specific summarization (Doctor, Nurse, Admin)
- Prevents age hallucination through context verification
- Lists accessible patients per role
- Blocked for Admin role
- Detailed structured output format

**Main Functions:**
```python
summarize_patient_report(db: Session, patient_name: str, user_role: str) -> str
list_accessible_patients(db: Session, user_role: str) -> list[str]
```

---

### 5. **Treatment Comparison Tool**
**File:** `services/treatment_comparison_tool.py`

**Purpose:** Compares treatment options with clinical analysis and role-specific guidance

**Key Features:**
- Role-specific guidance (Doctor, Nurse, Admin)
- Uses vector embeddings for clinical context retrieval
- Caches comparison results for 30 days
- Outputs Markdown tables with structured comparison
- Sanitizes HTML and enforces plain text output

**Main Function:**
```python
compare_treatments(query: str, user_role: str, db: Optional[Session] = None) -> str
```

---

## Test Cases for Each Tool

---

# 1. DIAGNOSIS RECOMMENDATION TOOL

## Positive Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| DG-P1 | Query: "fever + cough + fatigue", Role: "Doctor" | Returns differential diagnosis table with top conditions (e.g., CAP, viral URI, bronchitis) | Valid symptom query with multiple symptoms |
| DG-P2 | Query: "patient with shortness of breath + chest pain + tachycardia", Role: "Doctor" | Returns differential including cardiac and pulmonary causes; includes "Red Flags" section | Serious symptom combination |
| DG-P3 | Query: "what are possible diagnoses for headache + neck stiffness + fever", Role: "Doctor" | Returns differential with meningitis as high-confidence diagnosis | Classic symptom triad |
| DG-P4 | Query: "possible diagnosis for polyuria + polydipsia + weight loss", Role: "Doctor" | Returns differential pointing toward diabetes mellitus | Classic diabetes symptom pattern |
| DG-P5 | Query: Same as DG-P1, called twice in sequence | Second call returns cached result within milliseconds | Cache functionality working |
| DG-P6 | Query: "dyspnea + swelling + dizziness symptoms", Role: "Doctor" | Returns structured table with confidence levels and "Recommended Next Steps" | Multi-symptom query with detailed response |

## Negative Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| DG-N1 | Query: "fever + cough + fatigue", Role: "Nurse" | Error: "Diagnosis recommendation tool is available only for Doctor role." | Non-doctor user attempt |
| DG-N2 | Query: "fever + cough + fatigue", Role: "Admin" | Error: "Diagnosis recommendation tool is available only for Doctor role." | Admin user attempt |
| DG-N3 | Query: "What is the weather like today?", Role: "Doctor" | Error: "This is not related to a symptom-based diagnosis recommendation question." | Non-medical query |
| DG-N4 | Query: "Tell me about aspirin", Role: "Doctor" | Error: "This is not related to a symptom-based diagnosis recommendation question." | Medication query (not symptoms) |
| DG-N5 | Query: "", Role: "Doctor" | Error: "This is not related to a symptom-based diagnosis recommendation question." | Empty query |
| DG-N6 | Query: "xyz abc def", Role: "Doctor" | Return: "No relevant symptom-based diagnostic context found." or "ACCESS_RESTRICTED" | Nonsense/gibberish query |
| DG-N7 | Query: "symptoms?", Role: "Doctor" | Error or generic response (depends on implementation) | Too generic/vague |
| DG-N8 | Database connection fails | Error: "Error generating diagnosis recommendation: [exception message]" | Database unavailable |

## Edge Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| DG-E1 | Query: "fever+cough+fatigue" (no spaces around +) | Same as DG-P1 | Parser handles "+" operator correctly |
| DG-E2 | Query: "FEVER + COUGH + FATIGUE" (all uppercase) | Returns diagnosis; normalized to lowercase for processing | Case-insensitive processing |
| DG-E3 | Query: String with special characters: "fever@#$+cough%^&", Role: "Doctor" | Handles gracefully; may return error or no results | Special character handling |
| DG-E4 | Query: Very long query with 50+ symptoms listed | Returns top 3-5 diagnoses with confidence levels | Long input handling |
| DG-E5 | Query: "pulmonary embolism" with vague symptoms, Role: "Doctor" | PE not included unless query contains: sudden onset, pleuritic chest pain, hemoptysis, tachycardia, hypoxia, or thrombotic risk | Safety guard against PE hallucination |
| DG-E6 | Query: "sudden onset + pleuritic chest pain + hemoptysis + tachycardia", Role: "Doctor" | PE included in differential as justified condition | PE safety rule triggered correctly |
| DG-E7 | Query: Same as DG-P1, called after 30 days | Returns non-cached fresh result (cache expired) | Cache expiration handling |
| DG-E8 | Query: "fever + cough...", Role: "doctor" (lowercase role) | Normalizes role to "Doctor" and processes correctly | Role normalization |
| DG-E9 | Query: "1 + 2 + 3" | Rejects as non-medical | Numeric content handling |
| DG-E10 | Query: "severe symptoms", Role: "Doctor" | Generic response/error (too vague without specific symptoms) | Vague query without recognized symptoms |

---

# 2. MEDICAL KNOWLEDGE SERVICE

## Positive Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| MK-P1 | Query: "hypertension", Type: "condition", Role: "Doctor" | Returns clinically detailed explanation with differential points; 4-6 bullet points | Doctor getting condition knowledge |
| MK-P2 | Query: "aspirin", Type: "drug", Role: "Nurse" | Returns concise nursing-safe explanation without advanced prescribing; 4-6 bullet points | Nurse getting drug knowledge |
| MK-P3 | Query: "ECG procedure", Type: "procedure", Role: "Doctor" | Returns detailed procedure explanation; augmented with RAG if available | Procedure knowledge retrieval |
| MK-P4 | Query: "fever management", Type: "guideline", Role: "Admin" | Returns high-level informational explanation; avoids bedside directives | Admin getting guideline knowledge |
| MK-P5 | Same query as MK-P1 called twice | Second call returns cached result using normalized cache key | Cache hit working correctly |
| MK-P6 | Query: "diabetes", Type: "condition", Role: "Doctor" | Augmented response with local clinical context from retrieved documents | RAG augmentation successful |
| MK-P7 | Query: "symptoms of heart attack", Type: "symptom", Role: "Nurse" | Returns nursing-safe symptom explanation; practical and accessible | Symptom knowledge for nurses |
| MK-P8 | Query: "warfarin", Type: "drug", Role: "Doctor" | Returns clinical details including interactions, monitoring, contraindications | Detailed drug knowledge |

## Negative Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| MK-N1 | Query: "", Type: "condition", Role: "Doctor" | Error or empty response | Empty query |
| MK-N2 | Query: "xyz pharmaceuatical", Type: "drug", Role: "Nurse" | Returns: "Unable to find information" or generic response | Non-existent medication |
| MK-N3 | Query: "random gibberish", Type: "condition", Role: "Doctor" | Returns empty or generic response | Nonsense input |
| MK-N4 | Query: "heart disease", Type: "unknowntype", Role: "Doctor" | Normalizes unknown type or returns error | Invalid knowledge type |
| MK-N5 | Query: "classified admin info", Type: "condition", Role: "Nurse" | Returns: "ACCESS_RESTRICTED" if asking for admin-only content | Role-based access restriction |
| MK-N6 | Database connection fails | Error message returned | Database unavailable |
| MK-N7 | Query: "hypertension", Type: "condition", Role: "InvalidRole" | Defaults to generic role policy or error | Invalid user role |

## Edge Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| MK-E1 | Query: "   hypertension   " (extra whitespace), Type: "condition", Role: "Doctor" | Normalized and processes correctly | Whitespace normalization |
| MK-E2 | Query: "Hypertension?", Type: "condition", Role: "Doctor" | Removes trailing punctuation; processes as "hypertension" | Punctuation handling |
| MK-E3 | Query: "condition" (generic term), Type: "condition", Role: "Doctor" | Very generic response or "please specify" | Overly generic query |
| MK-E4 | Query: "hypertension", Type: "conditions" (plural), Role: "Doctor" | Normalizes "conditions" → "condition"; processes correctly | Plural alias handling |
| MK-E5 | Query: "HYPERTENSION" (uppercase), Type: "CONDITION" (uppercase), Role: "DOCTOR" | Normalized to lowercase; "Doctor" title-cased; processes correctly | Case normalization |
| MK-E6 | Query: Very long query (500+ chars), Type: "condition", Role: "Doctor" | Truncates or summarizes; processes without error | Long query handling |
| MK-E7 | Query: "hypertension", Type: "condition", Role: "Doctor"; Same query after 30+ days | Returns fresh response (cache expired v2 key) | Cache expiration |
| MK-E8 | Query: "diabetes", Type: "symptom" (wrong type), Role: "Doctor" | Returns knowledge as "symptom" or suggests correction | Type mismatch handling |
| MK-E9 | Query: Clinical context unavailable or error during RAG | Returns Groq-only response without RAG augmentation | RAG failure graceful fallback |
| MK-E10 | Query: "heart+disease+condition" (with special chars), Type: "condition", Role: "Nurse" | Processes with special char handling; normalizes spaces | Special character handling |

---

# 3. RETRIEVAL SERVICE

## Positive Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| RT-P1 | Query: "respiratory infection management", Role: "Doctor" | Returns 3 most relevant document chunks with headers showing source, category, section, allowed roles | Valid clinical query for doctor |
| RT-P2 | Query: "emergency department protocols", Role: "Nurse" | Returns accessible document chunks filtered for Nurse role | Role-based filtering working |
| RT-P3 | Query: "diabetes treatment", Role: "Admin" | Returns admin-accessible document chunks | Admin access to public content |
| RT-P4 | Query: "fever management", Role: "Doctor", top_k: 5 | Returns 5 most relevant chunks | Custom top_k parameter |
| RT-P5 | Query: "CAP treatment", Role: "Doctor" | Returns treatment protocol chunks with high relevance (distance ≤ 0.47) | Strong semantic match |
| RT-P6 | Query: "audit logs", Role: "Admin" | Returns admin-only governance/audit content | Admin-intent content retrieval |
| RT-P7 | Query: "nursing care procedures", Role: "Nurse" | Returns chunks specifically filtered for Nurse role | Nurse-accessible content |

## Negative Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| RT-N1 | Query: "audit logs", Role: "Nurse" | Returns: "ACCESS_RESTRICTED: Relevant content exists but is restricted by your role permissions." | Non-admin attempting admin-only content |
| RT-N2 | Query: "audit logs", Role: "Doctor" | Returns: "ACCESS_RESTRICTED: Relevant content exists but is restricted by your role permissions." | Doctor attempting admin-only content |
| RT-N3 | Query: "xyz qwerty asdfgh lkjhgf" (nonsense), Role: "Doctor" | Returns: "NO_RELEVANT_DATA: No relevant medical protocols found in the knowledge base." | Gibberish query |
| RT-N4 | Query: "", Role: "Doctor" | Returns: "NO_RELEVANT_DATA: No relevant medical protocols found in the knowledge base." | Empty query |
| RT-N5 | Query: "some random topic" (completely off-topic), Role: "Doctor" | Returns: "NO_RELEVANT_DATA: No relevant medical protocols found in the knowledge base." | Non-medical query |
| RT-N6 | Database connection fails | Returns: "An error occurred while retrieving medical knowledge." | Database unavailable |
| RT-N7 | Embedding model fails | Returns: "An error occurred while retrieving medical knowledge." | Embedding service error |

## Edge Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| RT-E1 | Query: "   respiratory   infection   " (extra spaces), Role: "Doctor" | Normalizes spaces; processes as "respiratory infection" | Whitespace normalization |
| RT-E2 | Query: "RESPIRATORY INFECTION" (uppercase), Role: "Doctor" | Converts to lowercase; matches documents correctly | Case normalization |
| RT-E3 | Query: Very strong overall match (distance 0.45) but Doctor has no role access | Returns: "ACCESS_RESTRICTED" (role-filtered match much weaker) | Access restriction detection |
| RT-E4 | Query: "respiratory", Role: "Doctor" | May return generic or weak results; depends on lexical overlap | Short query handling |
| RT-E5 | Query: Complex phrase with medical jargon, Role: "Doctor" | Returns relevant results if semantically similar to training data | Complex query handling |
| RT-E6 | Top_k = 1, Query: "hypertension", Role: "Doctor" | Returns only 1 result | Minimum k value |
| RT-E7 | Top_k = 100, Query: "fever", Role: "Doctor" | Returns available results (max 8 per implementation) | Large k value |
| RT-E8 | Query about governance (contains "audit", "compliance", "policy"), Role: "Doctor" | Returns "ACCESS_RESTRICTED" (admin intent + non-admin role) | Admin intent detection |
| RT-E9 | Query: "fever", Role: "doctor" (lowercase), Role: "Doctor" | Normalizes role to "Doctor" and processes | Role case normalization |
| RT-E10 | Document chunks with best overall match distance > 0.42 but weak role match | Returns "NO_RELEVANT_DATA" instead of "ACCESS_RESTRICTED" | Weak match classification |

---

# 4. SUMMARIZATION SERVICE

## Positive Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| SM-P1 | Patient: "Arjun_Sharma", Role: "Doctor" | Returns structured summary with all 5 sections (Access Scope, Patient Summary, Key Clinical Points, Medications, Restrictions) | Complete doctor access |
| SM-P2 | Patient: "Meera_Nair", Role: "Nurse" | Returns nursing-safe summary with focus on bedside care, escalation triggers, medication admin | Nurse-accessible summary |
| SM-P3 | Patient: "Rohan_Desai", Role: "Doctor" | Age explicitly stated in report; returns accurate age without hallucination | Age correctly reported |
| SM-P4 | List accessible patients, Role: "Doctor" | Returns list of all patient names accessible to doctor | Patient list retrieval |
| SM-P5 | List accessible patients, Role: "Nurse" | Returns filtered list of patients accessible to nurse | Role-filtered patient list |
| SM-P6 | Patient with no age data, Role: "Doctor" | Returns "Age: Not available in accessible report." (no hallucination) | Age unavailability handled |

## Negative Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| SM-N1 | Patient: "Arjun_Sharma", Role: "Admin" | Error: "Summarization tool is not available for Admin role." | Admin blocked from summarization |
| SM-N2 | Patient: "NonExistent_Patient", Role: "Doctor" | Error: "I cannot find an accessible report for this patient under your role permissions." | Non-existent patient |
| SM-N3 | Patient: "Restricted_Patient_Data", Role: "Nurse" | Error: "I cannot find an accessible report for this patient under your role permissions." | Role lacks access to patient |
| SM-N4 | Patient: "", Role: "Doctor" | Error or handling for empty patient name | Empty patient name |
| SM-N5 | Database connection fails | Error: "An error occurred while retrieving patient report." | Database unavailable |
| SM-N6 | Patient name has special characters: "Patient@#$%", Role: "Doctor" | Graceful error or attempt to match | Special characters in name |

## Edge Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| SM-E1 | Patient: "arjun_sharma" (lowercase), Role: "Doctor" | Normalizes and finds "Arjun_Sharma" (case handling) | Case normalization |
| SM-E2 | Patient: "  Arjun_Sharma  " (spaces), Role: "Doctor" | Trims whitespace; processes correctly | Whitespace trimming |
| SM-E3 | Patient with age pattern: "Patient is 25-year-old" | Correctly extracts age "25" | Age pattern regex matching |
| SM-E4 | Patient with multiple age mentions | Uses first mentioned age or handles ambiguity | Multiple age references |
| SM-E5 | Patient with age in different format: "age=45" | Regex captures age correctly (adjusted for format) | Alternate age format |
| SM-E6 | Very large patient report (1000+ chunks) | Returns comprehensive summary within token limits | Large report handling |
| SM-E7 | Patient report with classified sections (Doctor can access, Nurse cannot) | Filters context by role before summarization | Section-level filtering |
| SM-E8 | Patient report with media/images (if stored as chunks) | Skips or handles media; returns text-based summary | Media handling |
| SM-E9 | List accessible patients when no patients exist for role | Returns empty list [] | Empty patient list |
| SM-E10 | Patient name with unicode characters: "Müller_Patient", Role: "Doctor" | Processes or returns encoding error gracefully | Unicode handling |

---

# 5. TREATMENT COMPARISON TOOL

## Positive Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| TC-P1 | Query: "compare metformin vs gliclazide for diabetes", Role: "Doctor" | Returns structured comparison with Treatment Summary and Comparative Analysis tables; includes clinical evidence and dosing | Doctor-level treatment comparison |
| TC-P2 | Query: "compare insulin vs oral hypoglycemics for Type 2 Diabetes", Role: "Nurse" | Returns simplified practical comparison with administration routes, monitoring, patient care focus | Nurse-level practical comparison |
| TC-P3 | Query: "compare antibiotics for pneumonia", Role: "Doctor" | Returns comparison with efficacy, resistance patterns, adverse effects, monitoring needs | Complex treatment options |
| TC-P4 | Query: "compare treatments for hypertension", Role: "Admin" | Returns cost, resource requirements, policy implications; no clinical detail | Admin-level operational focus |
| TC-P5 | Same query as TC-P1 called twice | Second call returns cached result within milliseconds | Cache functionality (30-day expiration) |
| TC-P6 | Query: "compare CAP treatments", Role: "Doctor" | Uses clinical context retrieval to augment comparison; includes reference to protocols | RAG-augmented comparison |
| TC-P7 | Query: "compare surgical vs medical management", Role: "Doctor" | Returns detailed analysis of both approaches with pros/cons | Comparative strategy analysis |

## Negative Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| TC-N1 | Query: "", Role: "Doctor" | Error or generic response | Empty query |
| TC-N2 | Query: "how do you cook pasta?", Role: "Doctor" | Error: "Not a medical treatment comparison query." or generic response | Non-medical query |
| TC-N3 | Query: "asdfgh vs qwerty", Role: "Doctor" | Error or "Unable to generate meaningful comparison" | Nonsense query |
| TC-N4 | Query: "compare treatments", Role: "Doctor" | Requests clarification or returns generic response | Too vague (no specific treatments mentioned) |
| TC-N5 | Query: "compare aspirin vs ibuprofen", Role: "Nurse", but clinical context unavailable | Returns Groq-only response without clinical reference | Graceful degradation without RAG |
| TC-N6 | Database connection fails | Error message during cache or context retrieval | Database unavailable |

## Edge Test Cases

| Test ID | Input | Expected Output | Scenario |
|---------|-------|-----------------|----------|
| TC-E1 | Query: "compare   metformin   vs   gliclazide" (extra spaces), Role: "Doctor" | Normalizes spaces; processes correctly | Whitespace normalization |
| TC-E2 | Query: "COMPARE METFORMIN VS GLICLAZIDE" (uppercase), Role: "Doctor" | Converts to lowercase; processes correctly | Case normalization |
| TC-E3 | Query: "metformin vs gliclazide vs sitagliptin vs pioglitazone" (4+ options), Role: "Doctor" | Returns comparison table supporting multiple options or limits to top 3 | Many treatment options |
| TC-E4 | Query: Very long query (300+ characters) | Truncates focus or processes with partial understanding | Long query handling |
| TC-E5 | Query with special characters: "compare @metformin@ vs #gliclazide#", Role: "Doctor" | Handles special chars gracefully; extracts drug names | Special character handling |
| TC-E6 | Query asks for comparison on specific dimension: "cost comparison between treatment A and B", Role: "Admin" | Focuses output on cost dimension only | Focus instruction working |
| TC-E7 | Query: "compare treatments", Role: "invalid_role" | Defaults to Doctor role policy or error | Invalid user role |
| TC-E8 | Same query as TC-P1, called after 30 days | Returns non-cached fresh comparison (cache expired) | Cache expiration (30-day TTL) |
| TC-E9 | Groq LLM API timeout | Graceful error: "Error generating treatment comparison: API timeout" | LLM service failure |
| TC-E10 | Output contains HTML tags (if LLM tries to include) | Sanitized output removes HTML; returns plain text with Markdown tables only | HTML sanitization working |

---

## Summary of Test Coverage

| Tool | Positive Cases | Negative Cases | Edge Cases | Total |
|------|---|---|---|---|
| Diagnosis Recommendation | 6 | 8 | 10 | 24 |
| Medical Knowledge Service | 8 | 7 | 10 | 25 |
| Retrieval Service | 7 | 7 | 10 | 24 |
| Summarization Service | 6 | 6 | 10 | 22 |
| Treatment Comparison | 7 | 6 | 10 | 23 |
| **TOTAL** | **34** | **34** | **50** | **118** |

---

## Key Testing Scenarios

### Cross-Tool Integration Tests
1. **Diagnosis → Known Conditions Flow**: Symptom query triggers diagnosis tool → if confidence low, retrieves context → calls medical knowledge service for condition details
2. **Patient Workflow**: Summarization service retrieves patient → diagnosis recommendation for symptoms → treatment comparison → medical knowledge for details
3. **Role Cascade**: All tools respect role hierarchy; admin-only content inaccessible to doctors/nurses

### Security Tests
1. **Role-Based Access Control**: Verify each role can/cannot access restricted content
2. **Admin Intent Detection**: Ensure non-admin users cannot bypass governance queries
3. **Cache Poison Prevention**: Validate cache keys use normalized inputs (no role-specific injection)

### Performance Tests
1. **Cache Hit Speed**: Verify cached queries return within <100ms
2. **Vector Search Scale**: Test retrievals with 1000+ document chunks
3. **LLM Response Time**: Monitor Groq API response times (target <5s)

### Data Quality Tests
1. **Age Hallucination Prevention**: Verify summarization never invents patient ages
2. **PE Safety Rule**: Verify PE only included when justified by symptoms
3. **Role Policy Enforcement**: Verify nurses don't receive clinical-only diagnostic details

---

## Running These Tests

### Unit Testing (pytest)
```python
pytest test_diagnosis_recommendation.py -v
pytest test_medical_knowledge_service.py -v
pytest test_retrieval_service.py -v
pytest test_summarization_service.py -v
pytest test_treatment_comparison_tool.py -v
```

### Integration Testing
```python
pytest test_integration_flows.py -v
```

### Manual Smoke Tests
Use the Streamlit frontend or API endpoints to verify each tool manually with provided test cases.

---

**Document Version:** 1.0  
**Last Updated:** 2024  
**Test Coverage:** 118 comprehensive test cases across 5 core tools
