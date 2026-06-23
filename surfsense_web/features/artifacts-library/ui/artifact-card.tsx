import { formatRelativeDate } from "@/lib/format-date";
import type { LibraryArtifact } from "../model/artifact";
import { KIND_META } from "./kind-meta";

export function ArtifactCard({
	artifact,
	onOpen,
}: {
	artifact: LibraryArtifact;
	onOpen: (artifact: LibraryArtifact) => void;
}) {
	const meta = KIND_META[artifact.kind];
	const Icon = meta.icon;

	const subtitle =
		artifact.status === "running"
			? "Generating…"
			: artifact.status === "error"
				? "Failed"
				: meta.label;

	return (
		<button
			type="button"
			onClick={() => onOpen(artifact)}
			className="group flex w-full items-start gap-3 rounded-xl border bg-card p-3 text-left transition-colors hover:border-primary/40 hover:bg-accent/50"
		>
			<span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
				<Icon className="size-4" />
			</span>
			<span className="min-w-0 flex-1">
				<span className="block truncate text-sm font-medium text-foreground">{artifact.title}</span>
				<span className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
					<span className={artifact.status === "error" ? "text-destructive" : undefined}>
						{subtitle}
					</span>
					<span aria-hidden>·</span>
					<span>{formatRelativeDate(artifact.createdAt)}</span>
				</span>
			</span>
		</button>
	);
}
