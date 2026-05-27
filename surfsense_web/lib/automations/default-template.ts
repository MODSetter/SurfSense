/**
 * Minimal valid ``AutomationCreate`` skeleton used to seed the raw-JSON
 * create form. ``search_space_id`` is omitted on purpose — the form
 * injects it from the route so users never have to know their id.
 *
 * The shape matches the Pydantic ``AutomationCreate`` model less the
 * search_space_id field; Zod validates the merged payload before submit.
 */
export const DEFAULT_AUTOMATION_TEMPLATE = {
	name: "My automation",
	description: null,
	definition: {
		name: "My automation",
		goal: null,
		plan: [
			{
				step_id: "step_1",
				action: "agent_task",
				params: {
					query: "Summarize new docs added to folder 12 since the last run.",
				},
			},
		],
		execution: {
			timeout_seconds: 600,
			max_retries: 2,
			retry_backoff: "exponential",
			concurrency: "drop_if_running",
			on_failure: [],
		},
		metadata: { tags: [] },
	},
	triggers: [
		{
			type: "schedule",
			params: {
				cron: "0 9 * * 1-5",
				timezone: "UTC",
			},
			static_inputs: {},
			enabled: true,
		},
	],
} as const;
