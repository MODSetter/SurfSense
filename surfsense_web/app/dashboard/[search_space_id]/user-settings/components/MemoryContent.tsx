"use client";

import { useAtomValue } from "jotai";
import { ArrowUp, ChevronDown, ClipboardCopy, Download, Info, Pen } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { PlateEditor } from "@/components/editor/plate-editor";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";

import { baseApiService } from "@/lib/apis/base-api.service";

const MEMORY_HARD_LIMIT = 25_000;

const MemoryReadSchema = z.object({
	memory_md: z.string(),
});

export function MemoryContent() {
	const activeSearchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const [memory, setMemory] = useState("");
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [editQuery, setEditQuery] = useState("");
	const [editing, setEditing] = useState(false);
	const [showInput, setShowInput] = useState(false);
	const textareaRef = useRef<HTMLInputElement>(null);

	const fetchMemory = useCallback(async () => {
		try {
			setLoading(true);
			const data = await baseApiService.get("/api/v1/users/me/memory", MemoryReadSchema);
			setMemory(data.memory_md);
		} catch {
			toast.error("Failed to load memory");
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchMemory();
	}, [fetchMemory]);

	const handleClear = async () => {
		try {
			setSaving(true);
			const data = await baseApiService.put("/api/v1/users/me/memory", MemoryReadSchema, {
				body: { memory_md: "" },
			});
			setMemory(data.memory_md);
			toast.success("Memory cleared");
		} catch {
			toast.error("Failed to clear memory");
		} finally {
			setSaving(false);
		}
	};

	const handleEdit = async () => {
		const query = editQuery.trim();
		if (!query) return;

		try {
			setEditing(true);
			const data = await baseApiService.post("/api/v1/users/me/memory/edit", MemoryReadSchema, {
				body: { query, search_space_id: Number(activeSearchSpaceId) },
			});
			setMemory(data.memory_md);
			setEditQuery("");
			setShowInput(false);
			toast.success("Memory updated");
		} catch {
			toast.error("Failed to edit memory");
		} finally {
			setEditing(false);
		}
	};

	const openInput = () => {
		setShowInput(true);
		requestAnimationFrame(() => textareaRef.current?.focus());
	};

	const handleDownload = () => {
		if (!memory) return;
		try {
			const blob = new Blob([memory], { type: "text/markdown;charset=utf-8" });
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = "personal-memory.md";
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} catch {
			toast.error("Failed to download memory");
		}
	};

	const handleCopyMarkdown = async () => {
		if (!memory) return;
		try {
			await navigator.clipboard.writeText(memory);
			toast.success("Copied to clipboard");
		} catch {
			toast.error("Failed to copy memory");
		}
	};

	const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			handleEdit();
		} else if (e.key === "Escape") {
			setShowInput(false);
			setEditQuery("");
		}
	};

	const displayMemory = memory.replace(/\(\d{4}-\d{2}-\d{2}\)\s*\[(fact|pref|instr)\]\s*/g, "");
	const charCount = memory.length;

	const getCounterColor = () => {
		if (charCount > MEMORY_HARD_LIMIT) return "text-red-500";
		if (charCount > 15_000) return "text-orange-500";
		if (charCount > 10_000) return "text-yellow-500";
		return "text-muted-foreground";
	};

	if (loading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner size="md" className="text-muted-foreground" />
			</div>
		);
	}

	if (!memory) {
		return (
			<div className="flex flex-col items-center justify-center py-16 text-center">
				<h3 className="text-base font-medium text-foreground">What does SurfSense remember?</h3>
				<p className="mt-2 max-w-sm text-sm text-muted-foreground">
					Nothing yet. SurfSense picks up on your preferences and context as you chat.
				</p>
			</div>
		);
	}

	return (
		<div className="space-y-4">
			<Alert className="bg-muted/50 py-3 md:py-4">
				<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
				<AlertDescription className="text-xs md:text-sm">
					<p>
						SurfSense uses this personal memory to personalize your responses across all
						conversations. Use the input below to add, update, or remove memory entries.
					</p>
				</AlertDescription>
			</Alert>

			<div className="relative h-[380px] rounded-lg border bg-background">
				<div className="h-full overflow-y-auto scrollbar-thin">
					<PlateEditor
						markdown={displayMemory}
						readOnly
						preset="readonly"
						variant="default"
						editorVariant="none"
						className="px-5 py-4 text-sm min-h-full"
					/>
				</div>

				{showInput ? (
					<div className="absolute bottom-3 inset-x-3 z-10">
						<div className="relative flex items-center gap-2 rounded-full border bg-muted/60 backdrop-blur-sm px-4 py-2 shadow-sm">
							<input
								ref={textareaRef}
								type="text"
								value={editQuery}
								onChange={(e) => setEditQuery(e.target.value)}
								onKeyDown={handleKeyDown}
								placeholder="Tell SurfSense what to remember or forget"
								disabled={editing}
								className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/70"
							/>
							<Button
								type="button"
								size="icon"
								variant="ghost"
								onClick={handleEdit}
								disabled={editing || !editQuery.trim()}
								className="h-9 w-9 shrink-0 rounded-full"
							>
								{editing ? <Spinner size="sm" /> : <ArrowUp className="!h-5 !w-5" />}
							</Button>
						</div>
					</div>
				) : (
					<Button
						type="button"
						size="icon"
						variant="secondary"
						onClick={openInput}
						className="absolute bottom-3 right-3 z-10 h-[54px] w-[54px] rounded-full border bg-muted/60 backdrop-blur-sm shadow-sm"
					>
						<Pen className="!h-5 !w-5" />
					</Button>
				)}
			</div>

			<div className="flex items-center justify-between gap-2">
				<span className={`text-xs shrink-0 ${getCounterColor()}`}>
					{charCount.toLocaleString()} / {MEMORY_HARD_LIMIT.toLocaleString()}
					<span className="hidden sm:inline"> characters</span>
					<span className="sm:hidden"> chars</span>
					{charCount > 15_000 && charCount <= MEMORY_HARD_LIMIT && " - Approaching limit"}
					{charCount > MEMORY_HARD_LIMIT && " - Exceeds limit"}
				</span>
				<div className="flex items-center gap-1.5 sm:gap-2">
					<Button
						type="button"
						variant="destructive"
						size="sm"
						className="text-xs sm:text-sm"
						onClick={handleClear}
						disabled={saving || editing || !memory}
					>
						<span className="hidden sm:inline">Reset Memory</span>
						<span className="sm:hidden">Reset</span>
					</Button>
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<Button type="button" variant="secondary" size="sm" disabled={!memory}>
								Export
								<ChevronDown className="h-3 w-3 opacity-60" />
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end">
							<DropdownMenuItem onClick={handleCopyMarkdown}>
								<ClipboardCopy className="h-4 w-4 mr-2" />
								Copy as Markdown
							</DropdownMenuItem>
							<DropdownMenuItem onClick={handleDownload}>
								<Download className="h-4 w-4 mr-2" />
								Download as Markdown
							</DropdownMenuItem>
						</DropdownMenuContent>
					</DropdownMenu>
				</div>
			</div>
		</div>
	);
}
