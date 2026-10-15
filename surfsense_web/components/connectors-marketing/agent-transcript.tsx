import { CheckIcon } from "@/components/ui/icons";
import type { AgentTranscript as AgentTranscriptModel } from "@/lib/connectors-marketing/types";

/**
 * The hero's terminal illustration: a static "here is what comes back"
 * artifact — the prompt, the tool call it drives, and the structured rows it
 * returns. A server component with no animation, matching the rest of the
 * site: the homepage and pricing hero don't type text in or stagger their
 * content into view, and this shouldn't either.
 */
export function AgentTranscript({ transcript }: { transcript: AgentTranscriptModel }) {
	return (
		<div className="border border-border bg-card font-mono text-sm">
			<div
				className="flex items-center gap-2 border-b border-border px-4 py-2.5"
				aria-hidden="true"
			>
				<span className="flex gap-1.5">
					<span className="size-2 rounded-full bg-muted-foreground opacity-35" />
					<span className="size-2 rounded-full bg-muted-foreground opacity-35" />
					<span className="size-2 rounded-full bg-muted-foreground opacity-35" />
				</span>
				<span className="ml-1 text-xs text-muted-foreground">agent · surfsense</span>
			</div>

			<div className="space-y-4 p-4 sm:p-5">
				<p className="flex flex-wrap items-baseline gap-x-2 leading-relaxed">
					<span aria-hidden="true" className="select-none text-muted-foreground">
						$
					</span>
					<span>{transcript.prompt}</span>
				</p>

				<pre className="overflow-x-auto border border-border bg-muted px-4 py-3.5 font-mono text-xs leading-relaxed text-muted-foreground">
					<code className="whitespace-pre-wrap wrap-break-word text-foreground">
						{transcript.toolCall}
					</code>
				</pre>

				<ul className="space-y-2">
					{transcript.rows.map((row) => (
						<li
							key={row.primary}
							className="flex items-start justify-between gap-3 border border-border bg-background px-3 py-2.5"
						>
							<span className="min-w-0">
								<span className="block truncate text-[13px] font-medium">{row.primary}</span>
								<span className="mt-0.5 block truncate text-xs text-muted-foreground">
									{row.secondary}
								</span>
							</span>
							{row.tag ? (
								<span
									className="inline-flex shrink-0 items-center rounded-full border border-border px-2 py-px text-[10px] font-semibold tracking-wide whitespace-nowrap text-muted-foreground uppercase data-[tone=accent]:border-primary/40 data-[tone=accent]:text-primary"
									data-tone="accent"
								>
									{row.tag}
								</span>
							) : null}
						</li>
					))}
				</ul>

				<p className="flex items-center gap-1.5 text-xs text-muted-foreground">
					<CheckIcon aria-hidden="true" className="size-3.5 text-primary" />
					{transcript.resultSummary}
				</p>
			</div>
		</div>
	);
}
