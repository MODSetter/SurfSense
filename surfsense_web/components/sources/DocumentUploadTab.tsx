"use client";

import { useAtom } from "jotai";
import { ChevronDown, Dot, File as FileIcon, FolderOpen, Upload, X } from "lucide-react";

import { useTranslations } from "next-intl";
import { type ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { uploadDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { useElectronAPI } from "@/hooks/use-platform";
import {
	trackDocumentUploadFailure,
	trackDocumentUploadStarted,
	trackDocumentUploadSuccess,
} from "@/lib/posthog/events";
import {
	getAcceptedFileTypes,
	getSupportedExtensions,
	getSupportedExtensionsSet,
} from "@/lib/supported-extensions";

interface DocumentUploadTabProps {
	searchSpaceId: string;
	onSuccess?: () => void;
	onAccordionStateChange?: (isExpanded: boolean) => void;
}

interface FileWithId {
	id: string;
	file: File;
}

const MAX_FILE_SIZE_MB = 500;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

const toggleRowClass =
	"flex items-center justify-between rounded-lg bg-slate-400/5 dark:bg-white/5 p-3";

export function DocumentUploadTab({
	searchSpaceId,
	onSuccess,
	onAccordionStateChange,
}: DocumentUploadTabProps) {
	const t = useTranslations("upload_documents");
	const [files, setFiles] = useState<FileWithId[]>([]);
	const [uploadProgress, setUploadProgress] = useState(0);
	const [accordionValue, setAccordionValue] = useState<string>("");
	const [shouldSummarize, setShouldSummarize] = useState(false);
	const [uploadDocumentMutation] = useAtom(uploadDocumentMutationAtom);
	const { mutate: uploadDocuments, isPending: isUploading } = uploadDocumentMutation;
	const fileInputRef = useRef<HTMLInputElement>(null);
	const folderInputRef = useRef<HTMLInputElement>(null);
	const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

	useEffect(() => {
		return () => {
			if (progressIntervalRef.current) {
				clearInterval(progressIntervalRef.current);
			}
		};
	}, []);

	const electronAPI = useElectronAPI();
	const isElectron = !!electronAPI?.browseFiles;

	const acceptedFileTypes = useMemo(() => getAcceptedFileTypes(), []);
	const supportedExtensions = useMemo(
		() => getSupportedExtensions(acceptedFileTypes),
		[acceptedFileTypes]
	);
	const supportedExtensionsSet = useMemo(
		() => getSupportedExtensionsSet(acceptedFileTypes),
		[acceptedFileTypes]
	);

	const addFiles = useCallback(
		(incoming: File[]) => {
			const oversized = incoming.filter((f) => f.size > MAX_FILE_SIZE_BYTES);
			if (oversized.length > 0) {
				toast.error(t("file_too_large"), {
					description: t("file_too_large_desc", {
						name: oversized[0].name,
						maxMB: MAX_FILE_SIZE_MB,
					}),
				});
			}
			const valid = incoming.filter((f) => f.size <= MAX_FILE_SIZE_BYTES);
			if (valid.length === 0) return;

			setFiles((prev) => {
				const newEntries = valid.map((f) => ({
					id: crypto.randomUUID?.() ?? `file-${Date.now()}-${Math.random().toString(36)}`,
					file: f,
				}));
				return [...prev, ...newEntries];
			});
		},
		[t]
	);

	const onDrop = useCallback(
		(acceptedFiles: File[]) => {
			addFiles(acceptedFiles);
		},
		[addFiles]
	);

	const { getRootProps, getInputProps, isDragActive } = useDropzone({
		onDrop,
		accept: acceptedFileTypes,
		maxSize: MAX_FILE_SIZE_BYTES,
		noClick: isElectron,
	});

	const handleFileInputClick = useCallback((e: React.MouseEvent<HTMLInputElement>) => {
		e.stopPropagation();
	}, []);

	const handleBrowseFiles = useCallback(async () => {
		if (!electronAPI?.browseFiles) return;

		const paths = await electronAPI.browseFiles();
		if (!paths || paths.length === 0) return;

		const fileDataList = await electronAPI.readLocalFiles(paths);
		const filtered = fileDataList.filter(
			(fd: { name: string; data: ArrayBuffer; mimeType: string }) => {
				const ext = fd.name.includes(".") ? `.${fd.name.split(".").pop()?.toLowerCase()}` : "";
				return ext !== "" && supportedExtensionsSet.has(ext);
			}
		);

		if (filtered.length === 0) {
			toast.error(t("no_supported_files_in_folder"));
			return;
		}

		const newFiles: FileWithId[] = filtered.map(
			(fd: { name: string; data: ArrayBuffer; mimeType: string }) => ({
				id: crypto.randomUUID?.() ?? `file-${Date.now()}-${Math.random().toString(36)}`,
				file: new File([fd.data], fd.name, { type: fd.mimeType }),
			})
		);
		setFiles((prev) => [...prev, ...newFiles]);
	}, [electronAPI, supportedExtensionsSet, t]);

	const handleFolderChange = useCallback(
		(e: ChangeEvent<HTMLInputElement>) => {
			const fileList = e.target.files;
			if (!fileList || fileList.length === 0) return;

			const folderFiles = Array.from(fileList).filter((f) => {
				const ext = f.name.includes(".") ? `.${f.name.split(".").pop()?.toLowerCase()}` : "";
				return ext !== "" && supportedExtensionsSet.has(ext);
			});

			if (folderFiles.length === 0) {
				toast.error(t("no_supported_files_in_folder"));
				e.target.value = "";
				return;
			}

			addFiles(folderFiles);
			e.target.value = "";
		},
		[addFiles, supportedExtensionsSet, t]
	);

	const formatFileSize = (bytes: number) => {
		if (bytes === 0) return "0 Bytes";
		const k = 1024;
		const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return `${parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`;
	};

	const totalFileSize = files.reduce((total, entry) => total + entry.file.size, 0);

	const hasContent = files.length > 0;

	const handleAccordionChange = useCallback(
		(value: string) => {
			setAccordionValue(value);
			onAccordionStateChange?.(value === "supported-file-types");
		},
		[onAccordionStateChange]
	);

	const handleUpload = async () => {
		setUploadProgress(0);
		trackDocumentUploadStarted(Number(searchSpaceId), files.length, totalFileSize);

		progressIntervalRef.current = setInterval(() => {
			setUploadProgress((prev) => (prev >= 90 ? prev : prev + Math.random() * 10));
		}, 200);

		const rawFiles = files.map((entry) => entry.file);
		uploadDocuments(
			{
				files: rawFiles,
				search_space_id: Number(searchSpaceId),
				should_summarize: shouldSummarize,
			},
			{
				onSuccess: () => {
					if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
					setUploadProgress(100);
					trackDocumentUploadSuccess(Number(searchSpaceId), files.length);
					toast(t("upload_initiated"), { description: t("upload_initiated_desc") });
					onSuccess?.();
				},
				onError: (error: unknown) => {
					if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
					setUploadProgress(0);
					const message = error instanceof Error ? error.message : "Upload failed";
					trackDocumentUploadFailure(Number(searchSpaceId), message);
					toast(t("upload_error"), {
						description: `${t("upload_error_desc")}: ${message}`,
					});
				},
			}
		);
	};

	const renderBrowseButton = (options?: { compact?: boolean; fullWidth?: boolean }) => {
		const { compact, fullWidth } = options ?? {};
		const sizeClass = compact ? "h-7" : "h-8";
		const widthClass = fullWidth ? "w-full" : "";

		if (isElectron) {
			return (
				<DropdownMenu>
					<DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
						<Button
							variant="ghost"
							size="sm"
							className={`text-xs gap-1 bg-neutral-700/50 hover:bg-neutral-600/50 ${sizeClass} ${widthClass}`}
						>
							Browse
							<ChevronDown className="h-3 w-3 opacity-60" />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent
						align="center"
						className="dark:bg-neutral-800"
						onClick={(e) => e.stopPropagation()}
					>
						<DropdownMenuItem onClick={handleBrowseFiles}>
							<FileIcon className="h-4 w-4 mr-2" />
							Files
						</DropdownMenuItem>
						<DropdownMenuItem onClick={() => folderInputRef.current?.click()}>
							<FolderOpen className="h-4 w-4 mr-2" />
							Folder
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			);
		}

		return (
			<DropdownMenu>
				<DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
					<Button
						variant="ghost"
						size="sm"
						className={`text-xs gap-1 bg-neutral-700/50 hover:bg-neutral-600/50 ${sizeClass} ${widthClass}`}
					>
						Browse
						<ChevronDown className="h-3 w-3 opacity-60" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent
					align="center"
					className="dark:bg-neutral-800"
					onClick={(e) => e.stopPropagation()}
				>
					<DropdownMenuItem onClick={() => fileInputRef.current?.click()}>
						<FileIcon className="h-4 w-4 mr-2" />
						{t("browse_files")}
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => folderInputRef.current?.click()}>
						<FolderOpen className="h-4 w-4 mr-2" />
						{t("browse_folder")}
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		);
	};

	return (
		<div className="space-y-2 w-full mx-auto">
			{/* Hidden file input */}
			<input
				{...getInputProps()}
				ref={fileInputRef}
				className="hidden"
				onClick={handleFileInputClick}
			/>

			{/* Hidden folder input for web folder browsing */}
			<input
				ref={folderInputRef}
				type="file"
				className="hidden"
				onChange={handleFolderChange}
				multiple
				{...({ webkitdirectory: "", directory: "" } as React.InputHTMLAttributes<HTMLInputElement>)}
			/>

			{/* MOBILE DROP ZONE */}
			<div className="sm:hidden">
				{hasContent ? (
					isElectron ? (
						<div className="w-full">{renderBrowseButton({ compact: true, fullWidth: true })}</div>
					) : (
						<button
							type="button"
							className="w-full text-xs h-8 flex items-center justify-center gap-1.5 rounded-md border border-dashed border-muted-foreground/30 text-muted-foreground hover:text-foreground hover:border-foreground/50 transition-colors"
							onClick={() => fileInputRef.current?.click()}
						>
							Add more files
						</button>
					)
				) : (
				<div
					role="button"
					tabIndex={0}
					className="flex flex-col items-center gap-4 py-12 px-4 cursor-pointer w-full bg-transparent border-none"
					onClick={() => {
						if (!isElectron) fileInputRef.current?.click();
					}}
					onKeyDown={(e) => {
						if (e.key === "Enter" || e.key === " ") {
							e.preventDefault();
							if (!isElectron) fileInputRef.current?.click();
						}
					}}
				>
					<Upload className="h-10 w-10 text-muted-foreground" />
					<div className="text-center space-y-1.5">
						<p className="text-base font-medium">
							{isElectron ? "Select files or folder" : "Tap to select files or folder"}
						</p>
						<p className="text-sm text-muted-foreground">{t("file_size_limit")}</p>
					</div>
					<div
						className="w-full mt-1"
						onClick={(e) => e.stopPropagation()}
						onKeyDown={(e) => e.stopPropagation()}
						role="group"
					>
						{renderBrowseButton({ fullWidth: true })}
					</div>
				</div>
				)}
			</div>

			{/* DESKTOP DROP ZONE */}
			<div
				{...getRootProps()}
				className={`hidden sm:block border-2 border-dashed rounded-lg transition-colors border-muted-foreground/30 hover:border-foreground/70 cursor-pointer ${hasContent ? "p-3" : "py-20 px-4"}`}
			>
				{hasContent ? (
					<div className="flex items-center gap-3">
						<Upload className="h-4 w-4 text-muted-foreground shrink-0" />
						<span className="text-xs text-muted-foreground flex-1 truncate">
							{isDragActive ? t("drop_files") : t("drag_drop_more")}
						</span>
						{renderBrowseButton({ compact: true })}
					</div>
				) : (
					<div className="relative">
						{isDragActive && (
							<div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
								<Upload className="h-8 w-8 text-primary" />
								<p className="text-sm font-medium text-primary">{t("drop_files")}</p>
							</div>
						)}
						<div className={`flex flex-col items-center gap-2 ${isDragActive ? "invisible" : ""}`}>
							<Upload className="h-8 w-8 text-muted-foreground" />
							<p className="text-sm font-medium">{t("drag_drop")}</p>
							<p className="text-xs text-muted-foreground">{t("file_size_limit")}</p>
							<div className="mt-1">{renderBrowseButton()}</div>
						</div>
					</div>
				)}
			</div>

			{/* FILES SELECTED */}
			{files.length > 0 && (
				<div className="rounded-lg border border-border p-3 space-y-2">
					<div className="flex items-center justify-between">
						<p className="text-sm font-medium">
							{t("selected_files", { count: files.length })}
							<Dot className="inline h-4 w-4" />
							{formatFileSize(totalFileSize)}
						</p>
						<Button
							variant="ghost"
							size="sm"
							className="h-7 text-xs text-muted-foreground hover:text-foreground"
							onClick={() => setFiles([])}
							disabled={isUploading}
						>
							{t("clear_all")}
						</Button>
					</div>

					<div className="max-h-[160px] sm:max-h-[200px] overflow-y-auto -mx-1">
						{files.map((entry) => (
							<div
								key={entry.id}
								className="flex items-center gap-2 py-1.5 px-2 rounded-md hover:bg-slate-400/5 dark:hover:bg-white/5 group"
							>
								<span className="text-[10px] font-medium uppercase leading-none bg-muted px-1.5 py-0.5 rounded text-muted-foreground shrink-0">
									{entry.file.name.split(".").pop() || "?"}
								</span>
								<span className="text-sm truncate flex-1 min-w-0">{entry.file.name}</span>
								<span className="text-xs text-muted-foreground shrink-0">
									{formatFileSize(entry.file.size)}
								</span>
								<Button
									variant="ghost"
									size="icon"
									className="h-6 w-6 shrink-0"
									onClick={() => setFiles((prev) => prev.filter((e) => e.id !== entry.id))}
									disabled={isUploading}
								>
									<X className="h-3 w-3" />
								</Button>
							</div>
						))}
					</div>

					{isUploading && (
						<div className="space-y-1">
							<div className="flex items-center justify-between text-xs">
								<span>{t("uploading_files")}</span>
								<span>{Math.round(uploadProgress)}%</span>
							</div>
							<Progress value={uploadProgress} className="h-1.5" />
						</div>
					)}

					<div className={toggleRowClass}>
						<div className="space-y-0.5">
							<p className="font-medium text-sm">Enable AI Summary</p>
							<p className="text-xs text-muted-foreground">
								Improves search quality but adds latency
							</p>
						</div>
						<Switch checked={shouldSummarize} onCheckedChange={setShouldSummarize} />
					</div>

					<Button
						className="w-full"
						onClick={handleUpload}
						disabled={isUploading || files.length === 0}
					>
						{isUploading ? (
							<span className="flex items-center gap-2">
								<Spinner size="sm" />
								{t("uploading")}
							</span>
						) : (
							<span className="flex items-center gap-2">
								{t("upload_button", { count: files.length })}
							</span>
						)}
					</Button>
				</div>
			)}

			{/* SUPPORTED FORMATS */}
			<Accordion
				type="single"
				collapsible
				value={accordionValue}
				onValueChange={handleAccordionChange}
				className="w-full mt-5"
			>
				<AccordionItem value="supported-file-types" className="border border-border rounded-lg">
					<AccordionTrigger className="px-3 py-2.5 hover:no-underline !items-center [&>svg]:!translate-y-0">
						<span className="text-xs sm:text-sm text-muted-foreground font-normal">
							{t("supported_file_types")}
						</span>
					</AccordionTrigger>
					<AccordionContent className="px-3 pb-3">
						<div className="flex flex-wrap gap-1.5">
							{supportedExtensions.map((ext) => (
								<Badge
									key={ext}
									variant="secondary"
									className="rounded border-0 bg-neutral-200/80 dark:bg-neutral-700/60 text-muted-foreground text-[10px] px-2 py-0.5 font-normal"
								>
									{ext}
								</Badge>
							))}
						</div>
					</AccordionContent>
				</AccordionItem>
			</Accordion>
		</div>
	);
}
