"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	AlertCircleIcon,
	CheckCircle2Icon,
	ChevronRightIcon,
	DownloadIcon,
	FileIcon,
	Loader2Icon,
	TerminalIcon,
	XCircleIcon,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { z } from "zod";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { getBearerToken } from "@/lib/auth-utils";
import { BACKEND_URL } from "@/lib/env-config";
import { cn } from "@/lib/utils";

// ============================================================================
// Zod Schemas
// ============================================================================

const ExecuteArgsSchema = z.object({
	command: z.string(),
	timeout: z.number().nullish(),
});

const ExecuteResultSchema = z.object({
	result: z.string().nullish(),
	exit_code: z.number().nullish(),
	output: z.string().nullish(),
	error: z.string().nullish(),
	status: z.string().nullish(),
	thread_id: z.string().nullish(),
});

// ============================================================================
// Types
// ============================================================================

type ExecuteArgs = z.infer<typeof ExecuteArgsSchema>;
type ExecuteResult = z.infer<typeof ExecuteResultSchema>;

interface SandboxFile {
	path: string;
	name: string;
}

interface ParsedOutput {
	exitCode: number | null;
	output: string;
	displayOutput: string;
	truncated: boolean;
	isError: boolean;
	files: SandboxFile[];
}

// ============================================================================
// Helpers
// ============================================================================

const SANDBOX_FILE_RE = /^SANDBOX_FILE:\s*(.+)$/gm;

function extractSandboxFiles(text: string): SandboxFile[] {
	const files: SandboxFile[] = [];
	let match: RegExpExecArray | null;
	while ((match = SANDBOX_FILE_RE.exec(text)) !== null) {
		const filePath = match[1].trim();
		if (filePath) {
			const name = filePath.includes("/") ? filePath.split("/").pop() || filePath : filePath;
			files.push({ path: filePath, name });
		}
	}
	SANDBOX_FILE_RE.lastIndex = 0;
	return files;
}

function stripSandboxFileLines(text: string): string {
	return text
		.replace(/^SANDBOX_FILE:\s*.+$/gm, "")
		.replace(/\n{3,}/g, "\n\n")
		.trim();
}

function parseExecuteResult(result: ExecuteResult): ParsedOutput {
	const raw = result.result || result.output || "";

	if (result.error) {
		return {
			exitCode: null,
			output: result.error,
			displayOutput: result.error,
			truncated: false,
			isError: true,
			files: [],
		};
	}

	if (result.exit_code !== undefined && result.exit_code !== null) {
		const files = extractSandboxFiles(raw);
		const displayOutput = stripSandboxFileLines(raw);
		return {
			exitCode: result.exit_code,
			output: raw,
			displayOutput,
			truncated: raw.includes("[Output was truncated"),
			isError: result.exit_code !== 0,
			files,
		};
	}

	const exitMatch = raw.match(/^Exit code:\s*(\d+)/);
	if (exitMatch) {
		const exitCode = parseInt(exitMatch[1], 10);
		const outputMatch = raw.match(/\nOutput:\n([\s\S]*)/);
		const output = outputMatch ? outputMatch[1] : "";
		const files = extractSandboxFiles(output);
		const displayOutput = stripSandboxFileLines(output);
		return {
			exitCode,
			output,
			displayOutput,
			truncated: raw.includes("[Output was truncated"),
			isError: exitCode !== 0,
			files,
		};
	}

	if (raw.startsWith("Error:")) {
		return {
			exitCode: null,
			output: raw,
			displayOutput: raw,
			truncated: false,
			isError: true,
			files: [],
		};
	}

	const files = extractSandboxFiles(raw);
	const displayOutput = stripSandboxFileLines(raw);
	return { exitCode: null, output: raw, displayOutput, truncated: false, isError: false, files };
}

function truncateCommand(command: string, maxLen = 80): string {
	if (command.length <= maxLen) return command;
	return command.slice(0, maxLen) + "…";
}

// ============================================================================
// Download helper
// ============================================================================

