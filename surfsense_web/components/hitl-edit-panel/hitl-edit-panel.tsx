"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { XIcon } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import {
	closeHitlEditPanelAtom,
	hitlEditPanelAtom,
} from "@/atoms/chat/hitl-edit-panel.atom";
import { PlateEditor } from "@/components/editor/plate-editor";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { useMediaQuery } from "@/hooks/use-media-query";

export function HitlEditPanelContent({
	title: initialTitle,
	content: initialContent,
	onSave,
	onClose,
}: {
	title: string;
	content: string;
	toolName: string;
	onSave: (title: string, content: string) => void;
	onClose?: () => void;
}) {
	const [editedTitle, setEditedTitle] = useState(initialTitle);
	const markdownRef = useRef(initialContent);
	const [isSaving, setIsSaving] = useState(false);

	const handleMarkdownChange = useCallback((md: string) => {
		markdownRef.current = md;
	}, []);

	const handleSave = useCallback(() => {
		if (!editedTitle.trim()) return;
		setIsSaving(true);
		onSave(editedTitle, markdownRef.current);
		onClose?.();
	}, [editedTitle, onSave, onClose]);

	return (
		<>
			<div className="flex items-center gap-2 px-4 py-2 shrink-0 border-b">
				<input
					value={editedTitle}
					onChange={(e) => setEditedTitle(e.target.value)}
					placeholder="Untitled"
					className="flex-1 min-w-0 bg-transparent text-sm font-semibold text-foreground outline-none placeholder:text-muted-foreground"
					aria-label="Page title"
				/>
				{onClose && (
					<Button variant="ghost" size="icon" onClick={onClose} className="size-7 shrink-0">
						<XIcon className="size-4" />
						<span className="sr-only">Close panel</span>
					</Button>
				)}
			</div>

			<div className="flex-1 overflow-hidden">
				<PlateEditor
					markdown={initialContent}
					onMarkdownChange={handleMarkdownChange}
					readOnly={false}
					preset="full"
					placeholder="Start writing..."
					editorVariant="default"
					defaultEditing
					onSave={handleSave}
					hasUnsavedChanges
					isSaving={isSaving}
					className="[&_[role=toolbar]]:!bg-sidebar"
				/>
			</div>
		</>
	);
}

function DesktopHitlEditPanel() {
	const panelState = useAtomValue(hitlEditPanelAtom);
	const closePanel = useSetAtom(closeHitlEditPanelAtom);

	if (!panelState.isOpen || !panelState.onSave) return null;

	return (
		<div className="flex w-[50%] max-w-[700px] min-w-[380px] flex-col border-l bg-sidebar text-sidebar-foreground animate-in slide-in-from-right-4 duration-300 ease-out">
			<HitlEditPanelContent
				title={panelState.title}
				content={panelState.content}
				toolName={panelState.toolName}
				onSave={panelState.onSave}
				onClose={closePanel}
			/>
		</div>
	);
}

function MobileHitlEditDrawer() {
	const panelState = useAtomValue(hitlEditPanelAtom);
	const closePanel = useSetAtom(closeHitlEditPanelAtom);

	if (!panelState.onSave) return null;

	return (
		<Drawer
			open={panelState.isOpen}
			onOpenChange={(open) => {
				if (!open) closePanel();
			}}
			shouldScaleBackground={false}
		>
			<DrawerContent
				className="h-[95vh] max-h-[95vh] z-80 bg-sidebar overflow-hidden"
				overlayClassName="z-80"
			>
				<DrawerHandle />
				<DrawerTitle className="sr-only">
					Edit {panelState.toolName}
				</DrawerTitle>
				<div className="min-h-0 flex-1 flex flex-col overflow-hidden">
					<HitlEditPanelContent
						title={panelState.title}
						content={panelState.content}
						toolName={panelState.toolName}
						onSave={panelState.onSave}
						onClose={closePanel}
					/>
				</div>
			</DrawerContent>
		</Drawer>
	);
}

export function HitlEditPanel() {
	const panelState = useAtomValue(hitlEditPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	if (!panelState.isOpen) return null;

	if (isDesktop) {
		return <DesktopHitlEditPanel />;
	}

	return <MobileHitlEditDrawer />;
}

export function MobileHitlEditPanel() {
	const panelState = useAtomValue(hitlEditPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	if (isDesktop || !panelState.isOpen) return null;

	return <MobileHitlEditDrawer />;
}
