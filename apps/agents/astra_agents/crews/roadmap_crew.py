"""Roadmap crew — turns a skill gap into a 7-day bridge_roadmap.

This is the "autonomous skill-gap closure" wedge: not just listing what you
don't know, but planning a day-by-day path to close it before the deadline.

Two paths, same contract:
- LLM path uses the `creative` LLM to generate per-day focus + resources.
- Fallback path uses a curated lookup table for common skills, plus a generic
  "Day N: practice <skill>" template for unknown skills.

Both produce a list of `BridgeRoadmapDay` validated against the schema.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from astra_schemas import BridgeRoadmapDay, Opportunity, ReadinessEngine, Resource

logger = logging.getLogger("astra.roadmap_crew")


# ---------------------------------------------------------------------------
# Curated fallback library — hand-picked, high-signal resources for common
# requirements. Keep this short and quality-controlled rather than exhaustive;
# unknown skills get a generic template instead of bad links.
# ---------------------------------------------------------------------------

CURATED_RESOURCES: dict[str, list[dict[str, str]]] = {
    "python": [
        {"type": "Course", "title": "CS50P: Introduction to Python (Harvard, free)", "url": "https://cs50.harvard.edu/python/"},
        {"type": "Doc", "title": "The Python Tutorial (official)", "url": "https://docs.python.org/3/tutorial/"},
        {"type": "Video", "title": "Python Full Course for Beginners — freeCodeCamp (4h)", "url": "https://www.youtube.com/watch?v=rfscVS0vtbw"},
    ],
    "tensorflow": [
        {"type": "Course", "title": "TensorFlow Developer Certificate prep (free)", "url": "https://www.tensorflow.org/certificate"},
        {"type": "Video", "title": "TensorFlow 2.0 Full Tutorial — freeCodeCamp (7h)", "url": "https://www.youtube.com/watch?v=tPYj3fFJGjk"},
        {"type": "Doc", "title": "TensorFlow Quickstart for Beginners", "url": "https://www.tensorflow.org/tutorials/quickstart/beginner"},
    ],
    "pytorch": [
        {"type": "Course", "title": "PyTorch for Deep Learning — freeCodeCamp (26h)", "url": "https://www.youtube.com/watch?v=V_xro1bcAuA"},
        {"type": "Doc", "title": "PyTorch 60-Minute Blitz", "url": "https://pytorch.org/tutorials/beginner/deep_learning_60min_blitz.html"},
        {"type": "Course", "title": "fast.ai Practical Deep Learning (free)", "url": "https://course.fast.ai/"},
    ],
    "machine learning": [
        {"type": "Course", "title": "Andrew Ng's ML Specialization (Coursera, free audit)", "url": "https://www.coursera.org/specializations/machine-learning-introduction"},
        {"type": "Video", "title": "Machine Learning Full Course — freeCodeCamp (12h)", "url": "https://www.youtube.com/watch?v=NWONeJKn6kc"},
        {"type": "Repo", "title": "scikit-learn tutorials (official)", "url": "https://scikit-learn.org/stable/tutorial/"},
    ],
    "deep learning": [
        {"type": "Course", "title": "fast.ai Practical Deep Learning (free)", "url": "https://course.fast.ai/"},
        {"type": "Video", "title": "3Blue1Brown Neural Networks series", "url": "https://www.youtube.com/playlist?list=PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi"},
        {"type": "Course", "title": "Deep Learning Specialization (Coursera, free audit)", "url": "https://www.coursera.org/specializations/deep-learning"},
    ],
    "react": [
        {"type": "Doc", "title": "React — Quick Start (official)", "url": "https://react.dev/learn"},
        {"type": "Video", "title": "React Full Course 2024 — freeCodeCamp (12h)", "url": "https://www.youtube.com/watch?v=x4rFhThSX04"},
        {"type": "Course", "title": "Full Stack Open — React (University of Helsinki, free)", "url": "https://fullstackopen.com/en/part1"},
    ],
    "next.js": [
        {"type": "Course", "title": "Next.js 14 Official Learn Course", "url": "https://nextjs.org/learn"},
        {"type": "Video", "title": "Next.js Full Tutorial — Traversy Media (2h)", "url": "https://www.youtube.com/watch?v=Y6KDk5iyrYE"},
        {"type": "Doc", "title": "Next.js App Router Docs", "url": "https://nextjs.org/docs/app"},
    ],
    "node.js": [
        {"type": "Course", "title": "Node.js Full Course — freeCodeCamp (8h)", "url": "https://www.youtube.com/watch?v=Oe421EPjeBE"},
        {"type": "Doc", "title": "Node.js Getting Started (official)", "url": "https://nodejs.org/en/learn/getting-started/introduction-to-nodejs"},
        {"type": "Course", "title": "The Odin Project — NodeJS Path (free)", "url": "https://www.theodinproject.com/paths/full-stack-javascript/courses/nodejs"},
    ],
    "javascript": [
        {"type": "Course", "title": "JavaScript Algorithms & DS — freeCodeCamp (free)", "url": "https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures/"},
        {"type": "Video", "title": "JavaScript Full Course — freeCodeCamp (8h)", "url": "https://www.youtube.com/watch?v=PkZNo7MFNFg"},
        {"type": "Doc", "title": "MDN JavaScript Guide", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide"},
    ],
    "typescript": [
        {"type": "Doc", "title": "TypeScript Handbook (official)", "url": "https://www.typescriptlang.org/docs/handbook/"},
        {"type": "Course", "title": "TypeScript Full Course — Net Ninja (free)", "url": "https://www.youtube.com/playlist?list=PL4cUxeGkcC9gUgr39Q_yD6v-bSyMwKPUI"},
        {"type": "Video", "title": "TypeScript for React — Jack Herrington", "url": "https://www.youtube.com/watch?v=TPACABQTHvM"},
    ],
    "fastapi": [
        {"type": "Doc", "title": "FastAPI Tutorial (official, excellent)", "url": "https://fastapi.tiangolo.com/tutorial/"},
        {"type": "Video", "title": "FastAPI Full Course — freeCodeCamp (6h)", "url": "https://www.youtube.com/watch?v=0sOvCWFmrtA"},
        {"type": "Course", "title": "Test-Driven Development with FastAPI", "url": "https://testdriven.io/courses/tdd-fastapi/"},
    ],
    "docker": [
        {"type": "Course", "title": "Docker Tutorial — TechWorld with Nana (3h)", "url": "https://www.youtube.com/watch?v=3c-iBn73dDE"},
        {"type": "Doc", "title": "Docker Get Started (official)", "url": "https://docs.docker.com/get-started/"},
        {"type": "Video", "title": "Docker in 100 seconds — Fireship", "url": "https://www.youtube.com/watch?v=Gjnup-PuquQ"},
    ],
    "rust": [
        {"type": "Doc", "title": "The Rust Programming Language Book", "url": "https://doc.rust-lang.org/book/"},
        {"type": "Repo", "title": "rustlings — learn by doing", "url": "https://github.com/rust-lang/rustlings"},
        {"type": "Video", "title": "Rust Full Course — freeCodeCamp (14h)", "url": "https://www.youtube.com/watch?v=BpPEoZW5IiY"},
    ],
    "yolov8": [
        {"type": "Doc", "title": "Ultralytics YOLOv8 Quickstart", "url": "https://docs.ultralytics.com/quickstart/"},
        {"type": "Video", "title": "YOLOv8 Object Detection Tutorial — Nicolai Nielsen", "url": "https://www.youtube.com/watch?v=WgPbbWmnXJ8"},
        {"type": "Repo", "title": "Ultralytics — examples & notebooks", "url": "https://github.com/ultralytics/ultralytics"},
    ],
    "raspberry pi": [
        {"type": "Course", "title": "Raspberry Pi Projects for Beginners", "url": "https://projects.raspberrypi.org/en/projects/raspberry-pi-getting-started"},
        {"type": "Video", "title": "Raspberry Pi Full Course — freeCodeCamp", "url": "https://www.youtube.com/watch?v=eJKbTUgMzHk"},
        {"type": "Doc", "title": "Raspberry Pi Documentation", "url": "https://www.raspberrypi.com/documentation/"},
    ],
    "flutter": [
        {"type": "Course", "title": "Flutter Full Course — freeCodeCamp (37h)", "url": "https://www.youtube.com/watch?v=VPvVD8t02U8"},
        {"type": "Doc", "title": "Flutter Get Started (official)", "url": "https://docs.flutter.dev/get-started/install"},
        {"type": "Course", "title": "Flutter & Dart — The Complete Guide (Udemy preview)", "url": "https://www.youtube.com/watch?v=x0uinJvhNxI"},
    ],
    "sql": [
        {"type": "Course", "title": "SQL Tutorial — freeCodeCamp (4h)", "url": "https://www.youtube.com/watch?v=HXV3zeQKqGY"},
        {"type": "Doc", "title": "PostgreSQL Tutorial", "url": "https://www.postgresqltutorial.com/"},
        {"type": "Course", "title": "SQLBolt — Interactive SQL lessons", "url": "https://sqlbolt.com/"},
    ],
    "html": [
        {"type": "Course", "title": "HTML Full Course — freeCodeCamp", "url": "https://www.freecodecamp.org/learn/2022/responsive-web-design/"},
        {"type": "Doc", "title": "MDN HTML Basics", "url": "https://developer.mozilla.org/en-US/docs/Learn/Getting_started_with_the_web/HTML_basics"},
        {"type": "Video", "title": "HTML & CSS Full Course — SuperSimpleDev (6h)", "url": "https://www.youtube.com/watch?v=G3e-cpL7ofc"},
    ],
    "css": [
        {"type": "Course", "title": "CSS Full Course — freeCodeCamp", "url": "https://www.freecodecamp.org/learn/2022/responsive-web-design/"},
        {"type": "Video", "title": "CSS Flexbox & Grid — Kevin Powell", "url": "https://www.youtube.com/watch?v=JJSoEo8JSnc"},
        {"type": "Doc", "title": "MDN CSS Guide", "url": "https://developer.mozilla.org/en-US/docs/Learn/CSS"},
    ],
    "kubernetes": [
        {"type": "Video", "title": "Kubernetes Tutorial — TechWorld with Nana (4h)", "url": "https://www.youtube.com/watch?v=X48VuDVv0do"},
        {"type": "Course", "title": "Kubernetes The Hard Way", "url": "https://github.com/kelseyhightower/kubernetes-the-hard-way"},
        {"type": "Doc", "title": "Kubernetes Basics (official)", "url": "https://kubernetes.io/docs/tutorials/kubernetes-basics/"},
    ],
    "llm": [
        {"type": "Course", "title": "LLM University — Cohere (free)", "url": "https://docs.cohere.com/docs/llmu"},
        {"type": "Video", "title": "Build LLM Apps — freeCodeCamp (5h)", "url": "https://www.youtube.com/watch?v=jXiiSIPD2MU"},
        {"type": "Course", "title": "Prompt Engineering Guide", "url": "https://www.promptingguide.ai/"},
    ],
    "computer vision": [
        {"type": "Course", "title": "CS231n: CNNs for Visual Recognition (Stanford, free)", "url": "https://cs231n.stanford.edu/"},
        {"type": "Video", "title": "OpenCV Python Tutorial — freeCodeCamp (6h)", "url": "https://www.youtube.com/watch?v=oXlwWbU8l2o"},
        {"type": "Doc", "title": "OpenCV Python Tutorials", "url": "https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html"},
    ],
    "nlp": [
        {"type": "Course", "title": "CS224N: NLP with Deep Learning (Stanford, free)", "url": "https://web.stanford.edu/class/cs224n/"},
        {"type": "Course", "title": "Hugging Face NLP Course (free)", "url": "https://huggingface.co/learn/nlp-course"},
        {"type": "Video", "title": "NLP Full Course — freeCodeCamp", "url": "https://www.youtube.com/watch?v=dIUTsFT2MeQ"},
    ],
    "data science": [
        {"type": "Course", "title": "Data Analysis with Python — freeCodeCamp", "url": "https://www.freecodecamp.org/learn/data-analysis-with-python/"},
        {"type": "Video", "title": "Data Science Full Course — freeCodeCamp (12h)", "url": "https://www.youtube.com/watch?v=ua-CiDNNj30"},
        {"type": "Course", "title": "Kaggle Learn — Intro to ML (free)", "url": "https://www.kaggle.com/learn/intro-to-machine-learning"},
    ],
    "api": [
        {"type": "Doc", "title": "REST API Design Best Practices", "url": "https://restfulapi.net/"},
        {"type": "Video", "title": "APIs for Beginners — freeCodeCamp (2h)", "url": "https://www.youtube.com/watch?v=GZvSYJDk-us"},
        {"type": "Doc", "title": "Postman Learning Center", "url": "https://learning.postman.com/docs/getting-started/overview/"},
    ],
    "web3": [
        {"type": "Course", "title": "Solidity Full Course — freeCodeCamp (16h)", "url": "https://www.youtube.com/watch?v=gyMwXuJrbJQ"},
        {"type": "Course", "title": "CryptoZombies — Learn Solidity by building games", "url": "https://cryptozombies.io/"},
        {"type": "Doc", "title": "Ethereum Developer Docs", "url": "https://ethereum.org/en/developers/docs/"},
    ],
    "solidity": [
        {"type": "Course", "title": "Solidity by Example", "url": "https://solidity-by-example.org/"},
        {"type": "Course", "title": "CryptoZombies", "url": "https://cryptozombies.io/"},
        {"type": "Video", "title": "Solidity Full Course — Patrick Collins (32h)", "url": "https://www.youtube.com/watch?v=gyMwXuJrbJQ"},
    ],
    "unity": [
        {"type": "Course", "title": "Unity Beginner Tutorial — Brackeys", "url": "https://www.youtube.com/watch?v=j48LtUkZRjU&list=PLPV2KyIb3jR5QFsefuO2RlAgWEz6EvVi6"},
        {"type": "Doc", "title": "Unity Learn (official, free)", "url": "https://learn.unity.com/"},
        {"type": "Video", "title": "Unity Full Course — freeCodeCamp (5h)", "url": "https://www.youtube.com/watch?v=gB1F9G0JXOo"},
    ],
    "c#": [
        {"type": "Course", "title": "C# Full Course — freeCodeCamp (4h)", "url": "https://www.youtube.com/watch?v=GhQdlMFylQ8"},
        {"type": "Doc", "title": "C# Docs (Microsoft)", "url": "https://learn.microsoft.com/en-us/dotnet/csharp/"},
        {"type": "Course", "title": "C# Tutorial — W3Schools", "url": "https://www.w3schools.com/cs/"},
    ],
}

GENERIC_TEMPLATE = [
    {
        "type": "Course",
        "title": "freeCodeCamp search",
        "url_template": "https://www.youtube.com/@freecodecamp/search?query={query}",
    },
    {
        "type": "Doc",
        "title": "MDN Web Docs search",
        "url_template": "https://developer.mozilla.org/en-US/search?q={query}",
    },
    {
        "type": "Course",
        "title": "Kaggle Learn search",
        "url_template": "https://www.kaggle.com/search?q={query}",
    },
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_bridge_roadmap(
    skill_gap: list[str],
    *,
    days: int = 7,
    use_llm: bool = True,
) -> list[BridgeRoadmapDay]:
    """Build a `days`-long bridge roadmap from a skill gap list.

    Returns an empty list if there's no gap to close — the caller decides
    whether to render an empty roadmap or skip the section entirely.
    """
    if not skill_gap:
        return []

    if use_llm:
        try:
            llm_days = _generate_with_llm(skill_gap=skill_gap, days=days)
            if llm_days:
                return llm_days
        except Exception as exc:  # noqa: BLE001
            logger.warning("roadmap_crew: LLM path failed (%s) — using fallback", exc)

    return _fallback_roadmap(skill_gap, days=days)


def attach_roadmap_to_opportunity(
    opp: Opportunity, *, use_llm: bool = True
) -> Opportunity:
    """Convenience: build a roadmap from `opp.readiness_engine.skill_gap_identified`
    and return a new `Opportunity` with `bridge_roadmap` populated.
    """
    roadmap = generate_bridge_roadmap(
        list(opp.readiness_engine.skill_gap_identified), use_llm=use_llm
    )
    return opp.model_copy(
        update={
            "readiness_engine": ReadinessEngine(
                skill_gap_identified=list(opp.readiness_engine.skill_gap_identified),
                bridge_roadmap=roadmap,
            )
        }
    )


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------


def _fallback_roadmap(skill_gap: list[str], *, days: int) -> list[BridgeRoadmapDay]:
    """Round-robin the skill gap across `days`, attaching curated resources."""
    if not skill_gap:
        return []
    days = max(1, min(14, days))
    roadmap: list[BridgeRoadmapDay] = []
    for i in range(days):
        skill = skill_gap[i % len(skill_gap)]
        focus = _focus_for_day(day=i + 1, skill=skill, days=days)
        resources = _resources_for_skill(skill)
        roadmap.append(
            BridgeRoadmapDay(
                day=i + 1,
                focus=focus,
                resources=resources,
            )
        )
    return roadmap


def _focus_for_day(*, day: int, skill: str, days: int) -> str:
    """Stage focus by where in the week we are."""
    if day == 1:
        return f"{skill} — set up and 'hello world'"
    if day == days:
        return f"{skill} — integrate with the rest of your stack"
    if day == days - 1:
        return f"{skill} — debug + read someone else's project"
    return f"{skill} — guided exercise"


def _resources_for_skill(skill: str) -> list[Resource]:
    key = skill.lower().strip()
    curated = CURATED_RESOURCES.get(key)
    if curated:
        return [Resource(**r) for r in curated]  # type: ignore[arg-type]
    # Generic fallback — at least one valid HTTP URL is required by the schema.
    query = re.sub(r"\s+", "+", skill.strip())
    return [
        Resource(
            type=tpl["type"],  # type: ignore[arg-type]
            title=f"{tpl['title']}: {skill}",
            url=tpl["url_template"].format(query=query),  # type: ignore[arg-type]
        )
        for tpl in GENERIC_TEMPLATE
    ]


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------


def _generate_with_llm(*, skill_gap: list[str], days: int) -> list[BridgeRoadmapDay]:
    """Ask the creative LLM for a strict-JSON roadmap, then validate it.

    Returns `[]` rather than raising on parse errors so the caller's fallback
    runs without surfacing the noisy traceback. We DO raise for hard LLM
    crashes (network/timeout) so the caller can log them.
    """
    from crewai import Agent, Crew, Process, Task

    from astra_agents.llm import get_creative_llm

    skills_text = ", ".join(skill_gap)

    planner = Agent(
        role="Hackathon Bridge Planner",
        goal=(
            f"Plan a {days}-day learning sprint that closes the user's skill gap "
            "before a hackathon deadline. Output STRICT JSON only — no prose."
        ),
        backstory=(
            "You design week-long bridges from where someone is to where they "
            "need to be for a specific deadline. You favor concrete, tested "
            "resources (docs, well-known repos, top YouTube tutorials) over "
            "vague advice. You never invent URLs."
        ),
        llm=get_creative_llm(),
        allow_delegation=False,
        verbose=False,
    )
    task = Task(
        description=(
            f"SKILL GAP: {skills_text}\n"
            f"DAYS: {days}\n\n"
            "Output a JSON array of exactly DAYS items. Each item is an object: "
            '{"day": <int 1..DAYS>, "focus": "<short string>", '
            '"resources": [{"type": "Video|Doc|Repo|Course|Article", '
            '"title": "<string>", "url": "<https URL>"}]}. '
            "Each day must have at least one resource. Output ONLY the JSON "
            "array — no markdown, no prose, no comments."
        ),
        expected_output="A JSON array matching the BridgeRoadmapDay schema.",
        agent=planner,
    )
    crew = Crew(agents=[planner], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    raw = (getattr(result, "raw", None) or str(result)).strip()

    parsed = _parse_roadmap_json(raw)
    if not parsed:
        return []
    return parsed


def _parse_roadmap_json(raw: str) -> list[BridgeRoadmapDay]:
    """Best-effort: strip fences, find the first JSON array, validate items."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").lstrip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1:
        return []
    blob = cleaned[start : end + 1]
    try:
        data: list[dict[str, Any]] = json.loads(blob)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[BridgeRoadmapDay] = []
    for item in data:
        try:
            out.append(BridgeRoadmapDay.model_validate(item))
        except Exception:  # noqa: BLE001 — drop invalid days; better than corrupting the lot
            continue
    return out


__all__ = [
    "attach_roadmap_to_opportunity",
    "generate_bridge_roadmap",
]