async function downloadSandboxFile(threadId: string, filePath: string, fileName: string) {
	const token = getBearerToken();
	const url = `${BACKEND_URL}/api/v1/threads/${threadId}/sandbox/download?path=${encodeURIComponent(filePath)}`;
	const res = await fetch(url, {
		headers: { Authorization: `Bearer ${token || ""}` },
	});
	if (!res.ok) {
		throw new Error(`Download failed: ${res.statusText}`);
	}
	const blob = await res.blob();
	const blobUrl = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = blobUrl;
	a.download = fileName;
	document.body.appendChild(a);
	a.click();
	a.remove();
	URL.revokeObjectURL(blobUrl);
}

// ============================================================================
// Sub-Components
// ============================================================================

function ExecuteLoading({ command }: { command: string }) {
	return (
		<div className="my-4 flex max-w-lg items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
			<Loader2Icon className="size-4 shrink-0 animate-spin text-muted-foreground" />
			<code className="truncate text-sm text-muted-foreground font-mono">
				{truncateCommand(command)}
			</code>
		</div>
	);
}

function ExecuteErrorState({ command, error }: { command: string; error: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-xl border border-destructive/20 bg-destructive/5 p-4">
			<div className="flex items-center gap-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
					<AlertCircleIcon className="size-4 text-destructive" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-destructive">Execution failed</p>
					<code className="mt-0.5 block truncate text-xs text-muted-foreground font-mono">
						$ {command}
					</code>
					<p className="mt-1 text-xs text-muted-foreground">{error}</p>
				</div>
			</div>
		</div>
	);
}

function ExecuteCancelledState({ command }: { command: string }) {
	return (
		<div className="my-4 max-w-lg rounded-xl border border-muted p-4 text-muted-foreground">
			<p className="flex items-center gap-2 font-mono text-sm">
				<TerminalIcon className="size-4" />
				<span className="line-through truncate">$ {command}</span>
			</p>
		</div>
	);
}

