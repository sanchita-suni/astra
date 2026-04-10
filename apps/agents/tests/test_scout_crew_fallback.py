"""scout_crew fallback path test.

Verifies that even with LLM disabled, the scout crew returns a valid
`Opportunity`. This is the deterministic-fallback contract every crew owes:
the agent loop is allowed to fail, but the caller must always get a valid
schema object back.
"""

from __future__ import annotations

from astra_agents.crews.scout_crew import run_scout
from astra_schemas import Opportunity


def test_scout_crew_returns_valid_opportunity_without_llm() -> None:
    opp = run_scout(use_llm=False)
    assert isinstance(opp, Opportunity)
    assert opp.opportunity_id == "uuid-1234-5678-91011"
    assert opp.metadata.title == "Edge AI Innovation Challenge"
