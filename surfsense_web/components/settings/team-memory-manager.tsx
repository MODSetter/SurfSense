"use client";

import { ChevronDown, ClipboardCopy, Download, Info } from "lucide-react";
import { toast } from "sonner";
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
import { getMemoryLimitState, useTeamMemory } from "@/hooks/use-memory";

interface TeamMemoryManagerProps {
	searchSpaceId: number;
}

export function TeamMemoryManager({ searchSpaceId }: TeamMemoryManagerProps) {
	const { memory, displayMemory, limits, loading, saving, reset } = useTeamMemory(searchSpaceId);

	const handleClear = async () => {
		try {
			await reset();
			toast.success("Team memory cleared");
		} catch {
			toast.error("Failed to clear team memory");
		}
	};

	const handleDownload = () => {
		if (!memory) return;
		try {
			const blob = new Blob([memory], { type: "text/markdown;charset=utf-8" });
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = "team-memory.md";
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} catch {
			toast.error("Failed to download team memory");
		}
	};

	const handleCopyMarkdown = async () => {
		if (!memory) return;
		try {
			await navigator.clipboard.writeText(memory);
			toast.success("Copied to clipboard");
		} catch {
			toast.error("Failed to copy team memory");
		}
	};

	const charCount = memory.length;
	const limitState = getMemoryLimitState(charCount, limits);

	const getCounterColor = () => {
		if (limitState.level === "error") return "text-red-500";
		if (limitState.level === "warning") return "text-orange-500";
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
				<h3 className="text-base font-medium text-foreground">
					What does SurfSense remember about your team?
				</h3>
				<p className="mt-2 max-w-sm text-sm text-muted-foreground">
					Nothing yet. SurfSense picks up on team decisions and conventions as your team chats.
				</p>
			</div>
		);
	}

	return (
		<div className="space-y-4">
			<Alert>
				<Info />
				<AlertDescription>
					<p>
						SurfSense uses this shared memory to provide team-wide context across all conversations
						in this search space.
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
			</div>

			<div className="flex items-center justify-between gap-2">
				<span className={`text-xs shrink-0 ${getCounterColor()}`}>{limitState.label}</span>
				<div className="flex items-center gap-1.5 sm:gap-2">
					<Button
						type="button"
						variant="destructive"
						size="sm"
						className="text-xs sm:text-sm"
						onClick={handleClear}
						disabled={saving || !memory}
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
