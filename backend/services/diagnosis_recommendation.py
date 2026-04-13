import os
import re
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from database import SessionLocal
from models.medical_knowledge_cache import MedicalKnowledgeCache
from services.retrieval_service import retrieve_clinical_context

load_dotenv()

llm = ChatOpenAI(
	api_key=os.environ.get("GROQ_API_KEY"),
	base_url="https://api.groq.com/openai/v1",
	model="openai/gpt-oss-20b",
	temperature=0.2,
	max_tokens=1200,
)


def _is_symptom_query(user_message: str) -> bool:
	text = (user_message or "").strip().lower()
	if not text:
		return False

	if "+" in text:
		return True

	symptom_terms = [
		"fever", "cough", "fatigue", "pain", "headache", "vomiting", "nausea",
		"diarrhea", "dyspnea", "shortness of breath", "chest pain", "rash", "dizziness",
		"chills", "sore throat", "polyuria", "polydipsia", "weight loss", "swelling",
		"symptom", "symptoms", "signs"
	]

	diagnosis_intents = [
		"possible diagnosis", "differential", "what could this be", "likely condition",
		"possible conditions", "diagnosis"
	]

	has_symptom = any(term in text for term in symptom_terms)
	has_diagnosis_intent = any(intent in text for intent in diagnosis_intents)
	return has_symptom or has_diagnosis_intent


def _check_cache(query: str, db: Session) -> Optional[str]:
	try:
		cached_entry = db.query(MedicalKnowledgeCache).filter(
			MedicalKnowledgeCache.query == query,
			MedicalKnowledgeCache.knowledge_type == "diagnosis_recommendation",
			MedicalKnowledgeCache.expires_at > datetime.utcnow(),
		).first()
		return cached_entry.response if cached_entry else None
	except Exception:
		return None


def _save_cache(query: str, response: str, db: Session) -> None:
	try:
		entry = MedicalKnowledgeCache(
			query=query,
			knowledge_type="diagnosis_recommendation",
			response=response,
			source="RAG + Groq LLM",
			expires_at=datetime.utcnow() + timedelta(days=30),
		)
		db.add(entry)
		db.commit()
	except Exception:
		db.rollback()


def _generate_diagnosis_response(user_message: str, context: str) -> str:
	prompt = ChatPromptTemplate.from_messages([
		(
			"system",
			"You are a clinical differential diagnosis assistant for licensed doctors only.\n"
			"Use ONLY the provided context and never fabricate findings.\n"
			"If data is insufficient, say so explicitly.\n"
			"Provide a differential diagnosis, not a final diagnosis.\n"
			"Prefer common, high-probability diagnoses supported by the context.\n"
			"Do not include rare diagnoses unless strongly supported by the symptoms or context.\n"
			"Do not invent vitals, lab values, imaging results, or exam findings.\n"
			"Do not mention pulmonary embolism unless the query includes sudden onset, pleuritic chest pain, hemoptysis, tachycardia, hypoxia, or thrombotic risk.\n\n"
			"Return in this exact structure and no other sections:\n"
			"1) Differential Diagnosis Table\n"
			"| Rank | Possible Condition | Why it fits | Confidence |\n"
			"|---|---|---|---|\n"
			"2) Recommended Next Steps Table\n"
			"| Step | Action | Purpose |\n"
			"|---|---|---|\n"
			"3) Red Flags\n"
			"- Bullet list only\n\n"
			"Safety Rules:\n"
			"- Do not provide definitive diagnosis; provide differential only\n"
			"- Do not mention role/tool routing text\n"
			"- Keep concise and actionable for physicians\n"
			"- Each table row must be one line and each cell should be brief\n"
			"- Use 3 to 5 differential diagnoses maximum\n"
			"- If a condition is only weakly supported, mark confidence as Low\n"
			"- For common respiratory symptom sets, prioritize CAP, atypical pneumonia, viral URI, and bronchitis before less likely causes\n\n"
			"===== CLINICAL CONTEXT =====\n"
			"{context}\n"
			"============================"
		),
		("human", "Symptoms/Query: {question}")
	])

	chain = prompt | llm
	response = chain.invoke({"context": context, "question": user_message})
	return response.content


def recommend_diagnosis(
	query: str,
	user_role: str = "Doctor",
	db: Optional[Session] = None,
) -> str:
	"""Generate possible diagnoses and recommendations from symptoms (Doctor only)."""
	normalized_role = (user_role or "Doctor").strip().title()
	if normalized_role != "Doctor":
		return "Diagnosis recommendation tool is available only for Doctor role."

	if not _is_symptom_query(query):
		return "This is not related to a symptom-based diagnosis recommendation question."

	close_db = False
	if db is None:
		db = SessionLocal()
		close_db = True

	try:
		cache_key = f"diagnosis::{query.strip().lower()}"
		cached = _check_cache(cache_key, db)
		if cached:
			return cached

		context = retrieve_clinical_context(query, user_role="Doctor", top_k=6)
		if context.startswith("ACCESS_RESTRICTED:"):
			return "Relevant diagnostic context exists but is restricted."
		if context.startswith("NO_RELEVANT_DATA:"):
			return "No relevant symptom-based diagnostic context found in the knowledge base."

		result = _generate_diagnosis_response(query, context)
		result = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", result)
		result = re.sub(r"<[^>]+>", "", result).strip()
		result = re.sub(r"\n{3,}", "\n\n", result)

		_save_cache(cache_key, result, db)
		return result
	except Exception as exc:
		return f"Error generating diagnosis recommendation: {exc}"
	finally:
		if close_db:
			db.close()
