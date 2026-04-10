"""Astra core algorithms.

Pure-Python, framework-free, deterministic. Everything in this package is
unit-testable without a database, network, or LLM. The CrewAI crews import
from here as plain Python — no @tool decorators yet.
"""

from astra_core.deadman import DeadmanInputs, DeadmanResult, compute_deadman_alert
from astra_core.proof_of_work import ProofOfWork, build_proof_of_work
from astra_core.trust_score import TrustScoreBreakdown, compute_trust_score

__all__ = [
    "DeadmanInputs",
    "DeadmanResult",
    "ProofOfWork",
    "TrustScoreBreakdown",
    "build_proof_of_work",
    "compute_deadman_alert",
    "compute_trust_score",
]
