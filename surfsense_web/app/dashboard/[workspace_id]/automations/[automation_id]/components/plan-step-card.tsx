"use client";
import type { PlanStep } from "@/contracts/types/automation.types";

interface PlanStepCardProps {
	step: PlanStep;
	index: number;
}

/**
 * Read-only view of one plan step. Keep this user-facing: summarize what the
 * step does and only show advanced step controls when they are explicitly set.
 */
export function PlanStepCard({ step, index }: PlanStepCardProps) {
	const title = getStepTitle(step);
	const details = getStepDetails(step);

	return (
		<div className="rounded-md border border-border/60 bg-background/30 px-4 py-3">
			<div className="flex items-start gap-3">
				<span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
					{index + 1}
				</span>
				<div className="min-w-0 flex-1">
					<h3 className="text-sm font-medium text-foreground">{title}</h3>
					{details.length > 0 ? (
						<dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1.5 text-xs sm:grid-cols-2">
							{details.map((detail) => (
								<DefRow key={detail.label} label={detail.label} value={detail.value} />
							))}
						</dl>
					) : null}
				</div>
			</div>
		</div>
	);
}

function DefRow({ label, value }: { label: string; value: string }) {
	return (
		<div className="flex items-baseline gap-2 min-w-0">
			<dt className="text-muted-foreground shrink-0">{label}:</dt>
			<dd className="text-foreground min-w-0 truncate">{value}</dd>
		</div>
	);
}

function getStepTitle(step: PlanStep): string {
	if (step.action === "agent_task") {
		return readStringParam(step.params, "query") ?? "Run an agent task";
	}
	return sentenceCase(formatAction(step.action));
}

function getStepDetails(step: PlanStep): { label: string; value: string }[] {
	const details: { label: string; value: string }[] = [];

	if (step.action === "agent_task") {
		if (typeof step.params.auto_approve_all === "boolean") {
			details.push({
				label: "Approval",
				value: step.params.auto_approve_all ? "Auto-approve agent actions" : "Ask before actions",
			});
		}

		const mentionSummary = summarizeMentions(step.params);
		if (mentionSummary) {
			details.push({ label: "Scope", value: mentionSummary });
		}
	} else {
		const readableParams = Object.entries(step.params)
			.filter(([, value]) => value !== null && value !== undefined && value !== "")
			.map(([key, value]) => `${sentenceCase(formatKey(key))}: ${formatValue(value)}`);
		if (readableParams.length > 0) {
			details.push({ label: "Details", value: readableParams.join(" · ") });
		}
	}

	if (step.when) details.push({ label: "Runs when", value: step.when });
	if (step.output_as) details.push({ label: "Saves output as", value: step.output_as });
	if (step.max_retries != null)
		details.push({ label: "Max retries", value: String(step.max_retries) });
	if (step.timeout_seconds != null)
		details.push({ label: "Timeout", value: `${step.timeout_seconds}s` });

	return details;
}

function readStringParam(params: Record<string, unknown>, key: string): string | null {
	const value = params[key];
	return typeof value === "string" && value.trim() ? value : null;
}

function summarizeMentions(params: Record<string, unknown>): string | null {
	const parts: string[] = [];
	addMentionTitles(parts, params.mentioned_documents, "Documents and folders");
	addMentionTitles(parts, params.mentioned_connectors, "Connectors");
	if (parts.length === 0) {
		addCount(parts, params.mentioned_document_ids, "document");
		addCount(parts, params.mentioned_folder_ids, "folder");
		addCount(parts, params.mentioned_connector_ids, "connector");
	}
	return parts.length > 0 ? parts.join(", ") : null;
}

function addMentionTitles(parts: string[], value: unknown, label: string): void {
	if (!Array.isArray(value) || value.length === 0) return;
	const titles = value
		.map((entry) => {
			const record = asRecord(entry);
			const title = typeof record.title === "string" ? record.title : null;
			const accountName = typeof record.account_name === "string" ? record.account_name : null;
			return title ?? accountName;
		})
		.filter((title): title is string => !!title);
	if (titles.length === 0) return;
	parts.push(`${label}: ${titles.join(", ")}`);
}

function addCount(parts: string[], value: unknown, singular: string): void {
	if (!Array.isArray(value) || value.length === 0) return;
	parts.push(`${value.length} ${singular}${value.length === 1 ? "" : "s"}`);
}

function formatAction(action: string): string {
	return formatKey(action);
}

function formatKey(key: string): string {
	return key.replace(/_/g, " ");
}

function sentenceCase(value: string): string {
	return value.charAt(0).toUpperCase() + value.slice(1);
}

function asRecord(value: unknown): Record<string, unknown> {
	return value && typeof value === "object" && !Array.isArray(value)
		? (value as Record<string, unknown>)
		: {};
}

function formatValue(value: unknown): string {
	if (typeof value === "boolean") return value ? "Yes" : "No";
	if (typeof value === "string" || typeof value === "number") return String(value);
	if (Array.isArray(value)) return `${value.length} item${value.length === 1 ? "" : "s"}`;
	if (value && typeof value === "object") return "Configured";
	return String(value);
}
