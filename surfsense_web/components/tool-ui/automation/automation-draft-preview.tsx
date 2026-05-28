"use client";
import { CalendarClock, ChevronDown, ChevronRight, ListOrdered, Target } from "lucide-react";
import { useState } from "react";
import { describeCron } from "@/lib/automations/describe-cron";

interface DraftTrigger {
	type: string;
	params: Record<string, unknown>;
	static_inputs: Record<string, unknown>;
	enabled: boolean;
}

interface DraftPlanStep {
	step_id: string;
	action: string;
	when?: string | null;
}

interface AutomationDraft {
	name: string;
	description?: string | null;
	definition: {
		goal?: string | null;
		plan: DraftPlanStep[];
	};
	triggers: DraftTrigger[];
}

interface AutomationDraftPreviewProps {
	draft: AutomationDraft;
	/** Full unmodified args dict — surfaced as the "raw JSON" escape hatch. */
	raw: Record<string, unknown>;
}

/**
 * Structured preview of a drafted automation rendered inside the chat
 * approval card.
 *
 * Three layers, top to bottom:
 *   1. Name + description (and goal when present).
 *   2. Triggers — humanised cron string + timezone + static_inputs hint.
 *   3. Plan steps — ordered list of ``step_id → action``.
 *
 * A "View raw JSON" toggle reveals the full payload for power users who
 * want to inspect every field; it's collapsed by default so the card
 * stays scannable for the common case.
 */
export function AutomationDraftPreview({ draft, raw }: AutomationDraftPreviewProps) {
	const [showRaw, setShowRaw] = useState(false);

	return (
		<div className="space-y-4 text-sm">
			<div className="space-y-1">
				<p className="font-medium text-foreground">{draft.name}</p>
				{draft.description && <p className="text-xs text-muted-foreground">{draft.description}</p>}
			</div>

			{draft.definition.goal && (
				<Section icon={Target} label="Goal">
					<p className="text-xs text-foreground">{draft.definition.goal}</p>
				</Section>
			)}

			<Section icon={CalendarClock} label={`Triggers · ${draft.triggers.length}`}>
				{draft.triggers.length === 0 ? (
					<p className="text-xs text-muted-foreground">
						No triggers — automation will need one before it can run.
					</p>
				) : (
					<ul className="space-y-1.5">
						{draft.triggers.map((trigger) => (
							<li
								key={triggerKey(trigger)}
								className="rounded-md border border-border/60 bg-background/50 px-3 py-2 text-xs"
							>
								<TriggerLine trigger={trigger} />
							</li>
						))}
					</ul>
				)}
			</Section>

			<Section
				icon={ListOrdered}
				label={`Plan · ${draft.definition.plan.length} step${draft.definition.plan.length === 1 ? "" : "s"}`}
			>
				<ol className="space-y-1 text-xs">
					{draft.definition.plan.map((step, idx) => (
						<li key={step.step_id} className="flex items-start gap-2">
							<span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-muted text-[10px] font-medium text-muted-foreground shrink-0 mt-0.5">
								{idx + 1}
							</span>
							<div className="min-w-0">
								<span className="font-medium text-foreground">{step.step_id}</span>
								<span className="text-muted-foreground"> → </span>
								<code className="font-mono text-muted-foreground">{step.action}</code>
								{step.when && <span className="ml-2 text-muted-foreground">when {step.when}</span>}
							</div>
						</li>
					))}
				</ol>
			</Section>

			<button
				type="button"
				onClick={() => setShowRaw((value) => !value)}
				className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
			>
				{showRaw ? (
					<ChevronDown className="h-3 w-3" aria-hidden />
				) : (
					<ChevronRight className="h-3 w-3" aria-hidden />
				)}
				{showRaw ? "Hide raw JSON" : "View raw JSON"}
			</button>
			{showRaw && (
				<pre className="rounded-md bg-muted/40 px-3 py-2 text-[11px] font-mono text-foreground overflow-x-auto whitespace-pre-wrap break-words max-h-72">
					{JSON.stringify(raw, null, 2)}
				</pre>
			)}
		</div>
	);
}

/**
 * Stable key derived from the trigger's identifying fields. Drafts are
 * static snapshots so collisions only happen if the LLM emits two literally
 * identical triggers — harmless in practice.
 */
function triggerKey(trigger: DraftTrigger): string {
	const cron = typeof trigger.params.cron === "string" ? trigger.params.cron : "";
	const tz = typeof trigger.params.timezone === "string" ? trigger.params.timezone : "";
	return `${trigger.type}|${cron}|${tz}`;
}

function TriggerLine({ trigger }: { trigger: DraftTrigger }) {
	if (trigger.type === "schedule") {
		const cron = typeof trigger.params.cron === "string" ? trigger.params.cron : undefined;
		const tz = typeof trigger.params.timezone === "string" ? trigger.params.timezone : "UTC";
		const human = cron ? describeCron(cron) : "Schedule";
		const staticKeys = Object.keys(trigger.static_inputs ?? {});
		return (
			<div className="space-y-1">
				<div className="flex items-center gap-2 flex-wrap">
					<span className="font-medium text-foreground">{human}</span>
					<span className="text-muted-foreground">· {tz}</span>
					{!trigger.enabled && (
						<span className="rounded-md border border-border/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
							Disabled
						</span>
					)}
				</div>
				{cron && <code className="font-mono text-muted-foreground">{cron}</code>}
				{staticKeys.length > 0 && (
					<p className="text-muted-foreground">
						Static inputs: <span className="text-foreground">{staticKeys.join(", ")}</span>
					</p>
				)}
			</div>
		);
	}
	return <span className="capitalize text-foreground">{trigger.type}</span>;
}

function Section({
	icon: Icon,
	label,
	children,
}: {
	icon: typeof Target;
	label: string;
	children: React.ReactNode;
}) {
	return (
		<div className="space-y-1.5">
			<div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
				<Icon className="h-3 w-3" aria-hidden />
				{label}
			</div>
			{children}
		</div>
	);
}
