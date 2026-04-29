"use client";

import { useAtomValue } from "jotai";
import { CircleCheck, CircleSlash, Cog, RotateCcw } from "lucide-react";
import { useMemo } from "react";
import { agentFlagsAtom } from "@/atoms/agent/agent-flags-query.atom";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import type { AgentFeatureFlags } from "@/lib/apis/agent-flags-api.service";
import { cn } from "@/lib/utils";

type FlagKey = keyof AgentFeatureFlags;

interface FlagDef {
	key: FlagKey;
	label: string;
	description: string;
	envVar: string;
}

interface FlagGroup {
	id: string;
	title: string;
	subtitle: string;
	flags: FlagDef[];
}

const FLAG_GROUPS: FlagGroup[] = [
	{
		id: "tier1",
		title: "Tier 1 — Agent quality",
		subtitle: "Context editing, retries, fallbacks, doom-loop, tool-call repair.",
		flags: [
			{
				key: "enable_context_editing",
				label: "Context editing",
				description: "Trim tool outputs and spill old text into backend storage.",
				envVar: "SURFSENSE_ENABLE_CONTEXT_EDITING",
			},
			{
				key: "enable_compaction_v2",
				label: "Compaction v2",
				description: "SurfSense-aware compaction replacing safe summarization.",
				envVar: "SURFSENSE_ENABLE_COMPACTION_V2",
			},
			{
				key: "enable_retry_after",
				label: "Retry-After",
				description: "Honour rate-limit retry-after headers automatically.",
				envVar: "SURFSENSE_ENABLE_RETRY_AFTER",
			},
			{
				key: "enable_model_fallback",
				label: "Model fallback",
				description: "Fail over to a backup model on persistent errors.",
				envVar: "SURFSENSE_ENABLE_MODEL_FALLBACK",
			},
			{
				key: "enable_model_call_limit",
				label: "Model call limit",
				description: "Cap total model calls per turn to prevent budget run-aways.",
				envVar: "SURFSENSE_ENABLE_MODEL_CALL_LIMIT",
			},
			{
				key: "enable_tool_call_limit",
				label: "Tool call limit",
				description: "Cap total tool calls per turn.",
				envVar: "SURFSENSE_ENABLE_TOOL_CALL_LIMIT",
			},
			{
				key: "enable_tool_call_repair",
				label: "Tool-call name repair",
				description: "Recover from lower-cased / fuzzy tool names emitted by smaller models.",
				envVar: "SURFSENSE_ENABLE_TOOL_CALL_REPAIR",
			},
			{
				key: "enable_doom_loop",
				label: "Doom-loop detection",
				description: "Detect repeated identical tool calls and ask the user to confirm.",
				envVar: "SURFSENSE_ENABLE_DOOM_LOOP",
			},
		],
	},
	{
		id: "tier2",
		title: "Tier 2 — Safety",
		subtitle: "Permission rules, busy-mutex, smarter tool selection.",
		flags: [
			{
				key: "enable_permission",
				label: "Permission middleware",
				description: "Apply allow/deny/ask rules from the Agent Permissions tab.",
				envVar: "SURFSENSE_ENABLE_PERMISSION",
			},
			{
				key: "enable_busy_mutex",
				label: "Busy mutex",
				description: "Prevent two concurrent runs from corrupting the same thread.",
				envVar: "SURFSENSE_ENABLE_BUSY_MUTEX",
			},
			{
				key: "enable_llm_tool_selector",
				label: "LLM tool selector",
				description: "Use a smaller model to pre-filter the tool list per turn.",
				envVar: "SURFSENSE_ENABLE_LLM_TOOL_SELECTOR",
			},
		],
	},
	{
		id: "tier4",
		title: "Tier 4 — Skills + subagents",
		subtitle: "Built-in skills, specialized subagents, KB planner runnable.",
		flags: [
			{
				key: "enable_skills",
				label: "Skills",
				description: "Load on-demand skill packs (kb-research, report-writing, …).",
				envVar: "SURFSENSE_ENABLE_SKILLS",
			},
			{
				key: "enable_specialized_subagents",
				label: "Specialized subagents",
				description: "Spin up explore / report_writer / connector_negotiator subagents.",
				envVar: "SURFSENSE_ENABLE_SPECIALIZED_SUBAGENTS",
			},
			{
				key: "enable_kb_planner_runnable",
				label: "KB planner runnable",
				description: "Compile a private planner sub-agent for KB search.",
				envVar: "SURFSENSE_ENABLE_KB_PLANNER_RUNNABLE",
			},
		],
	},
	{
		id: "tier5",
		title: "Tier 5 — Audit + revert",
		subtitle: "Action log + revert route used by the Agent Actions sheet.",
		flags: [
			{
				key: "enable_action_log",
				label: "Action log",
				description: "Persist every tool call to agent_action_log.",
				envVar: "SURFSENSE_ENABLE_ACTION_LOG",
			},
			{
				key: "enable_revert_route",
				label: "Revert route",
				description: "Allow reverting reversible actions from the action log.",
				envVar: "SURFSENSE_ENABLE_REVERT_ROUTE",
			},
		],
	},
	{
		id: "tier6",
		title: "Tier 6 — Plugins",
		subtitle: "Optional middleware loaded from entry points.",
		flags: [
			{
				key: "enable_plugin_loader",
				label: "Plugin loader",
				description: "Load surfsense.plugins entry-point middleware.",
				envVar: "SURFSENSE_ENABLE_PLUGIN_LOADER",
			},
		],
	},
	{
		id: "obs",
		title: "Observability",
		subtitle: "Telemetry pipelines (orthogonal to feature gating).",
		flags: [
			{
				key: "enable_otel",
				label: "OpenTelemetry",
				description: "Emit OTel spans (also requires OTEL_EXPORTER_OTLP_ENDPOINT).",
				envVar: "SURFSENSE_ENABLE_OTEL",
			},
		],
	},
];

