"use client";

import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { PanelRight } from "lucide-react";
import dynamic from "next/dynamic";
import { startTransition, useEffect } from "react";
import { closeHitlEditPanelAtom, hitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";
import { closeReportPanelAtom, reportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { documentsSidebarOpenAtom } from "@/atoms/documents/ui.atoms";
import { closeEditorPanelAtom, editorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { DocumentsSidebar } from "../sidebar";

const EditorPanelContent = dynamic(
	() =>
		import("@/components/editor-panel/editor-panel").then((m) => ({
			default: m.EditorPanelContent,
		})),
	{ ssr: false, loading: () => null }
);

const HitlEditPanelContent = dynamic(
	() =>
		import("@/components/hitl-edit-panel/hitl-edit-panel").then((m) => ({
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

interface RightPanelProps {
	documentsPanel?: {
		open: boolean;
		onOpenChange: (open: boolean) => void;
	};
}

function CollapseButton({ onClick }: { onClick: () => void }) {
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button variant="ghost" size="icon" onClick={onClick} className="h-8 w-8 shrink-0">
					<PanelRight className="h-4 w-4" />
					<span className="sr-only">Collapse panel</span>
				</Button>
			</TooltipTrigger>
			<TooltipContent side="bottom">Collapse panel</TooltipContent>
		</Tooltip>
	);
}

/**
 * Absolutely positioned expand button — renders at top-right of the main
 * container so it occupies the same screen position as the collapse button
 * inside the Documents header.
 */
export function RightPanelExpandButton() {
	const [collapsed, setCollapsed] = useAtom(rightPanelCollapsedAtom);
	const documentsOpen = useAtomValue(documentsSidebarOpenAtom);
	const reportState = useAtomValue(reportPanelAtom);
	const editorState = useAtomValue(editorPanelAtom);
	const hitlEditState = useAtomValue(hitlEditPanelAtom);
	const reportOpen = reportState.isOpen && !!reportState.reportId;
	const editorOpen =
		editorState.isOpen &&
		(editorState.kind === "document"
			? !!editorState.documentId
			: !!editorState.localFilePath);
	const hitlEditOpen = hitlEditState.isOpen && !!hitlEditState.onSave;
	const hasContent = documentsOpen || reportOpen || editorOpen || hitlEditOpen;

	if (!collapsed || !hasContent) return null;

	return (
		<div className="flex shrink-0 items-center px-0.5">
			<Tooltip>
				<TooltipTrigger asChild>
					<Button
						variant="ghost"
						size="icon"
						onClick={() => startTransition(() => setCollapsed(false))}
						className="h-8 w-8 shrink-0 -m-0.5"
					>
						<PanelRight className="h-4 w-4" />
						<span className="sr-only">Expand panel</span>
					</Button>
				</TooltipTrigger>
				<TooltipContent side="bottom">Expand panel</TooltipContent>
			</Tooltip>
		</div>
	);
}

const PANEL_WIDTHS = { sources: 420, report: 640, editor: 640, "hitl-edit": 640 } as const;

export function RightPanel({ documentsPanel }: RightPanelProps) {
	const [activeTab] = useAtom(rightPanelTabAtom);
	const reportState = useAtomValue(reportPanelAtom);
	const closeReport = useSetAtom(closeReportPanelAtom);
	const editorState = useAtomValue(editorPanelAtom);
	const closeEditor = useSetAtom(closeEditorPanelAtom);
	const hitlEditState = useAtomValue(hitlEditPanelAtom);
	const closeHitlEdit = useSetAtom(closeHitlEditPanelAtom);
	const [collapsed, setCollapsed] = useAtom(rightPanelCollapsedAtom);

	const documentsOpen = documentsPanel?.open ?? false;
	const reportOpen = reportState.isOpen && !!reportState.reportId;
	const editorOpen =
		editorState.isOpen &&
		(editorState.kind === "document"
			? !!editorState.documentId
			: !!editorState.localFilePath);
	const hitlEditOpen = hitlEditState.isOpen && !!hitlEditState.onSave;

	useEffect(() => {
		if (!reportOpen && !editorOpen && !hitlEditOpen) return;
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") {
				if (hitlEditOpen) closeHitlEdit();
				else if (editorOpen) closeEditor();
				else if (reportOpen) closeReport();
			}
		};
		document.addEventListener("keydown", handleKeyDown);
		return () => document.removeEventListener("keydown", handleKeyDown);
	}, [reportOpen, editorOpen, hitlEditOpen, closeReport, closeEditor, closeHitlEdit]);

	const isVisible = (documentsOpen || reportOpen || editorOpen || hitlEditOpen) && !collapsed;

	let effectiveTab = activeTab;
	if (effectiveTab === "hitl-edit" && !hitlEditOpen) {
		effectiveTab = editorOpen ? "editor" : reportOpen ? "report" : "sources";
	} else if (effectiveTab === "editor" && !editorOpen) {
		effectiveTab = reportOpen ? "report" : "sources";
	} else if (effectiveTab === "report" && !reportOpen) {
		effectiveTab = editorOpen ? "editor" : "sources";
	} else if (effectiveTab === "sources" && !documentsOpen) {
		effectiveTab = hitlEditOpen
			? "hitl-edit"
			: editorOpen
				? "editor"
				: reportOpen
					? "report"
					: "sources";
	}

	const targetWidth = PANEL_WIDTHS[effectiveTab];
	const collapseButton = <CollapseButton onClick={() => setCollapsed(true)} />;

	if (!isVisible) return null;

	return (
		<aside
			style={{ width: targetWidth }}
			className="flex h-full shrink-0 flex-col rounded-xl border bg-sidebar text-sidebar-foreground overflow-hidden transition-[width] duration-200 ease-out"
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
			</div>
		</aside>
	);
}
