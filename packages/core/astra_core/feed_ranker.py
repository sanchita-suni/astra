"""Personalized feed ranking — scores opportunities against a user's skill profile.

Two matching modes:
1. **Semantic (FAISS + sentence-transformers)**: embeds user profile + opportunity
   requirements and uses cosine similarity. More accurate, catches "PyTorch" ≈ "Deep Learning".
2. **Keyword fallback**: set intersection when the embedder isn't available.

The ranker combines skills from three sources:
- GitHub languages + repo topics (from ProofOfWork)
- Resume skills (from keyword extraction)
- Questionnaire "skills to learn" (aspirational, weighted lower)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from astra_schemas import Opportunity, QuestionnaireResponse, ResumeSkills

logger = logging.getLogger("astra.feed_ranker")

# Lazy-loaded embedder so tests don't need sentence-transformers
_embedder = None


def _get_embedder():
    """Lazy-load the sentence-transformers embedder."""
    global _embedder
    if _embedder is None:
        try:
            from astra_vectorstore.embedder import get_default_embedder
            _embedder = get_default_embedder()
            logger.info("FAISS embedder loaded for semantic matching")
        except Exception as exc:
            logger.warning("Embedder not available, using keyword fallback: %s", exc)
    return _embedder


def _collect_user_skills(
    github_languages: list[str] | None = None,
    resume: ResumeSkills | None = None,
    questionnaire: QuestionnaireResponse | None = None,
) -> set[str]:
    """Union all skill signals into one case-insensitive set."""
    skills: set[str] = set()
    if github_languages:
        skills.update(l.lower() for l in github_languages)
    if resume:
        skills.update(s.lower() for s in resume.skills)
    if questionnaire:
        skills.update(s.lower() for s in questionnaire.skills_to_learn)
    return skills


def _build_user_text(
    github_languages: list[str] | None = None,
    resume: ResumeSkills | None = None,
    questionnaire: QuestionnaireResponse | None = None,
) -> str:
    """Build a natural-language description of the user for embedding."""
    parts: list[str] = []
    if github_languages:
        parts.append("Languages: " + ", ".join(github_languages))
    if resume and resume.skills:
        parts.append("Resume skills: " + ", ".join(resume.skills))
    if resume and resume.experience_summary:
        parts.append(resume.experience_summary)
    if questionnaire:
        parts.append(f"Experience: {questionnaire.experience_level}")
        if questionnaire.skills_to_learn:
            parts.append("Wants to learn: " + ", ".join(questionnaire.skills_to_learn))
        if questionnaire.preferred_types:
            parts.append("Interests: " + ", ".join(questionnaire.preferred_types))
    return " | ".join(parts) if parts else "general developer"


def _build_opp_text(opp: Opportunity) -> str:
    """Build a natural-language description of the opportunity for embedding."""
    parts = [
        opp.metadata.title,
        opp.metadata.organization,
        " ".join(opp.metadata.raw_requirements),
    ]
    return " | ".join(p for p in parts if p)


def _semantic_score(user_text: str, opp_text: str) -> float:
    """Cosine similarity between user and opportunity embeddings (0-1)."""
    import numpy as np
    embedder = _get_embedder()
    if embedder is None:
        return -1.0  # signal to use keyword fallback
    u = embedder.encode_one(user_text)
    o = embedder.encode_one(opp_text)
    return float(np.dot(u, o))  # already L2-normalized = cosine similarity


def _keyword_score(requirements: list[str], user_skills: set[str]) -> float:
    """Fraction of requirements covered by user skills (0-1)."""
    if not requirements:
        return 0.5  # neutral
    needed = {r.lower() for r in requirements if r}
    if not needed:
        return 0.5
    overlap = len(needed & user_skills)
    return overlap / len(needed)


def score_opportunity(
    opp: Opportunity,
    user_skills: set[str],
    preferred_types: list[str] | None = None,
    hours_per_week: int = 10,
    user_text: str | None = None,
) -> float:
    """Score a single opportunity 0-100 for a user.

    Components:
    - Skill match (45%): semantic or keyword overlap
    - Type preference (15%): bonus if themes match preferred types
    - Time fit (20%): penalty if user doesn't have enough hours
    - Freshness (20%): prefer further-out deadlines
    """
    requirements = [r.lower() for r in opp.metadata.raw_requirements]

    # --- Skill match (0-45) ---
    if user_text:
        opp_text = _build_opp_text(opp)
        sim = _semantic_score(user_text, opp_text)
        if sim >= 0:
            skill_score = sim * 45  # cosine sim is 0-1
        else:
            skill_score = _keyword_score(requirements, user_skills) * 45
    else:
        skill_score = _keyword_score(requirements, user_skills) * 45

    # --- Type preference (0-15) ---
    type_score = 7.5  # neutral default
    if preferred_types:
        pref_lower = {t.lower().replace("-", " ") for t in preferred_types}
        req_text = " ".join(requirements)
        title_lower = opp.metadata.title.lower()
        ml_words = {"ml", "ai", "machine learning", "deep learning", "tensorflow", "pytorch", "llm"}
        web_words = {"react", "next", "web", "javascript", "typescript", "frontend"}

        if "ai ml" in pref_lower or "ai-ml" in pref_lower:
            if any(w in req_text or w in title_lower for w in ml_words):
                type_score = 15.0
        if "web" in pref_lower:
            if any(w in req_text or w in title_lower for w in web_words):
                type_score = 15.0
        for p in pref_lower:
            if p in req_text or p in title_lower:
                type_score = 15.0
                break

    # --- Time fit (0-20) ---
    now = datetime.now(timezone.utc)
    deadline = opp.metadata.deadline_iso
    if hasattr(deadline, 'tzinfo') and deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    days_left = max(0, (deadline - now).days)
    hours_available = days_left * (hours_per_week / 7)
    hours_needed = opp.execution_intel.estimated_hours_required
    if hours_available >= hours_needed:
        time_score = 20.0
    elif hours_available >= hours_needed * 0.5:
        time_score = 12.0
    else:
        time_score = 5.0

    # --- Freshness (0-20) ---
    if days_left <= 0:
        freshness_score = 0.0
    elif days_left <= 2:
        freshness_score = 5.0
    elif days_left <= 7:
        freshness_score = 12.0
    elif days_left <= 30:
        freshness_score = 18.0
    else:
        freshness_score = 20.0

    total = skill_score + type_score + time_score + freshness_score
    return round(max(0, min(100, total)), 1)


def rank_opportunities(
    opportunities: list[Opportunity],
    *,
    github_languages: list[str] | None = None,
    resume: ResumeSkills | None = None,
    questionnaire: QuestionnaireResponse | None = None,
) -> list[tuple[Opportunity, float]]:
    """Rank opportunities by match score, descending. Excludes expired ones."""
    user_skills = _collect_user_skills(github_languages, resume, questionnaire)
    user_text = _build_user_text(github_languages, resume, questionnaire)
    preferred_types = list(questionnaire.preferred_types) if questionnaire else None
    hours = int(questionnaire.hours_per_week.replace("+", "")) if questionnaire else 10

    now = datetime.now(timezone.utc)
    scored: list[tuple[Opportunity, float]] = []
    for opp in opportunities:
        deadline = opp.metadata.deadline_iso
        if hasattr(deadline, 'tzinfo') and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline < now:
            continue
        score = score_opportunity(
            opp, user_skills, preferred_types, hours, user_text=user_text
        )
        scored.append((opp, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