function FlagRow({ def, value }: { def: FlagDef; value: boolean }) {
	return (
		<div className="flex items-start justify-between gap-4 py-3">
			<div className="flex min-w-0 flex-1 flex-col gap-1">
				<div className="flex flex-wrap items-center gap-2">
					<span className="text-sm font-medium">{def.label}</span>
					<code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
						{def.envVar}
					</code>
				</div>
				<p className="text-xs text-muted-foreground">{def.description}</p>
			</div>
			<Badge
				variant={value ? "default" : "secondary"}
				className={cn(
					"shrink-0 gap-1",
					value
						? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600"
						: "text-muted-foreground"
				)}
			>
				{value ? <CircleCheck className="size-3" /> : <CircleSlash className="size-3" />}
				{value ? "On" : "Off"}
			</Badge>
		</div>
	);
}

export function AgentStatusContent() {
	const { data: flags, isLoading, isError, error, refetch } = useAtomValue(agentFlagsAtom);

	const enabledCount = useMemo(() => {
		if (!flags) return 0;
		return Object.entries(flags).filter(([k, v]) => k !== "disable_new_agent_stack" && v === true)
			.length;
	}, [flags]);

	if (isLoading) {
		return (
			<div className="flex flex-col gap-3">
				<Skeleton className="h-12 w-full rounded-md" />
				<Skeleton className="h-32 w-full rounded-md" />
				<Skeleton className="h-32 w-full rounded-md" />
			</div>
		);
	}

	if (isError || !flags) {
		return (
			<Alert variant="destructive">
				<AlertTitle>Failed to load agent status</AlertTitle>
				<AlertDescription className="flex items-center gap-2">
					{error instanceof Error ? error.message : "Unknown error."}
					<button
						type="button"
						onClick={() => refetch()}
						className="ml-auto inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs hover:bg-background"
					>
						<RotateCcw className="size-3" />
						Retry
					</button>
				</AlertDescription>
			</Alert>
		);
	}

	const masterOff = flags.disable_new_agent_stack;

	return (
		<div className="space-y-6">
			{masterOff ? (
				<Alert variant="destructive">
					<Cog className="size-4" />
					<AlertTitle>Master kill-switch is on</AlertTitle>
					<AlertDescription>
						<code className="rounded bg-muted px-1 text-[10px]">
							SURFSENSE_DISABLE_NEW_AGENT_STACK=true
						</code>
						forces every new middleware off, regardless of the individual flags below. Restart the
						backend after changing it.
					</AlertDescription>
				</Alert>
			) : (
				<Alert>
					<Cog className="size-4" />
					<AlertTitle className="flex items-center gap-2">
						Agent stack
						<Badge variant="secondary" className="text-[10px]">
							{enabledCount} on
						</Badge>
					</AlertTitle>
					<AlertDescription>
						Read-only mirror of the backend's <code>AgentFeatureFlags</code>. Flip an env var and
						restart the backend to change a value.
					</AlertDescription>
				</Alert>
			)}

			{FLAG_GROUPS.map((group, groupIdx) => {
				const allOff = group.flags.every((f) => !flags[f.key]);
				return (
					<div key={group.id}>
						{groupIdx > 0 && <Separator className="my-4" />}
						<div className="rounded-lg border border-border/60 bg-card">
							<div className="flex items-start justify-between gap-3 border-b px-4 py-3">
								<div>
									<p className="text-sm font-semibold">{group.title}</p>
									<p className="text-xs text-muted-foreground">{group.subtitle}</p>
								</div>
								{allOff && (
									<Badge variant="outline" className="text-[10px] text-muted-foreground">
										all off
									</Badge>
								)}
							</div>
							<div className="divide-y divide-border/50 px-4">
								{group.flags.map((def) => (
									<FlagRow key={def.key} def={def} value={flags[def.key]} />
								))}
							</div>
						</div>
					</div>
				);
			})}
		</div>
	);
}
