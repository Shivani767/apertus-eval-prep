"""Tool-using agent episode adapter."""
from __future__ import annotations

from typing import Any

from apertus_eval_prep.tasks.base import Task, TaskExample
from apertus_eval_prep.tasks.rag_episode import Episode, load_episodes


class AgentEpisodeTask(Task):
    """Render a tool-using request and score task completion heuristically."""

    kind = "agent_episode"

    def metadata_for(self, example: TaskExample) -> dict[str, Any]:
        metadata = dict(example.metadata)
        metadata.setdefault("tool_plan", [])
        return metadata

    def prompt_for(self, example: TaskExample) -> str:
        tools = example.metadata.get("available_tools") or []
        tool_text = ", ".join(str(item.get("name")) for item in tools if isinstance(item, dict))
        return f"Available tools: {tool_text or 'none'}\n\nUser request: {example.prompt}"

    def score(self, example: TaskExample, output: str) -> dict[str, Any]:
        criteria = example.metadata.get("success_criteria") or {}
        expected = example.gold or ""
        normalized = " ".join(output.lower().split())
        correct = bool(expected and expected.lower() in normalized)
        if criteria.get("task_completed") is False:
            correct = False
        return {"score": 1.0 if correct else 0.0, "correct": correct,
                "predicted": output, "gold": expected or None, "scorer": "agent_heuristic"}


__all__ = ["AgentEpisodeTask", "Episode", "load_episodes"]
