"use client";

import { useAtomValue } from "jotai";
import { LayersIcon, XIcon } from "lucide-react";
import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import type { ArtifactKind, ChatArtifact } from "../model/artifact";
import { chatArtifactsAtom } from "../state/artifacts-panel.atom";
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
			<LayersIcon className="size-6 text-muted-foreground/60" />
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
			<div className="flex h-12 shrink-0 items-center justify-between border-b px-3">
				<h2 className="select-none text-lg font-semibold">Artifacts</h2>
				{onClose && (
					<Button
						variant="ghost"
						size="icon"
						onClick={onClose}
						className="h-8 w-8 shrink-0 rounded-full text-muted-foreground hover:text-accent-foreground"
					>
						<XIcon className="h-4 w-4" />
						<span className="sr-only">Close artifacts panel</span>
					</Button>
				)}
			</div>
			<ArtifactGroups artifacts={artifacts} />
		</>
	);
}
