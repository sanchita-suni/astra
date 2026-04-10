"""CrewAI crews — one module per role.

Day 1: scout_crew (validates schema round-trip).
Day 3: analyst_crew, roadmap_crew, vault_crew (the personalization layer).
Day 4: builder_crew (USP A) and judge_crew (USP B).

Every crew here MUST follow the scout_crew pattern: try the LLM path, fall
back deterministically. The fallback is the testable contract; the LLM path
is the polish layer.
"""