function SandboxFileDownload({ file, threadId }: { file: SandboxFile; threadId: string }) {
	const [downloading, setDownloading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleDownload = useCallback(async () => {
		setDownloading(true);
		setError(null);
		try {
			await downloadSandboxFile(threadId, file.path, file.name);
		} catch (e) {
			setError(e instanceof Error ? e.message : "Download failed");
		} finally {
			setDownloading(false);
		}
	}, [threadId, file.path, file.name]);

	return (
		<Button
			variant="ghost"
			size="sm"
			className="h-8 gap-2 rounded-lg bg-zinc-800/60 hover:bg-zinc-700/60 text-zinc-200 text-xs font-mono px-3"
			onClick={handleDownload}
			disabled={downloading}
		>
			{downloading ? (
				<Loader2Icon className="size-3.5 animate-spin" />
			) : (
				<DownloadIcon className="size-3.5" />
			)}
			<FileIcon className="size-3 text-zinc-400" />
			<span className="truncate max-w-[200px]">{file.name}</span>
			{error && <span className="text-destructive text-[10px] ml-1">{error}</span>}
		</Button>
	);
}

function ExecuteCompleted({
	command,
	parsed,
	threadId,
}: {
	command: string;
	parsed: ParsedOutput;
	threadId: string | null;
}) {
	const [open, setOpen] = useState(false);
	const isLongCommand = command.length > 80 || command.includes("\n");
	const hasTextContent = parsed.displayOutput.trim().length > 0 || isLongCommand;
	const hasFiles = parsed.files.length > 0 && !!threadId;
	const hasContent = hasTextContent || hasFiles;

	const exitBadge = useMemo(() => {
		if (parsed.exitCode === null) return null;
		const success = parsed.exitCode === 0;
		return (
			<Badge
				variant={success ? "secondary" : "destructive"}
				className={cn(
					"ml-auto gap-1 text-[10px] px-1.5 py-0",
					success &&
						"bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
				)}
			>
				{success ? <CheckCircle2Icon className="size-3" /> : <XCircleIcon className="size-3" />}
				{parsed.exitCode}
			</Badge>
		);
	}, [parsed.exitCode]);

	return (
		<div className="my-4 max-w-lg">
			<Collapsible open={open} onOpenChange={setOpen}>
				<CollapsibleTrigger
					className={cn(
						"flex w-full items-center gap-2 rounded-xl border bg-card px-4 py-2.5 text-left transition-colors hover:bg-accent/50",
						open && "rounded-b-none border-b-0",
						parsed.isError && "border-destructive/20"
					)}
					disabled={!hasContent}
				>
					<ChevronRightIcon
						className={cn(
							"size-3.5 shrink-0 text-muted-foreground transition-transform duration-200",
							open && "rotate-90",
							!hasContent && "invisible"
						)}
					/>
					<TerminalIcon className="size-3.5 shrink-0 text-muted-foreground" />
					<code className="min-w-0 flex-1 truncate text-sm font-mono">
						{truncateCommand(command)}
					</code>
					{hasFiles && !open && (
						<Badge
							variant="outline"
							className="gap-1 text-[10px] px-1.5 py-0 border-blue-500/30 text-blue-500"
						>
							<FileIcon className="size-2.5" />
							{parsed.files.length}
						</Badge>
					)}
					{exitBadge}
				</CollapsibleTrigger>

				<CollapsibleContent>
					<div
						className={cn(
							"rounded-b-xl border border-t-0 bg-zinc-950 dark:bg-zinc-900/60 px-4 py-3 space-y-3",
							parsed.isError && "border-destructive/20"
						)}
					>
						{isLongCommand && (
							<div>
								<p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-zinc-500">
									Command
								</p>
								<pre className="max-h-60 overflow-auto whitespace-pre-wrap break-all rounded-md bg-zinc-900/80 dark:bg-zinc-800/40 px-3 py-2 text-xs font-mono text-emerald-400 leading-relaxed">
									{command}
								</pre>
							</div>
						)}
						{parsed.displayOutput.trim().length > 0 && (
							<div>
								{(isLongCommand || hasFiles) && (
									<p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-zinc-500">
										Output
									</p>
								)}
								<pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all text-xs font-mono text-zinc-300 leading-relaxed">
									{parsed.displayOutput}
								</pre>
							</div>
						)}
						{parsed.truncated && (
							<p className="text-[10px] text-zinc-500 italic">
								Output was truncated due to size limits
							</p>
						)}
						{hasFiles && threadId && (
							<div>
								<p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-zinc-500">
									Files
								</p>
								<div className="flex flex-wrap gap-2">
									{parsed.files.map((file) => (
										<SandboxFileDownload key={file.path} file={file} threadId={threadId} />
									))}
								</div>
							</div>
						)}
					</div>
				</CollapsibleContent>
			</Collapsible>
		</div>
	);
}

// ============================================================================
// Tool UI
// ============================================================================

export const SandboxExecuteToolUI = makeAssistantToolUI<ExecuteArgs, ExecuteResult>({
	toolName: "execute",
	render: function SandboxExecuteUI({ args, result, status }) {
		const command = args.command || "…";

		if (status.type === "running" || status.type === "requires-action") {
			return <ExecuteLoading command={command} />;
		}

		if (status.type === "incomplete") {
			if (status.reason === "cancelled") {
				return <ExecuteCancelledState command={command} />;
			}
			if (status.reason === "error") {
				return (
					<ExecuteErrorState
						command={command}
						error={typeof status.error === "string" ? status.error : "An error occurred"}
					/>
				);
			}
		}

		if (!result) {
			return <ExecuteLoading command={command} />;
		}

		if (result.error && !result.result && !result.output) {
			return <ExecuteErrorState command={command} error={result.error} />;
		}

		const parsed = parseExecuteResult(result);
		const threadId = result.thread_id || null;
		return <ExecuteCompleted command={command} parsed={parsed} threadId={threadId} />;
	},
});

export { ExecuteArgsSchema, ExecuteResultSchema, type ExecuteArgs, type ExecuteResult };
