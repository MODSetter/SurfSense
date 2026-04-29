# `multi_agent_chat` — vertical slices + shared

```
multi_agent_chat/
  __init__.py

  shared/                     # Cross-domain helpers (one level)
    deps.py                   # connector_binding for new_chat factories
    prompt_loader.py          # read_prompt_md(package, stem)
    domain_agent_factory.py   # build_domain_agent(..., prompt_package=...)
    invoke_output.py          # extract_last_assistant_text (invoke result parsing)

  gmail/                      # Gmail slice (agent + tooling + prompt)
    domain_prompt.md
    connector_tools.py
    agent.py

  calendar/                   # Google Calendar slice
    domain_prompt.md
    connector_tools.py
    agent.py

  routing/
    from_domain_agents.py
    supervisor_routing.py

  supervisor/
    supervisor_prompt.md
    graph.py

  integration/
    create_multi_agent_chat.py
```

**References:** [Multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent), [Subagents](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents).
