import { CheckIcon } from "@/components/ui/icons";
import type { AgentTranscript as AgentTranscriptModel } from "@/lib/connectors-marketing/types";

/**
 * The hero's terminal illustration: a static "here is what comes back"
 * artifact — the prompt, the tool call it drives, and the structured rows it
 * returns. A server component with no animation, matching every other page
 * built on `app/(home)/home.css`: the homepage and pricing hero don't type
 * text in or stagger their content into view, and this shouldn't either.
 */
export function AgentTranscript({ transcript }: { transcript: AgentTranscriptModel }) {
	return (
		<div className="ss-home-terminal ss-home-mono text-sm">
			<div className="ss-home-terminal-bar" aria-hidden="true">
				<span className="flex gap-1.5">
					<span className="ss-home-terminal-dot" />
					<span className="ss-home-terminal-dot" />
					<span className="ss-home-terminal-dot" />
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

				<pre className="ss-home-code">
					<code className="whitespace-pre-wrap wrap-break-word">{transcript.toolCall}</code>
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
								<span className="ss-home-tag shrink-0" data-tone="accent">
									{row.tag}
								</span>
							) : null}
						</li>
					))}
				</ul>

				<p className="flex items-center gap-1.5 text-xs text-muted-foreground">
					<CheckIcon aria-hidden="true" className="size-3.5 text-(--home-accent)" />
					{transcript.resultSummary}
				</p>
			</div>
		</div>
	);
}
