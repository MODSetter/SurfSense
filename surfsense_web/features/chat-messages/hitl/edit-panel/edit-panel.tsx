"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { XIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { Skeleton } from "@/components/ui/skeleton";
import { useMediaQuery } from "@/hooks/use-media-query";
import { closeHitlEditPanelAtom, type ExtraField, hitlEditPanelAtom } from "./edit-panel.atom";
import { ExtraFieldsSection } from "./fields";

const PlateEditor = dynamic(
	() => import("@/components/editor/plate-editor").then((m) => ({ default: m.PlateEditor })),
	{ ssr: false, loading: () => <Skeleton className="h-64 w-full" /> }
);

/**
 * The actual editable form. Controlled by atom data via the
 * Desktop/Mobile shells below; isolated from layout so the same form
 * renders identically in either container.
 */
export function HitlEditPanelContent({
	title: initialTitle,
	content: initialContent,
	contentFormat,
	extraFields,
	onSave,
	onClose,
	showCloseButton = true,
}: {
	title: string;
	content: string;
	toolName: string;
	contentFormat?: "markdown" | "html";
	extraFields?: ExtraField[];
	onSave: (title: string, content: string, extraFieldValues?: Record<string, string>) => void;
	onClose?: () => void;
	showCloseButton?: boolean;
}) {
	const [editedTitle, setEditedTitle] = useState(initialTitle);
	const contentRef = useRef(initialContent);
	const [isSaving, setIsSaving] = useState(false);
	const [extraFieldValues, setExtraFieldValues] = useState<Record<string, string>>(() => {
		if (!extraFields) return {};
		const initial: Record<string, string> = {};
		for (const field of extraFields) {
			initial[field.key] = field.value;
		}
		return initial;
	});

	const handleContentChange = useCallback((content: string) => {
		contentRef.current = content;
	}, []);

	const handleExtraFieldChange = useCallback((key: string, value: string) => {
		setExtraFieldValues((prev) => ({ ...prev, [key]: value }));
	}, []);

	const handleSave = useCallback(() => {
		if (!editedTitle.trim()) return;
		setIsSaving(true);
		const extras = extraFields && extraFields.length > 0 ? extraFieldValues : undefined;
		onSave(editedTitle, contentRef.current, extras);
		onClose?.();
	}, [editedTitle, onSave, onClose, extraFields, extraFieldValues]);

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
				{onClose && showCloseButton && (
					<Button variant="ghost" size="icon" onClick={onClose} className="size-7 shrink-0">
						<XIcon className="size-4" />
						<span className="sr-only">Close panel</span>
					</Button>
				)}
			</div>

			{extraFields && extraFields.length > 0 && (
				<ExtraFieldsSection
					fields={extraFields}
					values={extraFieldValues}
					onFieldChange={handleExtraFieldChange}
				/>
			)}

			<div className="flex-1 overflow-hidden">
				<PlateEditor
					{...(contentFormat === "html"
						? { html: initialContent, onHtmlChange: handleContentChange }
						: { markdown: initialContent, onMarkdownChange: handleContentChange })}
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
				contentFormat={panelState.contentFormat}
				extraFields={panelState.extraFields}
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
				className="h-[90vh] max-h-[90vh] z-80 bg-sidebar overflow-hidden"
				overlayClassName="z-80"
			>
				<DrawerHandle />
				<DrawerTitle className="sr-only">Edit {panelState.toolName}</DrawerTitle>
				<div className="min-h-0 flex-1 flex flex-col overflow-hidden">
					<HitlEditPanelContent
						title={panelState.title}
						content={panelState.content}
						toolName={panelState.toolName}
						contentFormat={panelState.contentFormat}
						extraFields={panelState.extraFields}
						onSave={panelState.onSave}
						onClose={closePanel}
						showCloseButton={false}
					/>
				</div>
			</DrawerContent>
		</Drawer>
	);
}

/**
 * Entry point mounted by the right-panel layout. Renders the desktop
 * panel on lg+ and the mobile drawer below; both share state via the
 * ``hitlEditPanelAtom``.
 */
export function HitlEditPanel() {
	const panelState = useAtomValue(hitlEditPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	if (!panelState.isOpen) return null;

	if (isDesktop) {
		return <DesktopHitlEditPanel />;
	}

	return <MobileHitlEditDrawer />;
}

/**
 * Entry point mounted by chat pages so the mobile drawer can render
 * outside the desktop right-panel container.
 */
export function MobileHitlEditPanel() {
	const panelState = useAtomValue(hitlEditPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	if (isDesktop || !panelState.isOpen) return null;

	return <MobileHitlEditDrawer />;
}
