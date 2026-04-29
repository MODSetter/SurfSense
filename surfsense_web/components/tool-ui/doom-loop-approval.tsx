"use client";

import type { ToolCallMessagePartComponent } from "@assistant-ui/react";
import { CornerDownLeftIcon, OctagonAlert } from "lucide-react";
import { useCallback, useEffect, useMemo } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useHitlPhase } from "@/hooks/use-hitl-phase";
import type { HitlDecision, InterruptResult } from "@/lib/hitl";
import { isInterruptResult, useHitlDecision } from "@/lib/hitl";

/**
 * Specialized HITL card for ``DoomLoopMiddleware`` interrupts. The
 * backend signals these by setting ``context.permission === "doom_loop"``
 * on the ``permission_ask`` interrupt.
 *
 * The card replaces the generic "approve/reject" framing with a
 * "continue/stop" affordance that better matches the user's mental
 * model: the agent is stuck repeating itself, not asking permission
 * for a destructive action.
 */
function DoomLoopCard({
	toolName,
	args,
	interruptData,
	onDecision,
}: {
	toolName: string;
	args: Record<string, unknown>;
	interruptData: InterruptResult;
	onDecision: (decision: HitlDecision) => void;
}) {
	const { phase, setProcessing, setRejected } = useHitlPhase(interruptData);

	const context = (interruptData.context ?? {}) as Record<string, unknown>;
	const threshold = typeof context.threshold === "number" ? context.threshold : 3;
	const stuckTool = (typeof context.tool === "string" && context.tool) || toolName;
	const recentSignatures = Array.isArray(context.recent_signatures)
		? (context.recent_signatures as string[])
		: [];
	const displayName = stuckTool.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

	const argPreview = useMemo(() => {
		if (!args || Object.keys(args).length === 0) return null;
		try {
			const json = JSON.stringify(args, null, 2);
			return json.length > 600 ? `${json.slice(0, 600)}…` : json;
		} catch {
			return null;
		}
	}, [args]);

	const handleContinue = useCallback(() => {
		if (phase !== "pending") return;
		setProcessing();
		onDecision({ type: "approve" });
	}, [phase, setProcessing, onDecision]);

	const handleStop = useCallback(() => {
		if (phase !== "pending") return;
		setRejected();
		onDecision({ type: "reject", message: "Doom loop: user requested stop." });
	}, [phase, setRejected, onDecision]);

	useEffect(() => {
		const handler = (e: KeyboardEvent) => {
			if (phase !== "pending") return;
			if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
				e.preventDefault();
				handleStop();
			}
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [phase, handleStop]);

	const isResolved = phase === "complete" || phase === "rejected";

	return (
		<Alert variant={phase === "rejected" ? "default" : "destructive"} className="my-4 max-w-lg">
			<OctagonAlert className="size-4" />
			<AlertTitle className="flex items-center gap-2">
				<span>
					{phase === "rejected"
						? "Stopped"
						: phase === "processing"
							? "Continuing…"
							: phase === "complete"
								? "Continued"
								: "I might be stuck"}
				</span>
				{!isResolved && (
					<Badge variant="outline" className="font-mono text-[10px]">
						doom-loop
					</Badge>
				)}
			</AlertTitle>
			<AlertDescription className="flex flex-col gap-3">
				{phase === "processing" ? (
					<TextShimmerLoader text="Resuming…" size="sm" />
				) : phase === "rejected" ? (
					<p className="text-xs">
						I stopped retrying <span className="font-medium">{displayName}</span> as you asked.
					</p>
				) : phase === "complete" ? (
					<p className="text-xs">
						Continuing to call <span className="font-medium">{displayName}</span> as you asked.
					</p>
				) : (
					<p className="text-xs">
						I called <span className="font-medium">{displayName}</span> {threshold} times in a row
						with similar arguments. Should I keep going or stop and rethink?
					</p>
				)}

				{argPreview && phase === "pending" && (
					<>
						<Separator />
						<div className="flex flex-col gap-1">
							<p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
								Last arguments
							</p>
							<pre className="max-h-32 overflow-auto rounded-md bg-muted/50 p-2 text-[11px] text-foreground/80">
								{argPreview}
							</pre>
						</div>
					</>
				)}

				{recentSignatures.length > 0 && phase === "pending" && (
					<details className="text-[11px] text-muted-foreground">
						<summary className="cursor-pointer select-none">
							Show repeated signatures ({recentSignatures.length})
						</summary>
						<ul className="mt-1 ml-4 list-disc">
							{recentSignatures.map((sig) => (
								<li key={sig} className="font-mono break-all">
									{sig}
								</li>
							))}
						</ul>
					</details>
				)}

				{phase === "pending" && (
					<div className="flex items-center gap-2">
						<Button size="sm" variant="outline" className="rounded-lg gap-1.5" onClick={handleStop}>
							Stop and rethink
							<CornerDownLeftIcon className="size-3 opacity-60" />
						</Button>
						<Button size="sm" variant="ghost" onClick={handleContinue}>
							Continue anyway
						</Button>
					</div>
				)}
			</AlertDescription>
		</Alert>
	);
}

export const DoomLoopApprovalToolUI: ToolCallMessagePartComponent = ({
	toolName,
	args,
	result,
}) => {
	const { dispatch } = useHitlDecision();

	if (!result || !isInterruptResult(result)) return null;

	return (
		<DoomLoopCard
			toolName={toolName}
			args={args as Record<string, unknown>}
			interruptData={result}
			onDecision={(decision) => dispatch([decision])}
		/>
	);
};

export function isDoomLoopInterrupt(result: unknown): boolean {
	if (!isInterruptResult(result)) return false;
	const ctx = (result.context ?? {}) as Record<string, unknown>;
	return ctx.permission === "doom_loop";
}
