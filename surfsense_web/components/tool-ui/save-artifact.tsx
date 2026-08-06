"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { useSetAtom } from "jotai";
import { Check, FileText } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { z } from "zod";
import { openArtifactPanelAtom } from "@/atoms/chat/artifact-panel.atom";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { useMediaQuery } from "@/hooks/use-media-query";

const SaveArtifactArgsSchema = z.object({
	title: z.string(),
	content: z.string(),
	description: z.string().nullish(),
	document_id: z.number().nullish(),
});

const SaveArtifactResultSchema = z.object({
	status: z.enum(["saved", "failed"]),
	document_id: z.number().nullish(),
	title: z.string().nullish(),
	files: z.array(z.unknown()).optional(),
	error: z.string().nullish(),
});

type SaveArtifactArgs = z.infer<typeof SaveArtifactArgsSchema>;
type SaveArtifactResult = z.infer<typeof SaveArtifactResultSchema>;

function ArtifactPending({ title }: { title: string }) {
	return (
		<div className="my-4 max-w-lg rounded-xl border bg-muted/30 px-5 py-4">
			<p className="text-sm font-semibold">{title}</p>
			<TextShimmerLoader text="Saving artifact" size="sm" />
		</div>
	);
}

function ArtifactError({ title, error }: { title: string; error: string }) {
	return (
		<div role="alert" className="my-4 max-w-lg rounded-xl border bg-muted/30 px-5 py-4">
			<p className="text-sm font-semibold text-destructive">Artifact save failed</p>
			<p className="mt-1 text-sm text-foreground">{title}</p>
			<p className="mt-1 text-xs text-muted-foreground">{error}</p>
		</div>
	);
}

function ArtifactCard({
	documentId,
	title,
	autoOpen,
	publicRoute,
}: {
	documentId: number;
	title: string;
	autoOpen: boolean;
	publicRoute: boolean;
}) {
	const openPanel = useSetAtom(openArtifactPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 768px)");
	const openedRef = useRef(false);

	useEffect(() => {
		if (autoOpen && isDesktop && !publicRoute && !openedRef.current) {
			openedRef.current = true;
			openPanel({ documentId });
		}
	}, [autoOpen, documentId, isDesktop, openPanel, publicRoute]);

	return (
		<Button
			type="button"
			variant="outline"
			disabled={publicRoute}
			onClick={() => openPanel({ documentId })}
			className="my-4 h-auto w-full max-w-lg justify-start gap-3 rounded-xl p-4 text-left"
		>
			<span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
				<FileText className="size-5 text-muted-foreground" />
			</span>
			<span className="min-w-0 flex-1">
				<span className="block truncate text-sm font-medium">{title}</span>
				<span className="mt-0.5 block text-xs text-muted-foreground">Markdown document</span>
			</span>
			<Check className="size-4 text-muted-foreground" />
		</Button>
	);
}

export const SaveArtifactToolUI = ({
	args,
	result,
	status,
}: ToolCallMessagePartProps<SaveArtifactArgs, SaveArtifactResult>) => {
	const pathname = usePathname();
	const publicRoute = pathname?.startsWith("/public/") ?? false;
	const sawRunningRef = useRef(false);
	if (status.type === "running" || status.type === "requires-action") {
		sawRunningRef.current = true;
		return <ArtifactPending title={args.title || "Document"} />;
	}
	if (status.type === "incomplete") {
		return (
			<ArtifactError
				title={args.title || "Document"}
				error={
					status.reason === "cancelled"
						? "Artifact saving was cancelled"
						: typeof status.error === "string"
							? status.error
							: "An error occurred"
				}
			/>
		);
	}
	if (!result) return <ArtifactPending title={args.title || "Document"} />;
	if (result.status === "failed") {
		return (
			<ArtifactError
				title={result.title || args.title || "Document"}
				error={result.error || "The artifact could not be saved"}
			/>
		);
	}
	if (!result.document_id) {
		return <ArtifactError title={args.title || "Document"} error="Missing document ID" />;
	}
	return (
		<ArtifactCard
			documentId={result.document_id}
			title={result.title || args.title || "Document"}
			autoOpen={sawRunningRef.current}
			publicRoute={publicRoute}
		/>
	);
};
