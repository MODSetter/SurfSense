"use client";

import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { PanelRight } from "lucide-react";
import dynamic from "next/dynamic";
import { type MouseEvent, startTransition, useEffect } from "react";
import { closeReportPanelAtom, reportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { citationPanelAtom, closeCitationPanelAtom } from "@/atoms/citation/citation-panel.atom";
import { documentsSidebarOpenAtom } from "@/atoms/documents/ui.atoms";
import { closeEditorPanelAtom, editorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import {
	type RightPanelTab,
	rightPanelCollapsedAtom,
	rightPanelTabAtom,
} from "@/atoms/layout/right-panel.atom";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { artifactsPanelOpenAtom, closeArtifactsPanelAtom } from "@/features/chat-artifacts";
import { closeHitlEditPanelAtom, hitlEditPanelAtom } from "@/features/chat-messages/hitl";
import { cn } from "@/lib/utils";
import { DocumentsSidebar } from "../sidebar";

const EditorPanelContent = dynamic(
	() =>
		import("@/components/editor-panel/editor-panel").then((m) => ({
			default: m.EditorPanelContent,
		})),
	{ ssr: false, loading: () => null }
);

const CitationPanelContent = dynamic(
	() =>
		import("@/components/citation-panel/citation-panel").then((m) => ({
			default: m.CitationPanelContent,
		})),
	{ ssr: false, loading: () => null }
);

const HitlEditPanelContent = dynamic(
	() =>
		import("@/features/chat-messages/hitl").then((m) => ({
			default: m.HitlEditPanelContent,
		})),
	{ ssr: false, loading: () => null }
);

const ReportPanelContent = dynamic(
	() =>
		import("@/components/report-panel/report-panel").then((m) => ({
			default: m.ReportPanelContent,
		})),
	{ ssr: false, loading: () => null }
);

const ArtifactsPanelContent = dynamic(
	() =>
		import("@/features/chat-artifacts").then((m) => ({
			default: m.ArtifactsPanelContent,
		})),
	{ ssr: false, loading: () => null }
);

interface RightPanelProps {
	documentsPanel?: {
		open: boolean;
		onOpenChange: (open: boolean) => void;
	};
	showCollapseButton?: boolean;
	showTopBorder?: boolean;
}

function isKeyboardClick(event: MouseEvent) {
	return event.detail === 0;
}

function CollapseButton({ onClick }: { onClick: () => void }) {
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button
					variant="ghost"
					size="icon"
					tabIndex={-1}
					onClick={(event) => {
						if (isKeyboardClick(event)) return;
						onClick();
					}}
					className="h-8 w-8 shrink-0 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
				>
					<PanelRight className="h-4 w-4" />
					<span className="sr-only">Collapse panel</span>
				</Button>
			</TooltipTrigger>
			<TooltipContent side="bottom">Collapse panel</TooltipContent>
		</Tooltip>
	);
}

interface RightPanelToggleButtonProps {
	className?: string;
	iconClassName?: string;
	disabled?: boolean;
}

export function RightPanelToggleButton({
	className,
	iconClassName,
	disabled = false,
}: RightPanelToggleButtonProps) {
	const [collapsed, setCollapsed] = useAtom(rightPanelCollapsedAtom);
	const documentsOpen = useAtomValue(documentsSidebarOpenAtom);
	const reportState = useAtomValue(reportPanelAtom);
	const editorState = useAtomValue(editorPanelAtom);
	const hitlEditState = useAtomValue(hitlEditPanelAtom);
	const citationState = useAtomValue(citationPanelAtom);
	const artifactsOpen = useAtomValue(artifactsPanelOpenAtom);
	const reportOpen = reportState.isOpen && !!reportState.reportId;
	const editorOpen =
		editorState.isOpen &&
		(editorState.kind === "document"
			? !!editorState.documentId
			: editorState.kind === "memory"
				? !!editorState.memoryScope
				: !!editorState.localFilePath);
	const hitlEditOpen = hitlEditState.isOpen && !!hitlEditState.onSave;
	const citationOpen = citationState.isOpen && citationState.chunkId != null;
	const hasContent =
		documentsOpen || reportOpen || editorOpen || hitlEditOpen || citationOpen || artifactsOpen;
	const label = collapsed ? "Expand panel" : "Collapse panel";

	if (!hasContent) return null;

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button
					variant="ghost"
					size="icon"
					disabled={disabled}
					onClick={() => {
						if (disabled) return;
						startTransition(() => setCollapsed((value) => !value));
					}}
					className={cn(
						"h-8 w-8 shrink-0 text-muted-foreground hover:bg-accent hover:text-accent-foreground",
						className
					)}
				>
					<PanelRight className={cn("h-4 w-4", iconClassName)} />
					<span className="sr-only">{label}</span>
				</Button>
			</TooltipTrigger>
			<TooltipContent side="bottom">{label}</TooltipContent>
		</Tooltip>
	);
}

