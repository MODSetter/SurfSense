"use client";

import { useAtom } from "jotai";
import { ChevronDown, Dot, File as FileIcon, FolderOpen, Upload, X } from "lucide-react";

import { useTranslations } from "next-intl";
import { type ChangeEvent, useCallback, useMemo, useRef, useState } from "react";
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
import { documentsApiService } from "@/lib/apis/documents-api.service";
import {
	trackDocumentUploadFailure,
	trackDocumentUploadStarted,
	trackDocumentUploadSuccess,
} from "@/lib/posthog/events";

interface SelectedFolder {
	path: string;
	name: string;
}

interface DocumentUploadTabProps {
	searchSpaceId: string;
	onSuccess?: () => void;
	onAccordionStateChange?: (isExpanded: boolean) => void;
}

const audioFileTypes = {
	"audio/mpeg": [".mp3", ".mpeg", ".mpga"],
	"audio/mp4": [".mp4", ".m4a"],
	"audio/wav": [".wav"],
	"audio/webm": [".webm"],
	"text/markdown": [".md", ".markdown"],
	"text/plain": [".txt"],
};

const commonTypes = {
	"application/pdf": [".pdf"],
	"application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
	"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
	"application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
	"text/html": [".html", ".htm"],
	"text/csv": [".csv"],
	"text/tab-separated-values": [".tsv"],
	"image/jpeg": [".jpg", ".jpeg"],
	"image/png": [".png"],
	"image/bmp": [".bmp"],
	"image/webp": [".webp"],
	"image/tiff": [".tiff"],
};

