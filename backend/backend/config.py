import os
from dataclasses import dataclass


def _to_bool(value: str | None, default: bool = False) -> bool:
	if value is None:
		return default
	return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LangSmithSettings:
	enabled: bool
	api_key: str | None
	project: str
	endpoint: str | None


def get_langsmith_settings() -> LangSmithSettings:
	return LangSmithSettings(
		enabled=_to_bool(os.getenv("LANGSMITH_TRACING"), default=False),
		api_key=os.getenv("LANGSMITH_API_KEY"),
		project=os.getenv("LANGSMITH_PROJECT", "healthcare-assistant"),
		endpoint=os.getenv("LANGSMITH_ENDPOINT"),
	)