/**
 * Absolutely positioned expand button — renders at top-right of the main
 * container so it occupies the same screen position as the collapse button
 * inside the Documents header.
 */
export function RightPanelExpandButton() {
	const [collapsed] = useAtom(rightPanelCollapsedAtom);
	const documentsOpen = useAtomValue(documentsSidebarOpenAtom);
	const reportState = useAtomValue(reportPanelAtom);
	const editorState = useAtomValue(editorPanelAtom);
	const hitlEditState = useAtomValue(hitlEditPanelAtom);
	const citationState = useAtomValue(citationPanelAtom);
	const artifactsOpen = useAtomValue(artifactsPanelOpenAtom);
	const reportOpen = reportState.isOpen && !!reportState.reportId;
	const editorOpen =
		editorState.isOpen &&
		(editorState.kind === "document"
			? !!editorState.documentId
			: editorState.kind === "memory"
				? !!editorState.memoryScope
				: !!editorState.localFilePath);
	const hitlEditOpen = hitlEditState.isOpen && !!hitlEditState.onSave;
	const citationOpen = citationState.isOpen && citationState.chunkId != null;
	const hasContent =
		documentsOpen || reportOpen || editorOpen || hitlEditOpen || citationOpen || artifactsOpen;

	if (!collapsed || !hasContent) return null;

	return (
		<div className="flex shrink-0 items-center px-0.5">
			<RightPanelToggleButton className="-m-0.5" />
		</div>
	);
}

const PANEL_WIDTHS = {
	sources: 420,
	report: 640,
	editor: 640,
	"hitl-edit": 640,
	citation: 560,
	artifacts: 420,
} as const;

/**
 * Priority order used to fall back to another open surface when the active
 * tab's content closes. Artifacts sit just above the always-available sources
 * tab.
 */
const TAB_FALLBACK_ORDER: RightPanelTab[] = [
	"hitl-edit",
	"citation",
	"editor",
	"report",
	"artifacts",
	"sources",
];

function resolveEffectiveTab(
	activeTab: RightPanelTab,
	openByTab: Record<RightPanelTab, boolean>
): RightPanelTab {
	if (openByTab[activeTab]) return activeTab;
	return TAB_FALLBACK_ORDER.find((tab) => openByTab[tab]) ?? "sources";
}

