import { MessageSquareText } from "lucide-react";
import Link from "next/link";
import { formatRelativeDate } from "@/lib/format-date";
import type { LibraryArtifact } from "../model/artifact";
import { KIND_META } from "./kind-meta";

export function ArtifactCard({
	artifact,
	searchSpaceId,
	onOpen,
}: {
	artifact: LibraryArtifact;
	searchSpaceId: number;
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
		<div className="group relative flex items-start gap-3 rounded-xl border bg-card p-3 transition-colors hover:border-primary/40 hover:bg-accent/50">
			{/* Stretched overlay makes the whole card open the viewer; sibling controls sit above it via z-10. */}
			<button
				type="button"
				onClick={() => onOpen(artifact)}
				className="absolute inset-0 rounded-xl"
			>
				<span className="sr-only">Open {artifact.title}</span>
			</button>

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

			{artifact.sourceThreadId ? (
				<Link
					href={`/dashboard/${searchSpaceId}/new-chat/${artifact.sourceThreadId}`}
					title="Open source chat"
					className="relative z-10 flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-0 transition-opacity hover:bg-muted hover:text-foreground focus-visible:opacity-100 group-hover:opacity-100"
				>
					<MessageSquareText className="size-4" />
					<span className="sr-only">Open source chat</span>
				</Link>
			) : null}
		</div>
	);
}
