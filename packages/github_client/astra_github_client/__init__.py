"""Thin PyGithub wrapper.

Used by:
- USP D Vault — narrating user repos
- USP A Bridge-to-Build — creating starter repos under the user's account
- Trust Score — extracting commit cadence + language stats

The point of having a single wrapper module is so the rest of Astra never
imports `github` directly. That keeps rate-limit handling, auth, and mock
boundaries centralized.
"""

from astra_github_client.client import GitHubClient, RepoSummary, UserSummary

__all__ = ["GitHubClient", "RepoSummary", "UserSummary"]
