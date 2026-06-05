"""Agent runtime infrastructure wired by the boundary (not agent code).

Modules here are cross-agent infra used to *run* agents (e.g. the LangGraph
Postgres checkpointer), as opposed to ``app/agents/shared/`` which holds code
imported by 2+ sibling agent packages.
"""
