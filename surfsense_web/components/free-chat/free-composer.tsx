"use client";

import { ComposerPrimitive, useAui, useAuiState } from "@assistant-ui/react";
import { ArrowUpIcon, Globe, Paperclip, SquareIcon } from "lucide-react";
import { type FC, useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAnonymousMode } from "@/contexts/anonymous-mode";
import { useLoginGate } from "@/contexts/login-gate";
import { anonymousChatApiService } from "@/lib/apis/anonymous-chat-api.service";
import { cn } from "@/lib/utils";

const ANON_ALLOWED_EXTENSIONS = new Set([
	".md",
	".markdown",
	".txt",
	".text",
	".json",
	".jsonl",
	".yaml",
	".yml",
	".toml",
	".ini",
	".cfg",
	".conf",
	".xml",
	".css",
	".scss",
	".py",
	".js",
	".jsx",
	".ts",
	".tsx",
	".java",
	".kt",
	".go",
	".rs",
	".rb",
	".php",
	".c",
	".h",
	".cpp",
	".hpp",
	".cs",
	".swift",
	".sh",
	".sql",
	".log",
	".rst",
	".tex",
	".vue",
	".svelte",
	".astro",
	".tf",
	".proto",
	".csv",
	".tsv",
	".html",
	".htm",
	".xhtml",
]);

const ACCEPT_EXTENSIONS = Array.from(ANON_ALLOWED_EXTENSIONS).join(",");

export const FreeComposer: FC = () => {
	const aui = useAui();
	const isRunning = useAuiState(({ thread }) => thread.isRunning);
	const isEmpty = useAuiState(({ thread }) => thread.isEmpty);
	const { gate } = useLoginGate();
	const anonMode = useAnonymousMode();
	const [text, setText] = useState("");
	const [webSearchEnabled, setWebSearchEnabled] = useState(true);
	const fileInputRef = useRef<HTMLInputElement>(null);

	const hasUploadedDoc = anonMode.isAnonymous && anonMode.uploadedDoc !== null;

	const handleTextChange = useCallback(
		(e: React.ChangeEvent<HTMLTextAreaElement>) => {
			setText(e.target.value);
			aui.composer().setText(e.target.value);
		},
		[aui]
	);

	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent<HTMLTextAreaElement>) => {
			if (e.key === "/" && text === "") {
				e.preventDefault();
				gate("use saved prompts");
				return;
			}
			if (e.key === "@") {
				e.preventDefault();
				gate("mention documents");
				return;
			}
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				if (text.trim()) {
					aui.composer().send();
					setText("");
				}
			}
		},
		[text, aui, gate]
	);

	const handleUploadClick = useCallback(() => {
		if (hasUploadedDoc) {
			gate("upload more documents");
			return;
		}
		fileInputRef.current?.click();
	}, [hasUploadedDoc, gate]);

	const handleFileChange = useCallback(
		async (e: React.ChangeEvent<HTMLInputElement>) => {
			const file = e.target.files?.[0];
			if (!file) return;
			e.target.value = "";

			const ext = `.${file.name.split(".").pop()?.toLowerCase()}`;
			if (!ANON_ALLOWED_EXTENSIONS.has(ext)) {
				gate("upload PDFs, Word documents, images, and more");
				return;
			}

			try {
				const result = await anonymousChatApiService.uploadDocument(file);
				if (!result.ok) {
					if (result.reason === "quota_exceeded") gate("upload more documents");
					return;
				}
				const data = result.data;
				if (anonMode.isAnonymous) {
					anonMode.setUploadedDoc({
						filename: data.filename,
						sizeBytes: data.size_bytes,
					});
				}
				toast.success(`Uploaded "${data.filename}"`);
			} catch (err) {
				console.error("Upload failed:", err);
				toast.error(err instanceof Error ? err.message : "Upload failed");
			}
		},
		[gate, anonMode]
	);

	return (
		<ComposerPrimitive.Root className="aui-composer-root relative mx-auto flex w-full max-w-(--thread-max-width) flex-col rounded-2xl border border-border/40 bg-background shadow-xs transition-shadow focus-within:shadow-md dark:bg-neutral-900">
			{hasUploadedDoc && anonMode.isAnonymous && (
				<div className="flex items-center gap-2 px-3 pt-2">
					<Paperclip className="size-3.5 text-muted-foreground" />
					<span className="text-xs text-muted-foreground truncate">
						{anonMode.uploadedDoc?.filename}
					</span>
					<span className="text-xs text-muted-foreground/60">(1/1)</span>
				</div>
			)}

			<textarea
				placeholder="Ask anything..."
				value={text}
				onChange={handleTextChange}
				onKeyDown={handleKeyDown}
				rows={1}
				className={cn(
					"w-full resize-none bg-transparent px-4 pt-3 pb-0 text-sm",
					"placeholder:text-muted-foreground focus:outline-none",
					"min-h-[44px] max-h-[200px]"
				)}
				style={{ fieldSizing: "content" } as React.CSSProperties}
			/>

			<div className="flex items-center justify-between gap-2 px-3 pb-2 pt-1">
				<div className="flex items-center gap-2">
					<input
						ref={fileInputRef}
						type="file"
						accept={ACCEPT_EXTENSIONS}
						className="hidden"
						onChange={handleFileChange}
					/>
					<Tooltip>
						<TooltipTrigger asChild>
							<button
								type="button"
								onClick={handleUploadClick}
								className={cn(
									"flex items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-colors",
									"text-muted-foreground hover:text-foreground hover:bg-accent/50",
									hasUploadedDoc && "text-primary"
								)}
							>
								<Paperclip className="size-3.5" />
								{hasUploadedDoc ? "1/1" : "Upload"}
							</button>
						</TooltipTrigger>
						<TooltipContent>
							{hasUploadedDoc
								? "Document limit reached. Create an account for more."
								: "Upload a document (text files only)"}
						</TooltipContent>
					</Tooltip>

					<div className="h-4 w-px bg-border/60" />

					<Tooltip>
						<TooltipTrigger asChild>
							<label
								htmlFor="free-web-search-toggle"
								className="flex items-center gap-1.5 cursor-pointer select-none rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors"
							>
								<Globe className="size-3.5" />
								<span className="hidden sm:inline">Web</span>
								<Switch
									id="free-web-search-toggle"
									checked={webSearchEnabled}
									onCheckedChange={setWebSearchEnabled}
									className="scale-75"
								/>
							</label>
						</TooltipTrigger>
						<TooltipContent>Toggle web search</TooltipContent>
					</Tooltip>
				</div>

				<div className="flex items-center gap-1">
					{!isRunning ? (
						<ComposerPrimitive.Send asChild>
							<TooltipIconButton tooltip="Send" variant="default" className="size-8 rounded-full">
								<ArrowUpIcon />
							</TooltipIconButton>
						</ComposerPrimitive.Send>
					) : (
						<ComposerPrimitive.Cancel asChild>
							<TooltipIconButton
								tooltip="Cancel"
								variant="destructive"
								className="size-8 rounded-full"
							>
								<SquareIcon className="size-3.5" />
							</TooltipIconButton>
						</ComposerPrimitive.Cancel>
					)}
				</div>
			</div>
		</ComposerPrimitive.Root>
	);
};
