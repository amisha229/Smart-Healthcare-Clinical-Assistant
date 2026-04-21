# Smart Healthcare Clinical Assistant

Smart Healthcare Clinical Assistant is an AI-powered clinical support system built with Streamlit, FastAPI, LangChain-style orchestration, PostgreSQL, pgvector, Groq, and LangSmith. It helps healthcare professionals interact with clinical documents, patient reports, and treatment knowledge through a conversational interface.

The project focuses on role-aware clinical assistance for Doctors, Nurses, and Admins, with support for document retrieval, patient report summarization, treatment comparison, diagnosis recommendation, conversation memory, and observability.

## Features

- Conversational clinical assistant with a Streamlit chat interface
- Role-based access for Doctor, Nurse, and Admin users
- Retrieval-Augmented Generation (RAG) over clinical documents and protocols
- Patient report summarization with role-aware output
- Medical knowledge support for conditions, drugs, symptoms, procedures, and guidelines
- Treatment comparison for disease-specific treatment options
- Diagnosis recommendation support for doctor users
- Persistent conversation history stored in PostgreSQL
- LangSmith tracing and observability support
- Unit-tested backend services

## Tech Stack

- Frontend: Streamlit
- Backend: FastAPI
- Orchestration: LangChain-style chat orchestration and tool routing
- LLM Inference: Groq API via OpenAI-compatible client
- Database: PostgreSQL
- Vector Search: pgvector
- Embeddings: sentence-transformers `all-MiniLM-L6-v2`
- Observability: LangSmith
- Testing: pytest

## Architecture Overview

1. User interacts through the Streamlit UI.
2. FastAPI receives the request and handles routing.
3. The chat orchestration layer applies role rules and calls the selected tool.
4. Tools retrieve or process data using PostgreSQL, pgvector, and Groq.
5. Responses are returned to the UI and saved as conversation history.
6. LangSmith can trace tool execution and response flow.

Core tool set:
- Clinical Retrieval (RAG)
- Medical Summarization
- Medical Knowledge
- Treatment Comparison
- Diagnosis Recommendation

## Project Structure

```text
Smart-Healthcare-Clinical-Assistant/
|-- backend/
|   |-- main.py
|   |-- database.py
|   |-- config.py
|   |-- init_db.py
|   |-- seed_data.py
|   |-- add_admin.py
|   |-- Dockerfile
|   |-- docker-entrypoint.sh
|   |-- pytest.ini
|   |-- requirements.txt
|   |-- README.md
|   |-- TEST_CASES_DOCUMENTATION.md
|   |-- models/
|   |   |-- user.py
|   |   |-- conversation.py
|   |   |-- message.py
|   |   |-- document_chunk.py
|   |   |-- patient_report.py
|   |   `-- medical_knowledge_cache.py
|   |-- routes/
|   |   |-- auth.py
|   |   `-- chat.py
|   |-- schemas/
|   |   |-- user_schema.py
|   |   `-- chat_schema.py
|   |-- services/
|   |   |-- auth_service.py
|   |   |-- chat_service.py
|   |   |-- retrieval_service.py
|   |   |-- summarization_service.py
|   |   |-- medical_knowledge_service.py
|   |   |-- treatment_comparison_tool.py
|   |   |-- diagnosis_recommendation.py
|   |   `-- langsmith_observability.py
|   |-- tests/
|   |   |-- test_retrieval_service.py
|   |   |-- test_medical_knowledge_tool.py
|   |   |-- test_medical_summarization_tool.py
|   |   |-- test_treatment_comparison_tool.py
|   |   `-- test_diagnosis_recommendation.py
|   |-- utils/
|   |   |-- db_ingestion.py
|   |   `-- db_ingestion_treatments.py
|   |-- documents/
|   |   |-- Clinical_Protocols.txt
|   |   |-- Treatment_Protocols.txt
|   |   |-- langsmith_integration_plan.md
|   |   |-- tool_testing_report.md
|   |   |-- reports/
|   |   `-- treatments/
|   `-- frontend/
|       |-- app.py
|       |-- Dockerfile
|       |-- requirements.txt
|       `-- README.md
|-- documents/
|   |-- Clinical_Protocols.txt
|   |-- Treatment_Protocols.txt
|   |-- langsmith_integration_plan.md
|   |-- tool_testing_report.md
|   |-- reports/
|   |   |-- MR-2024-00312_Arjun_Sharma.txt
|   |   |-- MR-2024-00389_Meera_Nair.txt
|   |   |-- MR-2024-00421_Rohan_Desai.txt
|   |   |-- MR-2024-00478_Sunita_Rao.txt
|   |   |-- MR-2024-00519_Farhan_Sheikh.txt
|   |   |-- MR-2024-00553_Lakshmi_Venkataraman.txt
|   |   |-- MR-2024-00645_Ananya_Krishnan.txt
|   |   |-- MR-2024-00698_Deepak_Malhotra.txt
|   |   `-- MR-2024-00734_Priya_Subramaniam.txt
|   `-- treatments/
|-- frontend/
|   |-- app.py
|   |-- Dockerfile
|   |-- requirements.txt
|   `-- README.md
|-- docker-compose.yml
|-- docker_backup.dump
|-- copy_db.py
|-- README.md
|-- TEST_CASES_DOCUMENTATION.md
`-- .env (required - see Environment Variables section)
```

## Main Components

### Frontend
- `frontend/app.py`
- Provides login, chat, tool selection, patient selection, and conversation history.

### Backend API
- `backend/main.py`
- Exposes authentication and chat endpoints through FastAPI.

### Authentication
- `backend/routes/auth.py`
- Supports simple registration and login using PostgreSQL-backed users.

### Chat and Tool Routing
- `backend/services/chat_service.py`
- Applies role-aware behavior, stores messages, and routes requests to the selected tool.

### Retrieval Service
- `backend/services/retrieval_service.py`
- Uses embeddings and pgvector similarity search to fetch relevant clinical document chunks.

### Summarization Service
- `backend/services/summarization_service.py`
- Summarizes patient reports with different behavior for Doctor and Nurse roles.

### Medical Knowledge Service
- `backend/services/medical_knowledge_service.py`
- Provides general medical explanations with optional RAG augmentation and response caching.

### Treatment Comparison Tool
- `backend/services/treatment_comparison_tool.py`
- Compares treatment options for supported disease areas.

### Diagnosis Recommendation Tool
- `backend/services/diagnosis_recommendation.py`
- Suggests possible diagnoses and next steps for symptom-based doctor queries.

### Observability
- `backend/services/langsmith_observability.py`
- Adds tracing, feedback handling, and low-score analytics hooks through LangSmith.

## Setup

### Prerequisites

- Python 3.11 recommended
- PostgreSQL with pgvector enabled
- Groq API key
- Optional LangSmith credentials for tracing

### Install Backend Dependencies

```powershell
cd backend
pip install -r requirements.txt
```

### Install Frontend Dependencies

```powershell
cd frontend
pip install -r requirements.txt
```

## Environment Variables

Typical environment values used by this project include:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
GROQ_API_KEY=your_groq_api_key
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=healthcare-assistant
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
API_BASE_URL=http://localhost:8000
```

