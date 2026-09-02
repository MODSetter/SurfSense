"use client";

import { RefreshCw, Shapes, TriangleAlert } from "lucide-react";
import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { artifactChatHref } from "@/features/chat-artifacts/lib/artifact-deep-link";
import { useLibraryArtifacts } from "../hooks/use-library-artifacts";
import { useLibraryDeliverableJobs } from "../hooks/use-library-deliverable-jobs";
import { useLibraryPodcastRuns } from "../hooks/use-library-podcast-runs";
import { useLibraryVideoRuns } from "../hooks/use-library-video-runs";
import { ArtifactCard } from "./artifact-card";

const SKELETON_KEYS = ["s1", "s2", "s3", "s4", "s5", "s6"];

function LoadingState() {
	return (
		<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
			{SKELETON_KEYS.map((key) => (
				<div key={key} className="h-28 animate-pulse rounded-xl border bg-muted/40" />
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
					Something went wrong fetching this workspace's deliverables.
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
		<div className="rounded-lg border border-dashed border-border/60 bg-muted/20 px-6 py-12 text-center">
			<div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
				<Shapes className="h-6 w-6" aria-hidden />
			</div>
			<h3 className="mt-4 text-base font-semibold text-foreground">No artifacts yet</h3>
			<p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
				Artifacts collect the reports, resumes, podcasts, presentations, and images SurfSense
				creates for this workspace. Generated deliverables from your chats will appear here.
			</p>
		</div>
	);
}

export function ArtifactsLibrary({ workspaceId }: { workspaceId: number }) {
	const { artifacts, loading, error, refresh } = useLibraryArtifacts(workspaceId);
	const liveVideoRuns = useLibraryVideoRuns(workspaceId);
	const livePodcastRuns = useLibraryPodcastRuns(workspaceId);
	const liveDeliverableJobs = useLibraryDeliverableJobs(workspaceId);

	// Delivered media comes from the Artifact API (react-query); in-flight and
	// failed runs arrive by push from Zero. Merge newest-first.
	const merged = useMemo(
		() =>
			[...artifacts, ...liveVideoRuns, ...livePodcastRuns, ...liveDeliverableJobs].sort(
				(a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
			),
		[artifacts, liveVideoRuns, livePodcastRuns, liveDeliverableJobs]
	);

	return (
		<div className="w-full min-w-0 max-w-full space-y-6 overflow-x-hidden">
			<header className="flex items-center justify-between gap-4 flex-wrap">
				<div className="flex items-baseline gap-3">
					<h1 className="text-xl md:text-2xl font-semibold text-foreground">Artifacts</h1>
					{!loading && merged.length > 0 ? (
						<p className="whitespace-nowrap text-sm text-muted-foreground">
							{merged.length} {merged.length === 1 ? "artifact" : "artifacts"}
						</p>
					) : null}
				</div>
			</header>

			{loading ? (
				<LoadingState />
			) : error && merged.length === 0 ? (
				<ErrorState onRetry={() => refresh()} />
			) : merged.length === 0 ? (
				<EmptyState />
			) : (
				<div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-3">
					{merged.map((artifact) => (
						<ArtifactCard
							key={artifact.key}
							artifact={artifact}
							href={artifactChatHref(workspaceId, artifact.sourceThreadId, artifact.artifactId)}
						/>
					))}
				</div>
			)}
		</div>
	);
}
