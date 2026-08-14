import { Dot } from "lucide-react";
import Link from "next/link";
import { ArtifactFormatIcon } from "@/features/artifacts/artifact-format-icon";
import { ArtifactFormatLabel } from "@/features/artifacts/artifact-format-label";
import { formatRelativeDate } from "@/lib/format-date";
import { cn } from "@/lib/utils";
import type { LibraryArtifact } from "../model/artifact";

const CARD_CLASS_NAME =
	"flex min-w-0 w-full max-w-full items-start gap-3 overflow-hidden rounded-xl border bg-muted/30 p-3 text-left transition-colors";

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
			<span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
				<ArtifactFormatIcon format={artifact.format} className="size-4" />
			</span>
			<span className="min-w-0 flex-1">
				<span className="block truncate text-sm font-medium text-foreground">{artifact.title}</span>
				<span className="mt-0.5 flex min-w-0 items-center gap-1.5 overflow-hidden text-xs text-muted-foreground">
					<span
						className={cn(
							"shrink-0",
							artifact.status === "error" ? "text-destructive" : undefined
						)}
					>
						{statusLabel ?? <ArtifactFormatLabel format={artifact.format} />}
					</span>
					<Dot className="-mx-1 size-4 shrink-0 text-muted-foreground/60" aria-hidden="true" />
					<span className="min-w-0 truncate">{formatRelativeDate(artifact.createdAt)}</span>
				</span>
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