## Run Locally

### Start the Backend

From the `backend/` folder:

```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Start the Frontend

From the `frontend/` folder:

```powershell
streamlit run app.py
```

### Open the App

- Frontend: `http://localhost:8501`
- Backend API: `http://localhost:8000`
- Swagger Docs: `http://localhost:8000/docs`

## Docker

This repository includes a Docker-based backend setup.

### Build the Image

```powershell
docker build -t smart-healthcare-assistant .
```

### Run the Container

Make sure `DATABASE_URL` is reachable from the container, then run:

```powershell
docker run -p 8000:8000 --env-file .env smart-healthcare-assistant
```

The container entrypoint waits for PostgreSQL, runs `init_db.py`, and then starts the FastAPI server.

## API Endpoints

Authentication:
- `POST /auth/register`
- `POST /auth/login`

Chat:
- `POST /chat`
- `GET /chat/patients`
- `GET /chat/conversations`
- `GET /chat/conversations/{conversation_id}`
- `PATCH /chat/conversations/{conversation_id}`
- `DELETE /chat/conversations/{conversation_id}`

Observability:
- `POST /chat/feedback`
- `GET /chat/analytics/low-score-tools`

## Testing

Run backend tests from the `backend/` folder:

```powershell
pytest tests -q
```

The repository includes unit tests for:
- Retrieval service
- Medical summarization tool
- Medical knowledge tool
- Treatment comparison tool
- Diagnosis recommendation tool

## Example Use Cases

- Ask clinical questions against stored protocols and guidelines
- Summarize a patient report based on the logged-in role
- Compare treatment options for a disease such as diabetes or pneumonia
- Request general medical knowledge on conditions or drugs
- Suggest possible diagnoses from symptom combinations
- Continue previous consultations using saved conversation history

## Notes

- The current system uses simple username/password authentication for demo and project use.
- Doctor, Nurse, and Admin roles receive different levels of access and response detail.
- Diagnosis recommendation is restricted to the Doctor role.
- The frontend allows the user to select the tool, and the backend routes the request accordingly.

## Future Improvements

- Production-grade authentication and password hashing
- Integration with hospital systems or EHR platforms
- Voice-based interaction
- Expanded clinical datasets and stronger decision support
- More deployment-ready infrastructure and security hardening
