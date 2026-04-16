from __future__ import annotations

from collections import defaultdict
from typing import Any

from config import get_langsmith_settings


class LangSmithTracer:
    """Small wrapper around LangSmith RunTree APIs with safe fallbacks."""

    def __init__(self) -> None:
        self.settings = get_langsmith_settings()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.enabled and self.settings.api_key)

    def start_root_run(
        self,
        *,
        name: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any | None:
        if not self.enabled:
            return None
        try:
            from langsmith.run_trees import RunTree

            run = RunTree(
                name=name,
                run_type="chain",
                inputs=inputs,
                project_name=self.settings.project,
                tags=tags or [],
                extra={"metadata": metadata or {}},
            )
            run.post()
            return run
        except Exception:
            return None

    def start_child_run(
        self,
        parent_run: Any | None,
        *,
        name: str,
        run_type: str,
        inputs: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any | None:
        if not parent_run:
            return None
        try:
            child = parent_run.create_child(
                name=name,
                run_type=run_type,
                inputs=inputs,
                tags=tags or [],
                extra={"metadata": metadata or {}},
            )
            child.post()
            return child
        except Exception:
            return None

    def end_run(
        self,
        run: Any | None,
        *,
        outputs: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if not run:
            return
        try:
            if error:
                run.end(error=error)
            else:
                run.end(outputs=outputs or {})
            run.patch()
        except Exception:
            return

    def submit_feedback(
        self,
        *,
        run_id: str,
        score: float,
        key: str = "response_accuracy",
        comment: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        if not self.enabled:
            return False
        try:
            from langsmith import Client

            client = Client(
                api_key=self.settings.api_key,
                api_url=self.settings.endpoint,
            )
            client.create_feedback(
                run_id=run_id,
                key=key,
                score=score,
                comment=comment,
                source_info=metadata or {},
            )
            return True
        except Exception:
            return False

    def get_low_score_tool_summary(
        self,
        *,
        key: str = "response_accuracy",
        threshold: float = 0.7,
        limit: int = 100,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        try:
            from langsmith import Client

            client = Client(
                api_key=self.settings.api_key,
                api_url=self.settings.endpoint,
            )

            feedback_items = list(client.list_feedback(key=key, limit=limit))
            low_items: list[tuple[str, float]] = []
            for item in feedback_items:
                score = getattr(item, "score", None)
                run_id = str(getattr(item, "run_id", "") or "")
                if score is None or not run_id:
                    continue
                score_value = float(score)
                if score_value <= threshold:
                    low_items.append((run_id, score_value))

            if not low_items:
                return {
                    "key": key,
                    "threshold": threshold,
                    "total_low_score_count": 0,
                    "tools": [],
                }

            tool_stats: dict[str, dict[str, Any]] = defaultdict(
                lambda: {"count": 0, "score_sum": 0.0, "example_run_ids": []}
            )

            for run_id, score_value in low_items:
                tool_name = "unknown"
                try:
                    run = client.read_run(run_id)
                    run_name = str(getattr(run, "name", "") or "")
                    if run_name.startswith("chat.tool."):
                        tool_name = run_name.replace("chat.tool.", "", 1)
                    else:
                        extra = getattr(run, "extra", {}) or {}
                        metadata = extra.get("metadata", {}) if isinstance(extra, dict) else {}
                        tool_name = str(metadata.get("tool", "unknown") or "unknown")
                except Exception:
                    tool_name = "unknown"

                stats = tool_stats[tool_name]
                stats["count"] += 1
                stats["score_sum"] += score_value
                if len(stats["example_run_ids"]) < 5:
                    stats["example_run_ids"].append(run_id)

            tools = []
            for tool_name, stats in sorted(tool_stats.items(), key=lambda kv: kv[1]["count"], reverse=True):
                tools.append(
                    {
                        "tool": tool_name,
                        "count": stats["count"],
                        "average_score": round(stats["score_sum"] / stats["count"], 4),
                        "example_run_ids": stats["example_run_ids"],
                    }
                )

            return {
                "key": key,
                "threshold": threshold,
                "total_low_score_count": len(low_items),
                "tools": tools,
            }
        except Exception:
            return None
