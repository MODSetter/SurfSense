"use client";

import {
	AlertCircleIcon,
	CheckCircle2Icon,
	ChevronRightIcon,
	Loader2Icon,
	TerminalIcon,
	XCircleIcon,
} from "lucide-react";
import { useState } from "react";
import { z } from "zod";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { TimelineToolProps } from "@/features/chat-messages/timeline/tool-registry/types";
import { cn } from "@/lib/utils";

const ExecuteArgsSchema = z.object({
	code_or_command: z.string(),
	language: z.enum(["python", "bash"]).optional(),
	description: z.string().nullish(),
});

const ExecuteResultSchema = z.object({
	result: z.string().nullish(),
	output: z.string().nullish(),
	error: z.string().nullish(),
});
type ExecuteArgs = z.infer<typeof ExecuteArgsSchema>;
type ExecuteResult = z.infer<typeof ExecuteResultSchema>;

const EXIT_RE = /\n?\[Command exited with code (-?\d+)\]/;
const FULL_OUTPUT_RE = /\n?\[Full output: (.+)\]\s*$/m;

interface ParsedOutput {
	exitCode: number | null;
	output: string;
	fullOutputPath: string | null;
	truncated: boolean;
}

function parseResult(result: unknown): ParsedOutput {
	const structured = ExecuteResultSchema.safeParse(result);
	const raw =
		typeof result === "string"
			? result
			: structured.success
				? structured.data.error || structured.data.result || structured.data.output || ""
				: "";
	const exitMatch = raw.match(EXIT_RE);
	const fullOutputMatch = raw.match(FULL_OUTPUT_RE);
	return {
		exitCode: exitMatch ? Number(exitMatch[1]) : null,
		output: raw.replace(EXIT_RE, "").replace(FULL_OUTPUT_RE, "").trim(),
		fullOutputPath: fullOutputMatch?.[1]?.trim() || null,
		truncated: raw.includes("… [output truncated]"),
	};
}

function truncate(value: string, max = 80) {
	return value.length <= max ? value : `${value.slice(0, max)}…`;
}

export function SandboxExecuteToolUI({ args, result, status }: TimelineToolProps) {
	const parsedArgs = ExecuteArgsSchema.safeParse(args);
	const command = parsedArgs.success ? parsedArgs.data.code_or_command : "…";
	const language = parsedArgs.success ? parsedArgs.data.language : undefined;
	const [open, setOpen] = useState(false);

	if (status === "pending" || status === "running") {
		return (
			<div className="my-4 flex max-w-lg items-center gap-3 rounded-xl border bg-card px-4 py-3">
				<Loader2Icon className="size-4 shrink-0 animate-spin text-muted-foreground" />
				<code className="truncate font-mono text-sm text-muted-foreground">
					{truncate(command)}
				</code>
			</div>
		);
	}

	if (status === "cancelled") {
		return (
			<div className="my-4 max-w-lg rounded-xl border p-4 text-muted-foreground">
				<p className="flex items-center gap-2 font-mono text-sm line-through">
					<TerminalIcon className="size-4" /> {truncate(command)}
				</p>
			</div>
		);
	}

	const parsed = parseResult(result);
	const failed = status === "error" || (parsed.exitCode !== null && parsed.exitCode !== 0);
	const hasDetails =
		command.length > 80 ||
		command.includes("\n") ||
		parsed.output.length > 0 ||
		parsed.fullOutputPath !== null;

	return (
		<div className="my-4 max-w-lg">
			<Collapsible open={open} onOpenChange={setOpen}>
				<CollapsibleTrigger
					disabled={!hasDetails}
					className={cn(
						"flex w-full items-center gap-2 rounded-xl border bg-card px-4 py-2.5 text-left transition-colors hover:bg-accent",
						open && "rounded-b-none border-b-0",
						failed && "border-destructive/20"
					)}
				>
					<ChevronRightIcon
						className={cn(
							"size-3.5 shrink-0 text-muted-foreground transition-transform",
							open && "rotate-90",
							!hasDetails && "invisible"
						)}
					/>
					<TerminalIcon className="size-3.5 shrink-0 text-muted-foreground" />
					<code className="min-w-0 flex-1 truncate font-mono text-sm">{truncate(command)}</code>
					{language && <Badge variant="outline">{language}</Badge>}
					{parsed.exitCode !== null && (
						<Badge variant={failed ? "destructive" : "secondary"} className="gap-1">
							{failed ? (
								<XCircleIcon className="size-3" />
							) : (
								<CheckCircle2Icon className="size-3" />
							)}
							{parsed.exitCode}
						</Badge>
					)}
					{status === "error" && parsed.exitCode === null && (
						<AlertCircleIcon className="size-4 text-destructive" />
					)}
				</CollapsibleTrigger>
				<CollapsibleContent>
					<div
						className={cn(
							"space-y-3 rounded-b-xl border border-t-0 bg-zinc-950 px-4 py-3",
							failed && "border-destructive/20"
						)}
					>
						{(command.length > 80 || command.includes("\n")) && (
							<pre className="max-h-60 overflow-auto whitespace-pre-wrap break-all font-mono text-xs text-emerald-400">
								{command}
							</pre>
						)}
						{parsed.output && (
							<pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all font-mono text-xs text-zinc-300">
								{parsed.output}
							</pre>
						)}
						{parsed.fullOutputPath && (
							<p className="font-mono text-[11px] text-zinc-500">
								Full output: {parsed.fullOutputPath}
							</p>
						)}
						{parsed.truncated && (
							<p className="text-[11px] text-zinc-500">Output was truncated in this view.</p>
						)}
					</div>
				</CollapsibleContent>
			</Collapsible>
		</div>
	);
}

export { type ExecuteArgs, ExecuteArgsSchema, type ExecuteResult, ExecuteResultSchema };
