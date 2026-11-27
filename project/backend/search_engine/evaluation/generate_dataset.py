from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DOCUMENTS = {
    "quiet_cafe": "https://demo.pose.local/cafes/quiet-study",
    "busy_cafe": "https://demo.pose.local/cafes/loud-market",
    "accessible_cafe": "https://demo.pose.local/cafes/accessible",
    "open_article": "https://demo.pose.local/research/open-search",
    "unknown_article": "https://demo.pose.local/research/paywalled",
    "remote_job": "https://demo.pose.local/jobs/remote",
    "office_job": "https://demo.pose.local/jobs/on-site",
    "park": "https://demo.pose.local/places/park",
    "linen": "https://demo.pose.local/products/linen",
    "repository": "https://demo.pose.local/repos/search",
}


def doc_id(key: str) -> str:
    url = DOCUMENTS[key]
    canonical = url.replace("https://www.", "https://")
    return hashlib.sha256(canonical.encode()).hexdigest()


def pref(attribute: str, value: str, polarity: str = "positive") -> dict:
    return {
        "attribute": attribute,
        "value": value,
        "polarity": polarity,
        "weight": 0.9,
        "confidence": 1.0,
        "scope": "global",
        "source": "explicit",
    }


def criterion(attribute: str, value: str, hard: bool, operator: str = "semantic_match") -> dict:
    return {
        "id": f"eval-{attribute}-{value}".replace(" ", "-"),
        "attribute": attribute,
        "operator": operator,
        "value": value,
        "weight": 1.0 if hard else 0.7,
        "confidence": 1.0,
        "is_hard_constraint": hard,
        "source": "explicit",
    }


SCENARIOS: list[dict[str, Any]] = [
    {
        "query": "quiet study cafe",
        "profile": "quiet_reader",
        "preferences": [pref("noise_level", "quiet")],
        "labels": {"quiet_cafe": 3, "accessible_cafe": 2, "busy_cafe": 0},
    },
    {
        "query": "quiet study cafe",
        "profile": "accessibility_first",
        "preferences": [pref("accessibility", "step-free")],
        "labels": {"accessible_cafe": 3, "quiet_cafe": 2, "busy_cafe": 0},
    },
    {
        "query": "quiet cafe with comfortable seats and power outlets",
        "profile": "outlet_user",
        "preferences": [pref("power", "outlets")],
        "labels": {"quiet_cafe": 3, "accessible_cafe": 3, "busy_cafe": 0},
    },
    {
        "query": "study cafe without loud music",
        "profile": "neutral",
        "preferences": [],
        "labels": {"quiet_cafe": 3, "accessible_cafe": 2, "busy_cafe": 0},
        "hard": {"quiet_cafe": "satisfied", "accessible_cafe": "satisfied", "busy_cafe": "violated"},
        "exclusions": [criterion("query_requirement", "loud music", True, "neq")],
    },
    {
        "query": "cafe must have power outlets",
        "profile": "neutral",
        "preferences": [],
        "labels": {"quiet_cafe": 3, "accessible_cafe": 3, "busy_cafe": 0},
        "hard": {"quiet_cafe": "satisfied", "accessible_cafe": "satisfied", "busy_cafe": "violated"},
        "criteria": [criterion("query_requirement", "power outlets", True)],
    },
    {
        "query": "remote data engineer job with flexible hours",
        "profile": "remote_worker",
        "preferences": [pref("work_mode", "remote")],
        "labels": {"remote_job": 3, "office_job": 0},
        "hard": {"remote_job": "satisfied", "office_job": "violated"},
        "criteria": [criterion("remote", "true", True, "eq")],
    },
    {
        "query": "open information retrieval research article",
        "profile": "open_access",
        "preferences": [pref("access", "open")],
        "labels": {"open_article": 3, "unknown_article": 1},
        "hard": {"open_article": "satisfied", "unknown_article": "unknown"},
        "criteria": [criterion("access", "open", True, "eq")],
    },
    {
        "query": "a source about an underwater moon base",
        "profile": "neutral",
        "preferences": [],
        "labels": {},
    },
    {
        "query": "simple example of a BM25 search repository",
        "profile": "developer",
        "preferences": [pref("license", "MIT")],
        "labels": {"repository": 3, "open_article": 1},
    },
    {
        "query": "linen overshirt with natural fabric",
        "profile": "natural_fibers",
        "preferences": [pref("material", "linen")],
        "labels": {"linen": 3},
    },
]


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index in range(30):
        scenario = SCENARIOS[index % len(SCENARIOS)]
        query = scenario["query"]
        if index >= len(SCENARIOS):
            suffixes = ("", " options", " recommendations")
            query = query + suffixes[index // len(SCENARIOS) % len(suffixes)]
        labels = {doc_id(key): value for key, value in scenario["labels"].items()}
        hard = {doc_id(key): value for key, value in scenario.get("hard", {}).items()}
        cases.append(
            {
                "query_id": f"q{index + 1:03d}",
                "query": query,
                "user_profile_id": scenario["profile"],
                "preferences": scenario["preferences"],
                "criteria": scenario.get("criteria", []),
                "exclusions": scenario.get("exclusions", []),
                "relevance_labels": labels,
                "hard_constraint_labels": hard,
                "label_source": "synthetic_fixture",
            }
        )
    return cases


if __name__ == "__main__":
    destination = Path(__file__).with_name("datasets") / "pose_v2_fixture.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in build_cases()),
        encoding="utf-8",
    )
    print(f"Wrote {len(build_cases())} synthetic fixture cases to {destination}")
