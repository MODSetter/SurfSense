"use client";

import { Check } from "lucide-react";
import { motion, useReducedMotion, type Variants } from "motion/react";
import { useEffect, useState } from "react";
import type { AgentTranscript as AgentTranscriptModel } from "@/lib/connectors-marketing/types";
import { cn } from "@/lib/utils";

// Custom ease-out: fast start, gentle settle. Never ease-in for entrances.
const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];

const container: Variants = {
	hidden: {},
	show: { transition: { staggerChildren: 0.06, delayChildren: 0.08 } },
};

// Enter from a small offset + fade. Never from scale(0). Under 300ms per item.
const item: Variants = {
	hidden: { opacity: 0, y: 8 },
	show: { opacity: 1, y: 0, transition: { duration: 0.24, ease: EASE_OUT } },
};

/** Reveal a string one character at a time. Returns the full string instantly when disabled. */
function useTypedText(text: string, enabled: boolean, speedMs = 16) {
	const [count, setCount] = useState(enabled ? 0 : text.length);

	useEffect(() => {
		if (!enabled) {
			setCount(text.length);
			return;
		}
		setCount(0);
		let i = 0;
		const id = window.setInterval(() => {
			i += 1;
			setCount(i);
			if (i >= text.length) window.clearInterval(id);
		}, speedMs);
		return () => window.clearInterval(id);
	}, [text, enabled, speedMs]);

	return { shown: text.slice(0, count), done: count >= text.length };
}

export function AgentTranscript({
	transcript,
	className,
}: {
	transcript: AgentTranscriptModel;
	className?: string;
}) {
	const reduce = useReducedMotion() ?? false;
	const animate = !reduce;
	const { shown: typedPrompt, done: promptDone } = useTypedText(transcript.prompt, animate);
	const revealed = promptDone;

	return (
		<div
			className={cn(
				"w-full overflow-hidden rounded-xl border bg-card shadow-sm",
				"font-mono text-sm",
				className
			)}
		>
			{/* Window chrome */}
			<div className="flex items-center gap-2 border-b bg-muted/40 px-4 py-2.5">
				<span className="flex gap-1.5" aria-hidden>
					<span className="size-2.5 rounded-full bg-muted-foreground/25" />
					<span className="size-2.5 rounded-full bg-muted-foreground/25" />
					<span className="size-2.5 rounded-full bg-muted-foreground/25" />
				</span>
				<span className="ml-1 text-xs text-muted-foreground">agent · surfsense</span>
			</div>

			<div className="space-y-4 p-4 sm:p-5">
				{/* Prompt line (typed) */}
				<p className="flex flex-wrap items-baseline gap-x-2 leading-relaxed">
					<span className="select-none text-muted-foreground">$</span>
					<span className="text-foreground">
						{typedPrompt}
						{animate && !promptDone && (
							<span className="ml-0.5 inline-block h-3.5 w-1.5 translate-y-0.5 animate-pulse bg-foreground/70" />
						)}
					</span>
				</p>

				{/* Tool call + results reveal only after the prompt is typed */}
				<motion.div
					className="space-y-4"
					variants={container}
					initial={animate ? "hidden" : false}
					animate={revealed ? "show" : "hidden"}
				>
					<motion.pre
						variants={item}
						className="overflow-x-auto rounded-lg border bg-muted/50 px-3 py-2.5 text-xs leading-relaxed text-muted-foreground"
					>
						<code className="whitespace-pre-wrap wrap-break-word text-foreground/80">
							{transcript.toolCall}
						</code>
					</motion.pre>

					<ul className="space-y-2">
						{transcript.rows.map((row) => (
							<motion.li
								key={row.primary}
								variants={item}
								className="flex items-start justify-between gap-3 rounded-lg border bg-background px-3 py-2.5"
							>
								<span className="min-w-0">
									<span className="block truncate text-[13px] font-medium text-foreground">
										{row.primary}
									</span>
									<span className="mt-0.5 block truncate text-xs text-muted-foreground">
										{row.secondary}
									</span>
								</span>
								{row.tag && (
									<span className="shrink-0 rounded-full border border-brand/30 bg-brand/10 px-2 py-0.5 text-[10px] font-medium tracking-wide text-brand uppercase">
										{row.tag}
									</span>
								)}
							</motion.li>
						))}
					</ul>

					<motion.p
						variants={item}
						className="flex items-center gap-1.5 text-xs text-muted-foreground"
					>
						<Check className="size-3.5 text-brand" aria-hidden />
						{transcript.resultSummary}
					</motion.p>
				</motion.div>
			</div>
		</div>
	);
}