export function RightPanel({
	documentsPanel,
	showCollapseButton = true,
	showTopBorder = false,
}: RightPanelProps) {
	const [activeTab] = useAtom(rightPanelTabAtom);
	const reportState = useAtomValue(reportPanelAtom);
	const closeReport = useSetAtom(closeReportPanelAtom);
	const editorState = useAtomValue(editorPanelAtom);
	const closeEditor = useSetAtom(closeEditorPanelAtom);
	const hitlEditState = useAtomValue(hitlEditPanelAtom);
	const closeHitlEdit = useSetAtom(closeHitlEditPanelAtom);
	const citationState = useAtomValue(citationPanelAtom);
	const closeCitation = useSetAtom(closeCitationPanelAtom);
	const artifactsOpen = useAtomValue(artifactsPanelOpenAtom);
	const closeArtifacts = useSetAtom(closeArtifactsPanelAtom);
	const [collapsed, setCollapsed] = useAtom(rightPanelCollapsedAtom);

	const documentsOpen = documentsPanel?.open ?? false;
	const reportOpen = reportState.isOpen && !!reportState.reportId;
	const editorOpen =
		editorState.isOpen &&
		(editorState.kind === "document"
			? !!editorState.documentId
			: editorState.kind === "memory"
				? !!editorState.memoryScope
				: !!editorState.localFilePath);
	const hitlEditOpen = hitlEditState.isOpen && !!hitlEditState.onSave;
	const citationOpen = citationState.isOpen && citationState.chunkId != null;

	useEffect(() => {
		if (!reportOpen && !editorOpen && !hitlEditOpen && !citationOpen && !artifactsOpen) return;
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") {
				if (hitlEditOpen) closeHitlEdit();
				else if (citationOpen) closeCitation();
				else if (editorOpen) closeEditor();
				else if (reportOpen) closeReport();
				else if (artifactsOpen) closeArtifacts();
			}
		};
		document.addEventListener("keydown", handleKeyDown);
		return () => document.removeEventListener("keydown", handleKeyDown);
	}, [
		reportOpen,
		editorOpen,
		hitlEditOpen,
		citationOpen,
		artifactsOpen,
		closeReport,
		closeEditor,
		closeHitlEdit,
		closeCitation,
		closeArtifacts,
	]);

	const isVisible =
		(documentsOpen || reportOpen || editorOpen || hitlEditOpen || citationOpen || artifactsOpen) &&
		!collapsed;

	const effectiveTab = resolveEffectiveTab(activeTab, {
		sources: documentsOpen,
		report: reportOpen,
		editor: editorOpen,
		"hitl-edit": hitlEditOpen,
		citation: citationOpen,
		artifacts: artifactsOpen,
	});

	const targetWidth = PANEL_WIDTHS[effectiveTab];
	const collapseButton = showCollapseButton ? (
		<CollapseButton onClick={() => setCollapsed(true)} />
	) : null;

	if (!isVisible) return null;

	return (
		<aside
			style={{ width: targetWidth }}
			className={cn(
				"flex h-full shrink-0 flex-col border-l bg-panel text-sidebar-foreground overflow-hidden transition-[width] duration-200 ease-out",
				showTopBorder && "border-t"
			)}
		>
			<div className="relative flex-1 min-h-0 overflow-hidden">
				{effectiveTab === "sources" && documentsOpen && documentsPanel && (
					<div className="h-full">
						<DocumentsSidebar
							open={documentsPanel.open}
							onOpenChange={documentsPanel.onOpenChange}
							embedded
							headerAction={collapseButton}
						/>
					</div>
				)}
				{effectiveTab === "report" && reportOpen && (
					<div className="h-full flex flex-col">
						<ReportPanelContent
							reportId={reportState.reportId as number}
							title={reportState.title || "Report"}
							onClose={closeReport}
							shareToken={reportState.shareToken}
						/>
					</div>
				)}
				{effectiveTab === "editor" && editorOpen && (
					<div className="h-full flex flex-col">
						<EditorPanelContent
							kind={editorState.kind}
							documentId={editorState.documentId ?? undefined}
							localFilePath={editorState.localFilePath ?? undefined}
							memoryScope={editorState.memoryScope ?? undefined}
							searchSpaceId={editorState.searchSpaceId ?? undefined}
							title={editorState.title}
							onClose={closeEditor}
						/>
					</div>
				)}
				{effectiveTab === "hitl-edit" && hitlEditOpen && hitlEditState.onSave && (
					<div className="h-full flex flex-col">
						<HitlEditPanelContent
							title={hitlEditState.title}
							content={hitlEditState.content}
							toolName={hitlEditState.toolName}
							contentFormat={hitlEditState.contentFormat}
							extraFields={hitlEditState.extraFields}
							onSave={hitlEditState.onSave}
							onClose={closeHitlEdit}
						/>
					</div>
				)}
				{effectiveTab === "citation" && citationOpen && citationState.chunkId != null && (
					<div className="h-full flex flex-col">
						<CitationPanelContent chunkId={citationState.chunkId} onClose={closeCitation} />
					</div>
				)}
				{effectiveTab === "artifacts" && artifactsOpen && (
					<div className="h-full flex flex-col">
						<ArtifactsPanelContent onClose={closeArtifacts} />
					</div>
				)}
			</div>
		</aside>
	);
}
