"use client";

import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { PanelRight, PanelRightClose } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { startTransition, useEffect } from "react";
import { closeReportPanelAtom, reportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { documentsSidebarOpenAtom } from "@/atoms/documents/ui.atoms";
import { rightPanelCollapsedAtom, rightPanelTabAtom } from "@/atoms/layout/right-panel.atom";
import { ReportPanelContent } from "@/components/report-panel/report-panel";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { DocumentsSidebar } from "../sidebar";

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
					<PanelRightClose className="h-4 w-4" />
					<span className="sr-only">Collapse panel</span>
				</Button>
			</TooltipTrigger>
			<TooltipContent side="left">Collapse panel</TooltipContent>
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
	const reportOpen = reportState.isOpen && !!reportState.reportId;
	const hasContent = documentsOpen || reportOpen;

	if (!collapsed || !hasContent) return null;

	return (
		<div className="absolute top-4 right-4 z-20">
			<Tooltip>
				<TooltipTrigger asChild>
					<Button
						variant="ghost"
						size="icon"
					onClick={() => startTransition(() => setCollapsed(false))}
					className="h-8 w-8 shrink-0"
					>
						<PanelRight className="h-4 w-4" />
						<span className="sr-only">Expand panel</span>
					</Button>
				</TooltipTrigger>
				<TooltipContent side="left">Expand panel</TooltipContent>
			</Tooltip>
		</div>
	);
}

const PANEL_WIDTHS = { sources: 420, report: 640 } as const;

export function RightPanel({ documentsPanel }: RightPanelProps) {
	const [activeTab] = useAtom(rightPanelTabAtom);
	const reportState = useAtomValue(reportPanelAtom);
	const closeReport = useSetAtom(closeReportPanelAtom);
	const [collapsed, setCollapsed] = useAtom(rightPanelCollapsedAtom);

	const documentsOpen = documentsPanel?.open ?? false;
	const reportOpen = reportState.isOpen && !!reportState.reportId;

	useEffect(() => {
		if (!reportOpen) return;
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") closeReport();
		};
		document.addEventListener("keydown", handleKeyDown);
		return () => document.removeEventListener("keydown", handleKeyDown);
	}, [reportOpen, closeReport]);

	const isVisible = (documentsOpen || reportOpen) && !collapsed;

	const effectiveTab =
		activeTab === "report" && !reportOpen
			? "sources"
			: activeTab === "sources" && !documentsOpen
				? "report"
				: activeTab;

	const targetWidth = PANEL_WIDTHS[effectiveTab];
	const collapseButton = <CollapseButton onClick={() => setCollapsed(true)} />;

	const contentKey =
		effectiveTab === "sources" && documentsOpen
			? "sources"
			: effectiveTab === "report" && reportOpen
				? "report"
				: null;

	return (
		<AnimatePresence>
			{isVisible && (
			<motion.aside
				key="right-panel"
				initial={{ width: 0, opacity: 0 }}
				animate={{ width: targetWidth, opacity: 1 }}
				exit={{ width: 0, opacity: 0 }}
				transition={{
					width: { type: "spring", stiffness: 400, damping: 35, mass: 0.8 },
					opacity: { duration: 0.2, ease: "easeOut" },
				}}
				style={{ willChange: "width, opacity", contain: "layout style" }}
				className="flex h-full shrink-0 flex-col border-l bg-background overflow-hidden"
			>
				<div className="relative flex-1 min-h-0 overflow-hidden">
					<AnimatePresence mode="popLayout" initial={false}>
						{contentKey === "sources" && documentsPanel && (
							<motion.div
								key="sources"
								initial={{ opacity: 0, x: 8 }}
								animate={{ opacity: 1, x: 0 }}
								exit={{ opacity: 0, x: -8 }}
								transition={{ duration: 0.15, ease: "easeOut" }}
								className="h-full"
							>
								<DocumentsSidebar
									open={documentsPanel.open}
									onOpenChange={documentsPanel.onOpenChange}
									embedded
									headerAction={collapseButton}
								/>
							</motion.div>
						)}
						{contentKey === "report" && (
							<motion.div
								key="report"
								initial={{ opacity: 0, x: 8 }}
								animate={{ opacity: 1, x: 0 }}
								exit={{ opacity: 0, x: -8 }}
								transition={{ duration: 0.15, ease: "easeOut" }}
								className="h-full"
							>
								<div className="flex h-full flex-col">
									<ReportPanelContent
										reportId={reportState.reportId!}
										title={reportState.title || "Report"}
										onClose={closeReport}
										shareToken={reportState.shareToken}
									/>
								</div>
							</motion.div>
						)}
					</AnimatePresence>
					</div>
				</motion.aside>
			)}
		</AnimatePresence>
	);
}
