"use client";

import { useAtom } from "jotai";
import { CheckCircle2, FileType, Info, Tag, Upload, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useCallback, useMemo, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { uploadDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import {
	trackDocumentUploadFailure,
	trackDocumentUploadStarted,
	trackDocumentUploadSuccess,
} from "@/lib/posthog/events";
import { GridPattern } from "./GridPattern";

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
		"text/tab-separated-values": [".tsv"],
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
		"text/tab-separated-values": [".tsv"],
		"application/vnd.ms-excel": [".xls"],
		"application/xml": [".xml"],
		...audioFileTypes,
	},
};

const cardClass = "border border-border bg-slate-400/5 dark:bg-white/5";

// Upload limits
const MAX_FILES = 10;
const MAX_TOTAL_SIZE_MB = 200;
const MAX_TOTAL_SIZE_BYTES = MAX_TOTAL_SIZE_MB * 1024 * 1024;

export function DocumentUploadTab({
	searchSpaceId,
	onSuccess,
	onAccordionStateChange,
}: DocumentUploadTabProps) {
	const t = useTranslations("upload_documents");
	const [files, setFiles] = useState<File[]>([]);
	const [uploadProgress, setUploadProgress] = useState(0);
	const [accordionValue, setAccordionValue] = useState<string>("");
	const [uploadDocumentMutation] = useAtom(uploadDocumentMutationAtom);
	const { mutate: uploadDocuments, isPending: isUploading } = uploadDocumentMutation;
	const fileInputRef = useRef<HTMLInputElement>(null);

	const acceptedFileTypes = useMemo(() => {
		const etlService = process.env.NEXT_PUBLIC_ETL_SERVICE;
		return FILE_TYPE_CONFIG[etlService || "default"] || FILE_TYPE_CONFIG.default;
	}, []);

	const supportedExtensions = useMemo(
		() => Array.from(new Set(Object.values(acceptedFileTypes).flat())).sort(),
		[acceptedFileTypes]
	);

	const onDrop = useCallback(
		(acceptedFiles: File[]) => {
			setFiles((prev) => {
				const newFiles = [...prev, ...acceptedFiles];

				// Check file count limit
				if (newFiles.length > MAX_FILES) {
					toast.error(t("max_files_exceeded"), {
						description: t("max_files_exceeded_desc", { max: MAX_FILES }),
					});
					return prev;
				}

				// Check total size limit
				const newTotalSize = newFiles.reduce((sum, file) => sum + file.size, 0);
				if (newTotalSize > MAX_TOTAL_SIZE_BYTES) {
					toast.error(t("max_size_exceeded"), {
						description: t("max_size_exceeded_desc", { max: MAX_TOTAL_SIZE_MB }),
					});
					return prev;
				}

				return newFiles;
			});
		},
		[t]
	);

	const { getRootProps, getInputProps, isDragActive } = useDropzone({
		onDrop,
		accept: acceptedFileTypes,
		maxSize: 50 * 1024 * 1024, // 50MB per file
		noClick: false,
		disabled: files.length >= MAX_FILES,
	});

	// Handle file input click to prevent event bubbling that might reopen dialog
	const handleFileInputClick = useCallback((e: React.MouseEvent<HTMLInputElement>) => {
		e.stopPropagation();
	}, []);

	const formatFileSize = (bytes: number) => {
		if (bytes === 0) return "0 Bytes";
		const k = 1024;
		const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return `${parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`;
	};

	const totalFileSize = files.reduce((total, file) => total + file.size, 0);

	// Check if limits are reached
	const isFileCountLimitReached = files.length >= MAX_FILES;
	const isSizeLimitReached = totalFileSize >= MAX_TOTAL_SIZE_BYTES;
	const remainingFiles = MAX_FILES - files.length;
	const remainingSizeMB = Math.max(
		0,
		(MAX_TOTAL_SIZE_BYTES - totalFileSize) / (1024 * 1024)
	).toFixed(1);

	// Track accordion state changes
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

		const progressInterval = setInterval(() => {
			setUploadProgress((prev) => (prev >= 90 ? prev : prev + Math.random() * 10));
		}, 200);

		uploadDocuments(
			{ files, search_space_id: Number(searchSpaceId) },
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

	return (
		<motion.div
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.3 }}
			className="space-y-3 sm:space-y-6 max-w-4xl mx-auto pt-0"
		>
			<Alert className="border border-border bg-slate-400/5 dark:bg-white/5 flex items-start gap-3 [&>svg]:relative [&>svg]:left-0 [&>svg]:top-0 [&>svg~*]:pl-0">
				<Info className="h-4 w-4 shrink-0 mt-0.5" />
				<AlertDescription className="text-xs sm:text-sm leading-relaxed pt-0.5">
					{t("file_size_limit")}{" "}
					{t("upload_limits", { maxFiles: MAX_FILES, maxSizeMB: MAX_TOTAL_SIZE_MB })}
				</AlertDescription>
			</Alert>

			<Card className={`relative overflow-hidden ${cardClass}`}>
				<div className="absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,white,transparent)] opacity-30">
					<GridPattern />
				</div>
				<CardContent className="p-4 sm:p-10 relative z-10">
					<div
						{...getRootProps()}
						className={`flex flex-col items-center justify-center min-h-[200px] sm:min-h-[300px] border-2 border-dashed rounded-lg transition-colors ${
							isFileCountLimitReached || isSizeLimitReached
								? "border-destructive/50 bg-destructive/5 cursor-not-allowed"
								: "border-border hover:border-primary/50 cursor-pointer"
						}`}
					>
						<input
							{...getInputProps()}
							ref={fileInputRef}
							className="hidden"
							onClick={handleFileInputClick}
						/>
						{isFileCountLimitReached ? (
							<div className="flex flex-col items-center gap-2 sm:gap-4 text-center px-4">
								<Upload className="h-8 w-8 sm:h-12 sm:w-12 text-destructive/70" />
								<div>
									<p className="text-sm sm:text-lg font-medium text-destructive">
										{t("file_limit_reached")}
									</p>
									<p className="text-xs sm:text-sm text-muted-foreground mt-1">
										{t("file_limit_reached_desc", { max: MAX_FILES })}
									</p>
								</div>
							</div>
						) : isDragActive ? (
							<motion.div
								initial={{ opacity: 0, scale: 0.8 }}
								animate={{ opacity: 1, scale: 1 }}
								className="flex flex-col items-center gap-2 sm:gap-4"
							>
								<Upload className="h-8 w-8 sm:h-12 sm:w-12 text-primary" />
								<p className="text-sm sm:text-lg font-medium text-primary">{t("drop_files")}</p>
							</motion.div>
						) : (
							<div className="flex flex-col items-center gap-2 sm:gap-4">
								<Upload className="h-8 w-8 sm:h-12 sm:w-12 text-muted-foreground" />
								<div className="text-center">
									<p className="text-sm sm:text-lg font-medium">{t("drag_drop")}</p>
									<p className="text-xs sm:text-sm text-muted-foreground mt-1">{t("or_browse")}</p>
								</div>
								{files.length > 0 && (
									<p className="text-xs text-muted-foreground">
										{t("remaining_capacity", { files: remainingFiles, sizeMB: remainingSizeMB })}
									</p>
								)}
							</div>
						)}
						{!isFileCountLimitReached && (
							<div className="mt-2 sm:mt-4">
								<Button
									variant="outline"
									size="sm"
									className="text-xs sm:text-sm"
									onClick={(e) => {
										e.stopPropagation();
										e.preventDefault();
										fileInputRef.current?.click();
									}}
								>
									{t("browse_files")}
								</Button>
							</div>
						)}
					</div>
				</CardContent>
			</Card>

			<AnimatePresence mode="wait">
				{files.length > 0 && (
					<motion.div
						initial={{ opacity: 0, height: 0 }}
						animate={{ opacity: 1, height: "auto" }}
						exit={{ opacity: 0, height: 0 }}
						transition={{ duration: 0.3 }}
					>
						<Card className={cardClass}>
							<CardHeader className="p-4 sm:p-6">
								<div className="flex items-center justify-between gap-2">
									<div className="min-w-0 flex-1">
										<CardTitle className="text-base sm:text-2xl">
											{t("selected_files", { count: files.length })}
										</CardTitle>
										<CardDescription className="text-xs sm:text-sm">
											{t("total_size")}: {formatFileSize(totalFileSize)}
										</CardDescription>
									</div>
									<Button
										variant="outline"
										size="sm"
										className="text-xs sm:text-sm shrink-0"
										onClick={() => setFiles([])}
										disabled={isUploading}
									>
										{t("clear_all")}
									</Button>
								</div>
							</CardHeader>
							<CardContent className="p-4 sm:p-6 pt-0">
								<div className="space-y-2 sm:space-y-3 max-h-[250px] sm:max-h-[400px] overflow-y-auto">
									<AnimatePresence>
										{files.map((file, index) => (
											<motion.div
												key={`${file.name}-${index}`}
												initial={{ opacity: 0, x: -20 }}
												animate={{ opacity: 1, x: 0 }}
												exit={{ opacity: 0, x: 20 }}
												className={`flex items-center justify-between p-2 sm:p-4 rounded-lg border border-border ${cardClass} hover:bg-slate-400/10 dark:hover:bg-white/10 transition-colors`}
											>
												<div className="flex items-center gap-3 flex-1 min-w-0">
													<FileType className="h-5 w-5 text-muted-foreground flex-shrink-0" />
													<div className="flex-1 min-w-0">
														<p className="text-sm sm:text-base font-medium truncate">{file.name}</p>
														<div className="flex items-center gap-2 mt-1">
															<Badge variant="secondary" className="text-xs">
																{formatFileSize(file.size)}
															</Badge>
															<Badge variant="outline" className="text-xs">
																{file.type || "Unknown type"}
															</Badge>
														</div>
													</div>
												</div>
												<Button
													variant="ghost"
													size="icon"
													onClick={() => setFiles((prev) => prev.filter((_, i) => i !== index))}
													disabled={isUploading}
													className="h-8 w-8"
												>
													<X className="h-4 w-4" />
												</Button>
											</motion.div>
										))}
									</AnimatePresence>
								</div>

								{isUploading && (
									<motion.div
										initial={{ opacity: 0, y: 10 }}
										animate={{ opacity: 1, y: 0 }}
										className="mt-3 sm:mt-6 space-y-2 sm:space-y-3"
									>
										<Separator className="bg-border" />
										<div className="space-y-2">
											<div className="flex items-center justify-between text-xs sm:text-sm">
												<span>{t("uploading_files")}</span>
												<span>{Math.round(uploadProgress)}%</span>
											</div>
											<Progress value={uploadProgress} className="h-2" />
										</div>
									</motion.div>
								)}

								<motion.div
									className="mt-3 sm:mt-6"
									initial={{ opacity: 0, y: 10 }}
									animate={{ opacity: 1, y: 0 }}
								>
									<Button
										className="w-full py-3 sm:py-6 text-xs sm:text-base font-medium"
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
												<CheckCircle2 className="h-4 w-4 sm:h-5 sm:w-5" />
												{t("upload_button", { count: files.length })}
											</span>
										)}
									</Button>
								</motion.div>
							</CardContent>
						</Card>
					</motion.div>
				)}
			</AnimatePresence>

			<Accordion
				type="single"
				collapsible
				value={accordionValue}
				onValueChange={handleAccordionChange}
				className={`w-full ${cardClass} border border-border rounded-lg mb-0`}
			>
				<AccordionItem value="supported-file-types" className="border-0">
					<AccordionTrigger className="px-3 sm:px-6 py-3 sm:py-4 hover:no-underline !items-center [&>svg]:!translate-y-0">
						<div className="flex items-center gap-2 flex-1">
							<Tag className="h-4 w-4 sm:h-5 sm:w-5 shrink-0" />
							<div className="text-left min-w-0">
								<div className="font-semibold text-sm sm:text-base">
									{t("supported_file_types")}
								</div>
								<div className="text-xs sm:text-sm text-muted-foreground font-normal">
									{t("file_types_desc")}
								</div>
							</div>
						</div>
					</AccordionTrigger>
					<AccordionContent className="px-3 sm:px-6 pb-3 sm:pb-6">
						<div className="flex flex-wrap gap-2">
							{supportedExtensions.map((ext) => (
								<Badge key={ext} variant="outline" className="text-xs">
									{ext}
								</Badge>
							))}
						</div>
					</AccordionContent>
				</AccordionItem>
			</Accordion>
		</motion.div>
	);
}