const FILE_TYPE_CONFIG: Record<string, Record<string, string[]>> = {
	LLAMACLOUD: {
		...commonTypes,
		"application/msword": [".doc"],
		"application/vnd.ms-word.document.macroEnabled.12": [".docm"],
		"application/msword-template": [".dot"],
		"application/vnd.ms-word.template.macroEnabled.12": [".dotm"],
		"application/vnd.ms-powerpoint": [".ppt"],
		"application/vnd.ms-powerpoint.template.macroEnabled.12": [".pptm"],
		"application/vnd.ms-powerpoint.template": [".pot"],
		"application/vnd.openxmlformats-officedocument.presentationml.template": [".potx"],
		"application/vnd.ms-excel": [".xls"],
		"application/vnd.ms-excel.sheet.macroEnabled.12": [".xlsm"],
		"application/vnd.ms-excel.sheet.binary.macroEnabled.12": [".xlsb"],
		"application/vnd.ms-excel.workspace": [".xlw"],
		"application/rtf": [".rtf"],
		"application/xml": [".xml"],
		"application/epub+zip": [".epub"],
		"text/html": [".html", ".htm", ".web"],
		"image/gif": [".gif"],
		"image/svg+xml": [".svg"],
		...audioFileTypes,
	},
	DOCLING: {
		...commonTypes,
		"text/asciidoc": [".adoc", ".asciidoc"],
		"text/html": [".html", ".htm", ".xhtml"],
		"image/tiff": [".tiff", ".tif"],
		...audioFileTypes,
	},
	default: {
		...commonTypes,
		"application/msword": [".doc"],
		"message/rfc822": [".eml"],
		"application/epub+zip": [".epub"],
		"image/heic": [".heic"],
		"application/vnd.ms-outlook": [".msg"],
		"application/vnd.oasis.opendocument.text": [".odt"],
		"text/x-org": [".org"],
		"application/pkcs7-signature": [".p7s"],
		"application/vnd.ms-powerpoint": [".ppt"],
		"text/x-rst": [".rst"],
		"application/rtf": [".rtf"],
		"application/vnd.ms-excel": [".xls"],
		"application/xml": [".xml"],
		...audioFileTypes,
	},
};

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

	const [selectedFolder, setSelectedFolder] = useState<SelectedFolder | null>(null);
	const [watchFolder, setWatchFolder] = useState(true);
	const [folderSubmitting, setFolderSubmitting] = useState(false);
	const isElectron = typeof window !== "undefined" && !!window.electronAPI?.browseFiles;

	const acceptedFileTypes = useMemo(() => {
		const etlService = process.env.NEXT_PUBLIC_ETL_SERVICE;
		return FILE_TYPE_CONFIG[etlService || "default"] || FILE_TYPE_CONFIG.default;
	}, []);

	const supportedExtensions = useMemo(
		() => Array.from(new Set(Object.values(acceptedFileTypes).flat())).sort(),
		[acceptedFileTypes]
	);

	const supportedExtensionsSet = useMemo(
		() => new Set(supportedExtensions.map((ext) => ext.toLowerCase())),
		[supportedExtensions]
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
			setSelectedFolder(null);
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
		const api = window.electronAPI;
		if (!api?.browseFiles) return;

		const paths = await api.browseFiles();
		if (!paths || paths.length === 0) return;

		setSelectedFolder(null);
		const fileDataList = await api.readLocalFiles(paths);
		const newFiles: FileWithId[] = fileDataList.map((fd) => ({
			id: crypto.randomUUID?.() ?? `file-${Date.now()}-${Math.random().toString(36)}`,
			file: new File([fd.data], fd.name, { type: fd.mimeType }),
		}));
		setFiles((prev) => [...prev, ...newFiles]);
	}, []);

	const handleBrowseFolder = useCallback(async () => {
		const api = window.electronAPI;
		if (!api?.selectFolder) return;

		const folderPath = await api.selectFolder();
		if (!folderPath) return;

		const folderName = folderPath.split("/").pop() || folderPath.split("\\").pop() || folderPath;
		setFiles([]);
		setSelectedFolder({ path: folderPath, name: folderName });
		setWatchFolder(true);
	}, []);

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

	const hasContent = files.length > 0 || selectedFolder !== null;

	const handleAccordionChange = useCallback(
		(value: string) => {
			setAccordionValue(value);
			onAccordionStateChange?.(value === "supported-file-types");
		},
		[onAccordionStateChange]
	);

	const handleFolderSubmit = useCallback(async () => {
		if (!selectedFolder) return;
		const api = window.electronAPI;
		if (!api) return;

		setFolderSubmitting(true);
		try {
			const numericSpaceId = Number(searchSpaceId);
			const result = await documentsApiService.folderIndex(numericSpaceId, {
				folder_path: selectedFolder.path,
				folder_name: selectedFolder.name,
				search_space_id: numericSpaceId,
				enable_summary: shouldSummarize,
			});

			const rootFolderId = (result as { root_folder_id?: number })?.root_folder_id ?? null;

			if (watchFolder) {
				await api.addWatchedFolder({
					path: selectedFolder.path,
					name: selectedFolder.name,
					excludePatterns: [
						".git",
						"node_modules",
						"__pycache__",
						".DS_Store",
						".obsidian",
						".trash",
					],
					fileExtensions: null,
					rootFolderId,
					searchSpaceId: Number(searchSpaceId),
					active: true,
				});
				toast.success(`Watching folder: ${selectedFolder.name}`);
			} else {
				toast.success(`Syncing folder: ${selectedFolder.name}`);
			}

			setSelectedFolder(null);
			onSuccess?.();
		} catch (err) {
			toast.error((err as Error)?.message || "Failed to process folder");
		} finally {
			setFolderSubmitting(false);
		}
	}, [selectedFolder, watchFolder, searchSpaceId, shouldSummarize, onSuccess]);

	const handleUpload = async () => {
		setUploadProgress(0);
		trackDocumentUploadStarted(Number(searchSpaceId), files.length, totalFileSize);

		const progressInterval = setInterval(() => {
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
					clearInterval(progressInterval);
					setUploadProgress(100);
					trackDocumentUploadSuccess(Number(searchSpaceId), files.length);
					toast(t("upload_initiated"), { description: t("upload_initiated_desc") });
					onSuccess?.();
				},
				onError: (error: unknown) => {
					clearInterval(progressInterval);
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
						<DropdownMenuItem onClick={handleBrowseFolder}>
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
						variant="secondary"
						size="sm"
						className={`text-xs gap-1 ${sizeClass} ${widthClass}`}
					>
						Browse
						<ChevronDown className="h-3 w-3 opacity-60" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="center" onClick={(e) => e.stopPropagation()}>
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
					!selectedFolder &&
					(isElectron ? (
						<div className="w-full">{renderBrowseButton({ compact: true, fullWidth: true })}</div>
					) : (
						<button
							type="button"
							className="w-full text-xs h-8 flex items-center justify-center gap-1.5 rounded-md border border-dashed border-muted-foreground/30 text-muted-foreground hover:text-foreground hover:border-foreground/50 transition-colors"
							onClick={() => fileInputRef.current?.click()}
						>
							Add more files
						</button>
					))
				) : (
					<div
						className="flex flex-col items-center gap-4 py-12 px-4 cursor-pointer"
						onClick={() => {
							if (!isElectron) fileInputRef.current?.click();
						}}
					>
						<Upload className="h-10 w-10 text-muted-foreground" />
						<div className="text-center space-y-1.5">
							<p className="text-base font-medium">
								{isElectron ? "Select files or folder" : "Tap to select files or folder"}
							</p>
							<p className="text-sm text-muted-foreground">{t("file_size_limit")}</p>
						</div>
						<div className="w-full mt-1" onClick={(e) => e.stopPropagation()}>
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
				) : isDragActive ? (
					<div className="flex flex-col items-center gap-2">
						<Upload className="h-8 w-8 text-primary" />
						<p className="text-sm font-medium text-primary">{t("drop_files")}</p>
					</div>
				) : (
					<div className="flex flex-col items-center gap-2">
						<Upload className="h-8 w-8 text-muted-foreground" />
						<p className="text-sm font-medium">{t("drag_drop")}</p>
						<p className="text-xs text-muted-foreground">{t("file_size_limit")}</p>
						<div className="mt-1">{renderBrowseButton()}</div>
					</div>
				)}
			</div>

			{/* FOLDER SELECTED (Electron only — web flattens folder contents into file list) */}
			{isElectron && selectedFolder && (
				<div className="rounded-lg border border-border p-3 space-y-2">
					<div className="flex items-center gap-2 py-1.5 px-2 -mx-1 rounded-md hover:bg-slate-400/5 dark:hover:bg-white/5 group">
						<FolderOpen className="h-4 w-4 text-primary shrink-0" />
						<div className="min-w-0 flex-1">
							<p className="text-sm font-medium truncate">{selectedFolder.name}</p>
							<p className="text-xs text-muted-foreground truncate">{selectedFolder.path}</p>
						</div>
						<Button
							variant="ghost"
							size="icon"
							className="h-7 w-7 shrink-0"
							onClick={() => setSelectedFolder(null)}
							disabled={folderSubmitting}
						>
							<X className="h-3.5 w-3.5" />
						</Button>
					</div>

					<div className="rounded-lg bg-slate-400/5 dark:bg-white/5 divide-y divide-border">
						<div className="flex items-center justify-between p-3">
							<div className="space-y-0.5">
								<p className="font-medium text-sm">Watch folder</p>
								<p className="text-xs text-muted-foreground">Auto-sync when files change</p>
							</div>
							<Switch
								id="watch-folder-toggle"
								checked={watchFolder}
								onCheckedChange={setWatchFolder}
							/>
						</div>
						<div className="flex items-center justify-between p-3">
							<div className="space-y-0.5">
								<p className="font-medium text-sm">Enable AI Summary</p>
								<p className="text-xs text-muted-foreground">
									Improves search quality but adds latency
								</p>
							</div>
							<Switch checked={shouldSummarize} onCheckedChange={setShouldSummarize} />
						</div>
					</div>

					<Button
						className="w-full relative"
						onClick={handleFolderSubmit}
						disabled={folderSubmitting}
					>
						<span className={folderSubmitting ? "invisible" : ""}>
							{watchFolder ? "Sync & Watch for Changes" : "Sync Folder"}
						</span>
						{folderSubmitting && (
							<span className="absolute inset-0 flex items-center justify-center">
								<Spinner size="sm" />
							</span>
						)}
					</Button>
				</div>
			)}

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
						<div className="flex flex-wrap gap-1">
							{supportedExtensions.map((ext) => (
								<Badge key={ext} variant="outline" className="text-[10px] px-1.5 py-0">
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
