"use client";

import { useAtomValue } from "jotai";
import { FileWarning, RefreshCw, XIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { z } from "zod";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { FileDownloadCard } from "./file-download-card";
import type { ArtifactContent } from "./model";
import { VIEWERS } from "./viewer-registry";

const ArtifactFileSchema = z.object({
	file_id: z.number(),
	role: z.enum(["primary", "preview"]),
	filename: z.string(),
	mime_type: z.string(),
	size_bytes: z.number(),
	content_url: z.string(),
});

const ArtifactContentSchema = z.discriminatedUnion("kind", [
	z.object({
		kind: z.literal("text"),
		document_id: z.number(),
		title: z.string(),
		source_markdown: z.string(),
		generated: z.boolean(),
		updated_at: z.string().nullable(),
	}),
	z.object({
		kind: z.literal("file"),
		document_id: z.number(),
		title: z.string(),
		generated: z.boolean(),
		files: z.array(ArtifactFileSchema),
		updated_at: z.string().nullable(),
	}),
]);

export function ArtifactPanelContent({
	documentId,
	onClose,
}: {
	documentId: number;
	onClose: () => void;
}) {
	const workspaceId = Number(useAtomValue(activeWorkspaceIdAtom));
	const [content, setContent] = useState<ArtifactContent | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [attempt, setAttempt] = useState(0);

	const retry = useCallback(() => setAttempt((value) => value + 1), []);

	useEffect(() => {
		let active = true;
		const load = async () => {
			setLoading(true);
			setError(null);
			try {
				if (!Number.isFinite(workspaceId) || workspaceId <= 0) {
					throw new Error("No workspace selected");
				}
				const response = await authenticatedFetch(
					buildBackendUrl(
						`/api/v1/workspaces/${workspaceId}/documents/${documentId}/editor-content?retry=${attempt}`
					)
				);
				if (!response.ok) throw new Error("Artifact could not be loaded");
				const parsed = ArtifactContentSchema.safeParse(await response.json());
				if (!parsed.success) throw new Error("Artifact response is invalid");
				if (active) setContent(parsed.data);
			} catch (loadError) {
				if (active) {
					setContent(null);
					setError(loadError instanceof Error ? loadError.message : "Artifact could not be loaded");
				}
			} finally {
				if (active) setLoading(false);
			}
		};
		void load();
		return () => {
			active = false;
		};
	}, [workspaceId, documentId, attempt]);

	return (
		<div className="flex h-full min-h-0 flex-col">
			<div className="shrink-0">
				<div className="grid h-12 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b px-4">
					<p className="truncate text-sm text-muted-foreground">
						{content?.title ?? (loading ? "Loading…" : "Artifact")}
					</p>
					<Button
						variant="ghost"
						size="icon"
						onClick={onClose}
						className="size-6 shrink-0 rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
					>
						<XIcon className="size-4" />
						<span className="sr-only">Close artifact panel</span>
					</Button>
				</div>
			</div>

			{/* Viewers fill the panel edge to edge; everything else scrolls with padding. */}
			<div className="min-h-0 flex-1 overflow-hidden" aria-busy={loading}>
				{loading ? (
					<div className="h-full space-y-3 px-5 py-4">
						<Skeleton className="h-7 w-2/3" />
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-5/6" />
						<Skeleton className="h-4 w-4/6" />
					</div>
				) : error ? (
					<div
						role="alert"
						className="flex h-full flex-col items-center justify-center gap-3 px-5 py-4 text-center"
					>
						<FileWarning className="size-8 text-muted-foreground" />
						<div>
							<p className="text-sm font-medium">Couldn&apos;t open this artifact</p>
							<p className="mt-1 text-xs text-muted-foreground">{error}</p>
						</div>
						<Button variant="outline" size="sm" onClick={retry}>
							<RefreshCw className="size-4" />
							Try again
						</Button>
					</div>
				) : content?.kind === "text" ? (
					<div className="h-full overflow-y-auto px-5 py-4">
						<MarkdownViewer content={content.source_markdown} className="mx-auto max-w-3xl" />
					</div>
				) : content?.kind === "file" ? (
					<FileArtifact content={content} />
				) : null}
			</div>
		</div>
	);
}

function FileArtifact({ content }: { content: Extract<ArtifactContent, { kind: "file" }> }) {
	const primary = content.files.find((file) => file.role === "primary");
	if (!primary) {
		return (
			<p className="px-5 py-4 text-sm text-muted-foreground">This artifact has no primary file.</p>
		);
	}
	const Viewer = VIEWERS[primary.mime_type];
	return Viewer ? (
		<Viewer primary={primary} files={content.files} />
	) : (
		<div className="h-full overflow-y-auto px-5 py-4">
			<FileDownloadCard file={primary} />
		</div>
	);
}
