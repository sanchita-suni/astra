"""Keyword-based skill extraction from resume text.

Pure Python, no LLM, no I/O. Extracts skills, education, and an experience
summary from raw text (typically extracted from a PDF via pypdf).

The skill list is intentionally curated rather than exhaustive — matching
against hackathon `raw_requirements` is keyword-based, so the skills here
should be the same tokens that appear in opportunity listings.
"""

from __future__ import annotations

import re

from astra_schemas import ResumeSkills

# ~200 common tech skills that appear in hackathon requirements.
# Keep this alphabetically sorted for maintainability.
KNOWN_SKILLS: set[str] = {
    "angular", "ansible", "api", "arduino", "aws", "azure", "bash",
    "bootstrap", "c", "c#", "c++", "celery", "ci/cd", "cmake", "computer vision",
    "cpp", "css", "cuda", "dart", "deep learning", "devops", "django",
    "docker", "electron", "elixir", "express", "fastapi", "figma",
    "firebase", "flask", "flutter", "gcp", "git", "go", "golang",
    "graphql", "hadoop", "haskell", "html", "huggingface", "ios",
    "java", "javascript", "jenkins", "julia", "jupyter", "kafka",
    "keras", "kotlin", "kubernetes", "langchain", "linux", "llm",
    "lua", "machine learning", "matlab", "ml", "mongodb", "mysql",
    "natural language processing", "next.js", "nextjs", "nlp", "node.js",
    "nodejs", "nosql", "numpy", "opencv", "opengl", "pandas", "perl",
    "php", "postgresql", "postman", "power bi", "python", "pytorch",
    "r", "raspberry pi", "react", "react native", "redis", "rest api",
    "ruby", "rust", "sass", "scala", "scikit-learn", "sklearn",
    "solidity", "spark", "spring", "sql", "svelte", "swift",
    "tailwind", "tensorflow", "terraform", "three.js", "typescript",
    "unity", "unreal engine", "vercel", "vue", "vuejs",
    "web3", "websocket", "yolov8",
}

EDUCATION_KEYWORDS = {
    "bachelor", "b.s.", "b.sc", "b.tech", "b.e.",
    "master", "m.s.", "m.sc", "m.tech", "m.e.", "mba",
    "phd", "ph.d", "doctorate",
    "university", "college", "institute", "bootcamp", "diploma",
}

EXPERIENCE_VERBS = {
    "built", "developed", "designed", "implemented", "created",
    "led", "managed", "shipped", "deployed", "architected",
    "optimized", "automated", "integrated", "maintained",
    "researched", "published", "contributed", "founded",
}


def extract_skills_from_text(text: str) -> ResumeSkills:
    """Extract skills, education, and experience summary from resume text.

    Pure keyword matching — no LLM required. Good enough for matching against
    hackathon requirements, which are also keyword-based.
    """
    if not text or not text.strip():
        return ResumeSkills(skills=[], education=[], experience_summary="")

    text_lower = text.lower()
    words_set = set(re.findall(r"\b\w[\w.#+]*\b", text_lower))

    # --- Skills ---
    found_skills: list[str] = []
    seen: set[str] = set()
    for skill in sorted(KNOWN_SKILLS):
        if skill in seen:
            continue
        # Multi-word skills need substring match; single-word need exact match
        if " " in skill or "." in skill or "#" in skill or "+" in skill:
            if skill in text_lower:
                found_skills.append(skill)
                seen.add(skill)
        elif len(skill) <= 2:
            # Very short tokens (C, R) need word-boundary match
            if re.search(r"\b" + re.escape(skill) + r"\b", text_lower):
                found_skills.append(skill)
                seen.add(skill)
        elif skill in words_set:
            found_skills.append(skill)
            seen.add(skill)

    # --- Education ---
    sentences = re.split(r"[.!?\n]", text)
    education: list[str] = []
    for sent in sentences:
        sent_lower = sent.lower().strip()
        if any(kw in sent_lower for kw in EDUCATION_KEYWORDS):
            cleaned = sent.strip()
            if len(cleaned) > 10 and len(cleaned) < 300:
                education.append(cleaned)
                if len(education) >= 3:
                    break

    # --- Experience summary ---
    experience_sents: list[str] = []
    for sent in sentences:
        sent_lower = sent.lower().strip()
        if any(verb in sent_lower for verb in EXPERIENCE_VERBS):
            cleaned = sent.strip()
            if len(cleaned) > 20 and len(cleaned) < 300:
                experience_sents.append(cleaned)
                if len(experience_sents) >= 3:
                    break
    experience_summary = ". ".join(experience_sents)
    if experience_summary and not experience_summary.endswith("."):
        experience_summary += "."

    return ResumeSkills(
        skills=found_skills,
        education=education,
        experience_summary=experience_summary or "No experience details extracted.",
        extraction_source="keyword",
    )
