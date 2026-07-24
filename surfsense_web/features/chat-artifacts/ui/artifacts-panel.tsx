"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { Boxes, XIcon } from "lucide-react";
import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { useMediaQuery } from "@/hooks/use-media-query";
import type { ArtifactKind, ChatArtifact } from "../model/artifact";
import {
	artifactsPanelOpenAtom,
	chatArtifactsAtom,
	closeArtifactsPanelAtom,
} from "../state/artifacts-panel.atom";
import { ArtifactRow } from "./artifact-row";

const GROUP_ORDER: { kind: ArtifactKind; label: string }[] = [
	{ kind: "report", label: "Reports" },
	{ kind: "resume", label: "Resumes" },
	{ kind: "podcast", label: "Podcasts" },
	{ kind: "video", label: "Presentations" },
	{ kind: "image", label: "Images" },
];

function groupByKind(artifacts: ChatArtifact[]): { label: string; items: ChatArtifact[] }[] {
	return GROUP_ORDER.map(({ kind, label }) => ({
		label,
		items: artifacts.filter((a) => a.kind === kind),
	})).filter((group) => group.items.length > 0);
}

function EmptyState() {
	return (
		<div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center select-none">
			<Boxes className="size-6 text-muted-foreground/60" />
			<p className="text-sm font-medium text-foreground">No artifacts yet</p>
			<p className="text-xs text-muted-foreground">
				Reports, podcasts, presentations, and images you generate will appear here.
			</p>
		</div>
	);
}

function ArtifactGroups({ artifacts }: { artifacts: ChatArtifact[] }) {
	const groups = useMemo(() => groupByKind(artifacts), [artifacts]);

	if (groups.length === 0) return <EmptyState />;

	return (
		<div className="flex-1 overflow-y-auto px-2 py-2">
			{groups.map((group) => (
				<div key={group.label} className="mb-3 last:mb-0">
					<p className="px-3 pb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground/80 select-none">
						{group.label}
					</p>
					<div className="flex flex-col gap-0.5">
						{group.items.map((artifact) => (
							<ArtifactRow key={artifact.key} artifact={artifact} />
						))}
					</div>
				</div>
			))}
		</div>
	);
}

/** Inner content shared by the desktop right-panel tab and the mobile drawer. */
export function ArtifactsPanelContent({ onClose }: { onClose?: () => void }) {
	const artifacts = useAtomValue(chatArtifactsAtom);

	return (
		<>
			<div className="shrink-0">
				<div className="grid h-12 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b px-4">
					<div className="min-w-0 flex flex-1 items-center gap-2">
						<p className="truncate text-sm text-muted-foreground">Artifacts</p>
					</div>
					<div className="flex items-center gap-1 shrink-0">
						{onClose && (
							<Button
								variant="ghost"
								size="icon"
								onClick={onClose}
								className="size-6 shrink-0 rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
							>
								<XIcon className="size-4" />
								<span className="sr-only">Close artifacts panel</span>
							</Button>
						)}
					</div>
				</div>
			</div>
			<ArtifactGroups artifacts={artifacts} />
		</>
	);
}

/**
 * Mobile artifacts drawer. Desktop renders inside the layout-level RightPanel
 * tab instead, so this no-ops on large screens.
 */
export function MobileArtifactsPanel() {
	const isOpen = useAtomValue(artifactsPanelOpenAtom);
	const close = useSetAtom(closeArtifactsPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	if (isDesktop || !isOpen) return null;

	return (
		<Drawer
			open={isOpen}
			onOpenChange={(open) => {
				if (!open) close();
			}}
			shouldScaleBackground={false}
		>
			<DrawerContent
				className="h-[85vh] max-h-[85vh] z-80 overflow-hidden bg-sidebar"
				overlayClassName="z-80"
			>
				<DrawerHandle />
				<DrawerTitle className="sr-only">Artifacts</DrawerTitle>
				<div className="flex min-h-0 flex-1 flex-col overflow-hidden">
					<ArtifactsPanelContent onClose={close} />
				</div>
			</DrawerContent>
		</Drawer>
	);
}
