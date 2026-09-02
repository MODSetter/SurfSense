import { ChevronRight, Dot } from "lucide-react";
import Link from "next/link";
import { ArtifactFormatIcon } from "@/features/artifacts/ui/artifact-format-icon";
import { ArtifactFormatLabel } from "@/features/artifacts/ui/artifact-format-label";
import { formatRelativeDate } from "@/lib/format-date";
import { cn } from "@/lib/utils";
import type { LibraryArtifact } from "../model/artifact";

const CARD_CLASS_NAME =
	"flex min-h-28 min-w-0 w-full max-w-full flex-col overflow-hidden rounded-xl border bg-muted/30 p-4 text-left transition-colors";

export function ArtifactCard({
	artifact,
	href,
}: {
	artifact: LibraryArtifact;
	href: string | null;
}) {
	const statusLabel =
		artifact.status === "running" ? "Generating…" : artifact.status === "error" ? "Failed" : null;
	const content = (
		<>
			<span className="flex min-w-0 items-start gap-3">
				<span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
					<ArtifactFormatIcon format={artifact.format} className="size-4" />
				</span>
				<span className="min-w-0 flex-1">
					<span className="line-clamp-2 text-sm font-medium leading-5 text-foreground">
						{artifact.title}
					</span>
					<span className="mt-1 flex min-w-0 items-center overflow-hidden text-xs text-muted-foreground">
						<ArtifactFormatLabel format={artifact.format} className="shrink-0" />
						{statusLabel ? (
							<>
								<Dot className="size-4 shrink-0 text-muted-foreground/60" aria-hidden="true" />
								<span
									className={cn(
										"truncate",
										artifact.status === "error" ? "text-destructive" : undefined
									)}
								>
									{statusLabel}
								</span>
							</>
						) : null}
					</span>
				</span>
			</span>
			<span className="mt-auto flex min-w-0 items-center justify-between gap-3 pt-3 text-xs text-muted-foreground">
				<span className="min-w-0 truncate">Created {formatRelativeDate(artifact.createdAt)}</span>
				{href ? <ChevronRight className="size-4 shrink-0" aria-hidden="true" /> : null}
			</span>
		</>
	);

	if (!href) {
		return (
			<div className={cn(CARD_CLASS_NAME, "cursor-default")} aria-disabled="true">
				{content}
			</div>
		);
	}

	return (
		<Link
			href={href}
			className={cn(
				CARD_CLASS_NAME,
				"hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			)}
		>
			{content}
		</Link>
	);
}
