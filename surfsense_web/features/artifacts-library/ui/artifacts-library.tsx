"use client";

import { useSetAtom } from "jotai";
import { Boxes, RefreshCw, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { openReportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { MobileReportPanel } from "@/components/report-panel/report-panel";
import { Button } from "@/components/ui/button";
import { useLibraryArtifacts } from "../hooks/use-library-artifacts";
import type { LibraryArtifact, LibraryArtifactKind } from "../model/artifact";
import { ArtifactCard } from "./artifact-card";
import { KIND_META, KIND_ORDER } from "./kind-meta";
import { MediaViewerDialog } from "./media-viewer-dialog";

const SKELETON_KEYS = ["s1", "s2", "s3", "s4", "s5", "s6"];

function LoadingState() {
	return (
		<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
			{SKELETON_KEYS.map((key) => (
				<div key={key} className="h-[68px] animate-pulse rounded-xl border bg-muted/40" />
			))}
		</div>
	);
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
	return (
		<div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-20 text-center">
			<span className="flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
				<TriangleAlert className="size-6" />
			</span>
			<div>
				<p className="font-medium text-foreground">Couldn't load artifacts</p>
				<p className="mt-1 text-sm text-muted-foreground">
					Something went wrong fetching this search space's deliverables.
				</p>
			</div>
			<Button variant="outline" size="sm" onClick={onRetry}>
				<RefreshCw className="size-4" />
				Retry
			</Button>
		</div>
	);
}

function EmptyState() {
	return (
		<div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-20 text-center">
			<span className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
				<Boxes className="size-6" />
			</span>
			<div>
				<p className="font-medium text-foreground">No artifacts yet</p>
				<p className="mt-1 text-sm text-muted-foreground">
					Reports, resumes, podcasts, presentations, and images you generate appear here.
				</p>
			</div>
		</div>
	);
}

export function ArtifactsLibrary({ workspaceId }: { workspaceId: number }) {
	const searchSpaceId = workspaceId;
	const { artifacts, loading, error, refresh } = useLibraryArtifacts(searchSpaceId);
	const openReportPanel = useSetAtom(openReportPanelAtom);
	const [selectedMedia, setSelectedMedia] = useState<LibraryArtifact | null>(null);

	const grouped = useMemo(() => {
		const map = new Map<LibraryArtifactKind, LibraryArtifact[]>();
		for (const artifact of artifacts) {
			const bucket = map.get(artifact.kind);
			if (bucket) bucket.push(artifact);
			else map.set(artifact.kind, [artifact]);
		}
		return map;
	}, [artifacts]);

	const handleOpen = (artifact: LibraryArtifact) => {
		// Reports/resumes reuse the shared report panel; the rest open in the dialog.
		if (artifact.kind === "report" || artifact.kind === "resume") {
			openReportPanel({
				reportId: artifact.entityId,
				title: artifact.title,
				contentType: artifact.contentType,
			});
			return;
		}
		setSelectedMedia(artifact);
	};

	return (
		<div className="mx-auto w-full max-w-5xl px-6 py-8">
			<header className="mb-6 flex items-center justify-between gap-4">
				<div>
					<h1 className="text-xl font-semibold text-foreground">Artifacts</h1>
					<p className="mt-1 text-sm text-muted-foreground">
						Every deliverable created across this search space.
					</p>
				</div>
				{!loading && artifacts.length > 0 ? (
					<span className="shrink-0 text-sm text-muted-foreground">{artifacts.length} total</span>
				) : null}
			</header>

			{loading ? (
				<LoadingState />
			) : error ? (
				<ErrorState onRetry={() => refresh()} />
			) : artifacts.length === 0 ? (
				<EmptyState />
			) : (
				<div className="space-y-8">
					{KIND_ORDER.map((kind) => {
						const items = grouped.get(kind);
						if (!items || items.length === 0) return null;
						return (
							<section key={kind}>
								<h2 className="mb-3 text-sm font-medium text-muted-foreground">
									{KIND_META[kind].group}
									<span className="ml-1.5 text-muted-foreground/60">{items.length}</span>
								</h2>
								<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
									{items.map((artifact) => (
										<ArtifactCard
											key={artifact.key}
											artifact={artifact}
											searchSpaceId={searchSpaceId}
											onOpen={handleOpen}
										/>
									))}
								</div>
							</section>
						);
					})}
				</div>
			)}

			<MediaViewerDialog artifact={selectedMedia} onClose={() => setSelectedMedia(null)} />
			<MobileReportPanel />
		</div>
	);
}
