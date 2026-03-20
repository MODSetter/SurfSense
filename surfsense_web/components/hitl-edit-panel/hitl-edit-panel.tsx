"use client";

import { TagInput, type Tag as TagType } from "emblor";
import { useAtomValue, useSetAtom } from "jotai";
import { XIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
	closeHitlEditPanelAtom,
	hitlEditPanelAtom,
} from "@/atoms/chat/hitl-edit-panel.atom";
import type { ExtraField } from "@/atoms/chat/hitl-edit-panel.atom";
import { PlateEditor } from "@/components/editor/plate-editor";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useMediaQuery } from "@/hooks/use-media-query";

function parseEmailsToTags(value: string): TagType[] {
	if (!value.trim()) return [];
	return value
		.split(",")
		.map((s) => s.trim())
		.filter(Boolean)
		.map((email, i) => ({ id: `${Date.now()}-${i}`, text: email }));
}

function tagsToEmailString(tags: TagType[]): string {
	return tags.map((t) => t.text).join(", ");
}

function EmailsTagField({
	id,
	value,
	onChange,
	placeholder,
}: {
	id: string;
	value: string;
	onChange: (value: string) => void;
	placeholder?: string;
}) {
	const [tags, setTags] = useState<TagType[]>(() => parseEmailsToTags(value));
	const [activeTagIndex, setActiveTagIndex] = useState<number | null>(null);
	const isInitialMount = useRef(true);

	useEffect(() => {
		if (isInitialMount.current) {
			isInitialMount.current = false;
			return;
		}
		onChange(tagsToEmailString(tags));
	}, [tags, onChange]);

	const handleSetTags = useCallback(
		(newTags: TagType[] | ((prev: TagType[]) => TagType[])) => {
			setTags((prev) =>
				typeof newTags === "function" ? newTags(prev) : newTags
			);
		},
		[]
	);

	const handleAddTag = useCallback(
		(text: string) => {
			const trimmed = text.trim();
			if (!trimmed) return;
			if (tags.some((tag) => tag.text === trimmed)) return;
			const newTag: TagType = { id: Date.now().toString(), text: trimmed };
			setTags((prev) => [...prev, newTag]);
		},
		[tags]
	);

	return (
		<TagInput
			id={id}
			tags={tags}
			setTags={handleSetTags}
			placeholder={placeholder ?? "Add email"}
			onAddTag={handleAddTag}
			styleClasses={{
				inlineTagsContainer:
					"border border-input rounded-md bg-transparent shadow-xs transition-[color,box-shadow] outline-none focus-within:border-ring p-1 gap-1",
				input:
					"w-full min-w-[80px] focus-visible:outline-none shadow-none px-2 h-7 text-foreground placeholder:text-muted-foreground bg-transparent text-sm md:text-sm",
				tag: {
					body: "h-7 relative bg-accent dark:bg-muted/60 border-0 hover:bg-accent/80 dark:hover:bg-muted rounded-md font-medium text-xs text-foreground/80 ps-2 pe-7 flex",
					closeButton:
						"absolute -inset-y-px -end-px p-0 rounded-e-md flex size-7 transition-colors outline-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring/70 text-foreground hover:text-foreground",
				},
			}}
			activeTagIndex={activeTagIndex}
			setActiveTagIndex={setActiveTagIndex}
		/>
	);
}

export function HitlEditPanelContent({
	title: initialTitle,
	content: initialContent,
	extraFields,
	onSave,
	onClose,
	showCloseButton = true,
}: {
	title: string;
	content: string;
	toolName: string;
	extraFields?: ExtraField[];
	onSave: (title: string, content: string, extraFieldValues?: Record<string, string>) => void;
	onClose?: () => void;
	showCloseButton?: boolean;
}) {
	const [editedTitle, setEditedTitle] = useState(initialTitle);
	const markdownRef = useRef(initialContent);
	const [isSaving, setIsSaving] = useState(false);
	const [extraFieldValues, setExtraFieldValues] = useState<Record<string, string>>(() => {
		if (!extraFields) return {};
		const initial: Record<string, string> = {};
		for (const field of extraFields) {
			initial[field.key] = field.value;
		}
		return initial;
	});

	const handleMarkdownChange = useCallback((md: string) => {
		markdownRef.current = md;
	}, []);

	const handleExtraFieldChange = useCallback((key: string, value: string) => {
		setExtraFieldValues((prev) => ({ ...prev, [key]: value }));
	}, []);

	const handleSave = useCallback(() => {
		if (!editedTitle.trim()) return;
		setIsSaving(true);
		const extras = extraFields && extraFields.length > 0 ? extraFieldValues : undefined;
		onSave(editedTitle, markdownRef.current, extras);
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
				<div className="flex flex-col gap-3 px-4 py-3 border-b">
					{extraFields.map((field) => (
						<div key={field.key} className="flex flex-col gap-1.5">
							<Label htmlFor={`extra-field-${field.key}`} className="text-xs font-medium text-muted-foreground">
								{field.label}
							</Label>
							{field.type === "emails" ? (
								<EmailsTagField
									id={`extra-field-${field.key}`}
									value={extraFieldValues[field.key] ?? ""}
									onChange={(v) => handleExtraFieldChange(field.key, v)}
									placeholder={`Add ${field.label.toLowerCase()}`}
								/>
							) : field.type === "textarea" ? (
								<Textarea
									id={`extra-field-${field.key}`}
									value={extraFieldValues[field.key] ?? ""}
									onChange={(e) => handleExtraFieldChange(field.key, e.target.value)}
									className="text-sm min-h-[60px]"
								/>
							) : (
								<Input
									id={`extra-field-${field.key}`}
									type={field.type}
									value={extraFieldValues[field.key] ?? ""}
									onChange={(e) => handleExtraFieldChange(field.key, e.target.value)}
									className="text-sm"
								/>
							)}
						</div>
					))}
				</div>
			)}

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
