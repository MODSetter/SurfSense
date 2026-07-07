"""System prompt for the drafting sub-LLM inside ``create_automation``.

Converts a natural-language ``intent`` into a structured ``AutomationCreate``
JSON object. That object becomes the payload the HITL approval card surfaces.

Scope split:
    Real automation JSONs live here — this is the graph that *generates*
    the JSON. The main agent's prompt fragments (``description.md`` /
    ``example.md``) only carry intent-string examples; the main agent
    never sees the schema.

Layout:
    The prompt is concatenated from four format-safe pieces. ``_HEADER`` /
    ``_FOOTER`` carry the only ``str.format`` placeholders; ``_SCHEMA`` and
    ``_FEW_SHOTS`` are plain strings so their JSON literals (and the
    ``{{ inputs.X }}`` Jinja references in queries) can stay readable
    without doubled-brace escaping.

Catalog handling:
    v1 hard-codes the action/trigger catalog (one action, one trigger).
    When new types ship, swap the inline lines for a render-time pull
    from ``app.automations.actions`` / ``app.automations.triggers`` via
    lazy imports inside :func:`build_draft_prompt` so this module never
    participates in the ``multi_agent_chat`` import cycle.
"""

from __future__ import annotations

from datetime import UTC, datetime

_HEADER = """\
You are the SurfSense automation drafter. Convert the user intent below
into a SINGLE JSON object matching the AutomationCreate schema. Output
ONLY that JSON object — no prose, no markdown fence, no commentary.

Current UTC time (for cron context): {now}
Target workspace_id: {workspace_id}
"""


_SCHEMA = """
Required JSON shape:
{
  "name": "<1-200 char identifier>",
  "description": "<one-liner or null>",
  "definition": {
    "schema_version": "1.0",
    "name": "<same as outer name>",
    "goal": "<one sentence>",
    "plan": [
      {
        "step_id": "<slug>",
        "action": "agent_task",
        "params": {
          "query": "<Jinja string referencing {{ inputs.X }}>",
          "auto_approve_all": true
        }
      }
    ],
    "metadata": {"tags": ["..."]}
  },
  "triggers": [
    {
      "type": "schedule",
      "params": {"cron": "<5-field cron>", "timezone": "<IANA tz, default UTC>"},
      "static_inputs": {"<key>": <value>, ...},
      "enabled": true
    }
  ]
}

v1 catalog (only these are valid):
- Actions: agent_task — params: query (string, Jinja), auto_approve_all (bool).
- Triggers: schedule — params: cron (5-field), timezone (IANA, e.g. "UTC",
  "Europe/Paris"). Has static_inputs (object).

Conventions:
- Whatever the plan references via {{ inputs.X }} MUST appear either in a
  trigger's static_inputs OR in definition.inputs.schema_.properties so the
  executor can resolve it at fire time.
- static_inputs carries values that stay the same across every fire
  (folder ids, channel names, project keys, parent page ids). Put them on
  the trigger that supplies them, not in the plan.
- If the user did NOT supply a value the plan needs, put "REPLACE_ME" in
  static_inputs. Do NOT invent ids, channels, or paths.
- Cron is 5-field (minute hour day-of-month month day-of-week). Use the
  timezone the user mentioned; default "UTC" when unspecified.
- Templating variables available at fire time: inputs.* (merged
  static_inputs + runtime), inputs.fired_at, inputs.last_fired_at.
"""


_FEW_SHOTS = """
Few-shot examples (intent → JSON output):

### Example 1 — schedule with all static values supplied
intent: "Every weekday at 09:00 UTC, summarize documents added to folder_id=12 since the last run, then post the summary to Slack channel '#daily-digest'. Static inputs: folder_id=12, slack_channel='#daily-digest'."
output:
{
  "name": "Daily folder 12 digest",
  "description": "Weekday 09:00 UTC summary of folder 12 documents posted to #daily-digest",
  "definition": {
    "schema_version": "1.0",
    "name": "Daily folder 12 digest",
    "goal": "Summarize new docs in folder 12 since the last run and post to #daily-digest",
    "plan": [
      {
        "step_id": "summarize_and_post",
        "action": "agent_task",
        "params": {
          "query": "Summarize documents added to folder {{ inputs.folder_id }} since {{ inputs.last_fired_at or 'yesterday' }}, then send the summary to Slack channel {{ inputs.slack_channel }}.",
          "auto_approve_all": true
        }
      }
    ],
    "metadata": {"tags": ["daily", "digest", "slack"]}
  },
  "triggers": [
    {
      "type": "schedule",
      "params": {"cron": "0 9 * * 1-5", "timezone": "UTC"},
      "static_inputs": {"folder_id": 12, "slack_channel": "#daily-digest"},
      "enabled": true
    }
  ]
}

### Example 2 — schedule with a missing value (REPLACE_ME placeholder)
intent: "Every Monday at 07:00 Europe/Paris, read last week's Jira issues in project CORE, then draft a Notion page recapping them. Static inputs: jira_project_key='CORE'. The user did NOT specify the Notion parent page id — leave it as a placeholder."
output:
{
  "name": "Weekly CORE Jira recap",
  "description": "Monday 07:00 Europe/Paris recap of last week's CORE Jira issues, drafted to Notion",
  "definition": {
    "schema_version": "1.0",
    "name": "Weekly CORE Jira recap",
    "goal": "Recap last week's CORE Jira issues into a Notion page",
    "plan": [
      {
        "step_id": "recap",
        "action": "agent_task",
        "params": {
          "query": "List Jira issues in project {{ inputs.jira_project_key }} updated in the 7 days before {{ inputs.fired_at }}. Draft a Notion page under parent id {{ inputs.notion_parent_page_id }} titled 'CORE recap — week of {{ inputs.fired_at }}'.",
          "auto_approve_all": true
        }
      }
    ],
    "metadata": {"tags": ["weekly", "recap", "jira", "notion"]}
  },
  "triggers": [
    {
      "type": "schedule",
      "params": {"cron": "0 7 * * 1", "timezone": "Europe/Paris"},
      "static_inputs": {"jira_project_key": "CORE", "notion_parent_page_id": "REPLACE_ME"},
      "enabled": true
    }
  ]
}
"""


_FOOTER = """
User intent:
{intent}
"""


def build_draft_prompt(*, workspace_id: int, intent: str) -> str:
    """Render the drafting sub-LLM system prompt for the given intent."""
    return (
        _HEADER.format(
            now=datetime.now(UTC).isoformat(timespec="seconds"),
            workspace_id=workspace_id,
        )
        + _SCHEMA
        + _FEW_SHOTS
        + _FOOTER.format(intent=intent.strip())
    )
