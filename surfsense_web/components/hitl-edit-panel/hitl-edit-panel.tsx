"use client";

import { format } from "date-fns";
import { TagInput, type Tag as TagType } from "emblor";
import { useAtomValue, useSetAtom } from "jotai";
import { CalendarIcon, XIcon } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ExtraField } from "@/atoms/chat/hitl-edit-panel.atom";
import { closeHitlEditPanelAtom, hitlEditPanelAtom } from "@/atoms/chat/hitl-edit-panel.atom";
import { PlateEditor } from "@/components/editor/plate-editor";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
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
	const onChangeRef = useRef(onChange);
	onChangeRef.current = onChange;

	useEffect(() => {
		if (isInitialMount.current) {
			isInitialMount.current = false;
			return;
		}
		onChangeRef.current(tagsToEmailString(tags));
	}, [tags]);

	const handleSetTags = useCallback((newTags: TagType[] | ((prev: TagType[]) => TagType[])) => {
		setTags((prev) => (typeof newTags === "function" ? newTags(prev) : newTags));
	}, []);

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

function parseDateTimeValue(value: string): { date: Date | undefined; time: string } {
	if (!value) return { date: undefined, time: "09:00" };
	try {
		const d = new Date(value);
		if (Number.isNaN(d.getTime())) return { date: undefined, time: "09:00" };
		return {
			date: d,
			time: format(d, "HH:mm"),
		};
	} catch {
		return { date: undefined, time: "09:00" };
	}
}

function buildLocalDateTimeString(date: Date | undefined, time: string): string {
	if (!date) return "";
	const [hours, minutes] = time.split(":").map(Number);
	const combined = new Date(date);
	combined.setHours(hours ?? 9, minutes ?? 0, 0, 0);
	const y = combined.getFullYear();
	const m = String(combined.getMonth() + 1).padStart(2, "0");
	const d = String(combined.getDate()).padStart(2, "0");
	const h = String(combined.getHours()).padStart(2, "0");
	const min = String(combined.getMinutes()).padStart(2, "0");
	return `${y}-${m}-${d}T${h}:${min}:00`;
}

function DateTimePickerField({
	id,
	value,
	onChange,
}: {
	id: string;
	value: string;
	onChange: (value: string) => void;
}) {
	const parsed = useMemo(() => parseDateTimeValue(value), [value]);
	const [selectedDate, setSelectedDate] = useState<Date | undefined>(parsed.date);
	const [time, setTime] = useState(parsed.time);
	const [open, setOpen] = useState(false);

	const handleDateSelect = useCallback(
		(day: Date | undefined) => {
			setSelectedDate(day);
			onChange(buildLocalDateTimeString(day, time));
			setOpen(false);
		},
		[time, onChange]
	);

	const handleTimeChange = useCallback(
		(e: React.ChangeEvent<HTMLInputElement>) => {
			const newTime = e.target.value;
			setTime(newTime);
			onChange(buildLocalDateTimeString(selectedDate, newTime));
		},
		[selectedDate, onChange]
	);

	const displayLabel = selectedDate
		? `${format(selectedDate, "MMM d, yyyy")} at ${time}`
		: "Pick date & time";

	return (
		<div className="flex gap-2">
			<Popover open={open} onOpenChange={setOpen}>
				<PopoverTrigger asChild>
					<button
						id={id}
						type="button"
						className="flex-1 flex items-center gap-2 h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-[color,box-shadow] outline-none focus-visible:border-ring"
					>
						<CalendarIcon className="size-3.5 text-muted-foreground shrink-0" />
						<span className={selectedDate ? "text-foreground" : "text-muted-foreground"}>
							{displayLabel}
						</span>
					</button>
				</PopoverTrigger>
				<PopoverContent className="w-auto p-0" align="start">
					<Calendar
						mode="single"
						selected={selectedDate}
						onSelect={handleDateSelect}
						defaultMonth={selectedDate}
					/>
				</PopoverContent>
			</Popover>
			<Input
				type="time"
				value={time}
				onChange={handleTimeChange}
				className="w-[120px] text-sm shrink-0 appearance-none [&::-webkit-calendar-picker-indicator]:hidden [&::-webkit-calendar-picker-indicator]:appearance-none"
			/>
		</div>
	);
}

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
				<div className="flex flex-col gap-3 px-4 py-3 border-b">
					{extraFields.map((field) => (
						<div key={field.key} className="flex flex-col gap-1.5">
							<Label
								htmlFor={`extra-field-${field.key}`}
								className="text-xs font-medium text-muted-foreground"
							>
								{field.label}
							</Label>
							{field.type === "emails" ? (
								<EmailsTagField
									id={`extra-field-${field.key}`}
									value={extraFieldValues[field.key] ?? ""}
									onChange={(v) => handleExtraFieldChange(field.key, v)}
									placeholder={`Add ${field.label.toLowerCase()}`}
								/>
							) : field.type === "datetime-local" ? (
								<DateTimePickerField
									id={`extra-field-${field.key}`}
									value={extraFieldValues[field.key] ?? ""}
									onChange={(v) => handleExtraFieldChange(field.key, v)}
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
				className="h-[95vh] max-h-[95vh] z-80 bg-sidebar overflow-hidden"
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
