"""Lower-level runtime infrastructure for the chat agents.

Modules here are the foundation layer used to *run* chat agents: wired by the
boundary (routes/tasks) and/or imported by the agent factory + shared
middleware, but never part of any single agent's domain logic. Because they sit
below the agent packages, both the boundary and the agents may depend on them
(forward dependency), while they never import agent code.

Contents:
- ``checkpointer``      LangGraph Postgres checkpoint saver (boundary lifespan)
- ``llm_config``        LLM provider/model configuration resolution
- ``prompt_caching``    LiteLLM prompt-caching configuration
- ``errors``            agent-runtime error contracts (raised by MW, caught at boundary)
- ``path_resolver``     filesystem path resolution helpers
- ``mention_resolver``  @-mention resolution helpers
"""
