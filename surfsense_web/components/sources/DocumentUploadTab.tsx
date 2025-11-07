"use client";

import { CheckCircle2, FileType, Info, Loader2, Tag, Upload, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { GridPattern } from "./GridPattern";

interface DocumentUploadTabProps {
	searchSpaceId: string;
}

export function DocumentUploadTab({ searchSpaceId }: DocumentUploadTabProps) {
	const t = useTranslations("upload_documents");
	const router = useRouter();
	const [files, setFiles] = useState<File[]>([]);
	const [isUploading, setIsUploading] = useState(false);
	const [uploadProgress, setUploadProgress] = useState(0);

	const audioFileTypes = {
		"audio/mpeg": [".mp3", ".mpeg", ".mpga"],
		"audio/mp4": [".mp4", ".m4a"],
		"audio/wav": [".wav"],
		"audio/webm": [".webm"],
		"text/markdown": [".md", ".markdown"],
		"text/plain": [".txt"],
	};

	const getAcceptedFileTypes = () => {
		const etlService = process.env.NEXT_PUBLIC_ETL_SERVICE;

		if (etlService === "LLAMACLOUD") {
			return {
				"application/pdf": [".pdf"],
				"application/msword": [".doc"],
				"application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
				"application/vnd.ms-word.document.macroEnabled.12": [".docm"],
				"application/msword-template": [".dot"],
				"application/vnd.ms-word.template.macroEnabled.12": [".dotm"],
				"application/vnd.ms-powerpoint": [".ppt"],
				"application/vnd.ms-powerpoint.template.macroEnabled.12": [".pptm"],
				"application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
				"application/vnd.ms-powerpoint.template": [".pot"],
				"application/vnd.openxmlformats-officedocument.presentationml.template": [".potx"],
				"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
				"application/vnd.ms-excel": [".xls"],
				"application/vnd.ms-excel.sheet.macroEnabled.12": [".xlsm"],
				"application/vnd.ms-excel.sheet.binary.macroEnabled.12": [".xlsb"],
				"application/vnd.ms-excel.workspace": [".xlw"],
				"application/rtf": [".rtf"],
				"application/xml": [".xml"],
				"application/epub+zip": [".epub"],
				"text/csv": [".csv"],
				"text/tab-separated-values": [".tsv"],
				"text/html": [".html", ".htm", ".web"],
				"image/jpeg": [".jpg", ".jpeg"],
				"image/png": [".png"],
				"image/gif": [".gif"],
				"image/bmp": [".bmp"],
				"image/svg+xml": [".svg"],
				"image/tiff": [".tiff"],
				"image/webp": [".webp"],
				...audioFileTypes,
			};
		} else if (etlService === "DOCLING") {
			return {
				"application/pdf": [".pdf"],
				"application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
				"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
				"application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
				"text/asciidoc": [".adoc", ".asciidoc"],
				"text/html": [".html", ".htm", ".xhtml"],
				"text/csv": [".csv"],
				"image/png": [".png"],
				"image/jpeg": [".jpg", ".jpeg"],
				"image/tiff": [".tiff", ".tif"],
				"image/bmp": [".bmp"],
				"image/webp": [".webp"],
				...audioFileTypes,
			};
		} else {
			return {
				"image/bmp": [".bmp"],
				"text/csv": [".csv"],
				"application/msword": [".doc"],
				"application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
				"message/rfc822": [".eml"],
				"application/epub+zip": [".epub"],
				"image/heic": [".heic"],
				"text/html": [".html"],
				"image/jpeg": [".jpeg", ".jpg"],
				"image/png": [".png"],
				"application/vnd.ms-outlook": [".msg"],
				"application/vnd.oasis.opendocument.text": [".odt"],
				"text/x-org": [".org"],
				"application/pkcs7-signature": [".p7s"],
				"application/pdf": [".pdf"],
				"application/vnd.ms-powerpoint": [".ppt"],
				"application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
				"text/x-rst": [".rst"],
				"application/rtf": [".rtf"],
				"image/tiff": [".tiff"],
				"text/tab-separated-values": [".tsv"],
				"application/vnd.ms-excel": [".xls"],
				"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
				"application/xml": [".xml"],
				...audioFileTypes,
			};
		}
	};

	const acceptedFileTypes = getAcceptedFileTypes();
	const supportedExtensions = Array.from(new Set(Object.values(acceptedFileTypes).flat())).sort();

	const onDrop = useCallback((acceptedFiles: File[]) => {
		setFiles((prevFiles) => [...prevFiles, ...acceptedFiles]);
	}, []);

	const { getRootProps, getInputProps, isDragActive } = useDropzone({
		onDrop,
		accept: acceptedFileTypes,
		maxSize: 50 * 1024 * 1024,
		noClick: false,
		noKeyboard: false,
	});

	const removeFile = (index: number) => {
		setFiles((prevFiles) => prevFiles.filter((_, i) => i !== index));
	};

	const formatFileSize = (bytes: number) => {
		if (bytes === 0) return "0 Bytes";
		const k = 1024;
		const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return `${parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`;
	};

	const handleUpload = async () => {
		setIsUploading(true);
		setUploadProgress(0);

		const formData = new FormData();
		files.forEach((file) => {
			formData.append("files", file);
		});
		formData.append("search_space_id", searchSpaceId);

		try {
			const progressInterval = setInterval(() => {
				setUploadProgress((prev) => {
					if (prev >= 90) return prev;
					return prev + Math.random() * 10;
				});
			}, 200);

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/fileupload`,
				{
					method: "POST",
					headers: {
						Authorization: `Bearer ${window.localStorage.getItem("surfsense_bearer_token")}`,
					},
					body: formData,
				}
			);

			clearInterval(progressInterval);
			setUploadProgress(100);

			if (!response.ok) {
				throw new Error("Upload failed");
			}

			await response.json();

			toast(t("upload_initiated"), {
				description: t("upload_initiated_desc"),
			});

			router.push(`/dashboard/${searchSpaceId}/documents`);
		} catch (error: any) {
			setIsUploading(false);
			setUploadProgress(0);
			toast(t("upload_error"), {
				description: `${t("upload_error_desc")}: ${error.message}`,
			});
		}
	};

	const getTotalFileSize = () => {
		return files.reduce((total, file) => total + file.size, 0);
	};

	return (
		<motion.div
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.3 }}
			className="space-y-6 max-w-4xl mx-auto"
		>
			<Alert>
				<Info className="h-4 w-4" />
				<AlertDescription>{t("file_size_limit")}</AlertDescription>
			</Alert>

			<Card className="relative overflow-hidden">
				<div className="absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,white,transparent)] opacity-30">
					<GridPattern />
				</div>

				<CardContent className="p-10 relative z-10">
					<div
						{...getRootProps()}
						className="flex flex-col items-center justify-center min-h-[300px] border-2 border-dashed border-muted-foreground/25 rounded-lg hover:border-primary/50 transition-colors cursor-pointer"
					>
						<input {...getInputProps()} className="hidden" />

						{isDragActive ? (
							<motion.div
								initial={{ opacity: 0, scale: 0.8 }}
								animate={{ opacity: 1, scale: 1 }}
								className="flex flex-col items-center gap-4"
							>
								<Upload className="h-12 w-12 text-primary" />
								<p className="text-lg font-medium text-primary">{t("drop_files")}</p>
							</motion.div>
						) : (
							<motion.div
								initial={{ opacity: 0 }}
								animate={{ opacity: 1 }}
								className="flex flex-col items-center gap-4"
							>
								<Upload className="h-12 w-12 text-muted-foreground" />
								<div className="text-center">
									<p className="text-lg font-medium">{t("drag_drop")}</p>
									<p className="text-sm text-muted-foreground mt-1">{t("or_browse")}</p>
								</div>
							</motion.div>
						)}

						<div className="mt-4">
							<Button
								variant="outline"
								size="sm"
								onClick={(e) => {
									e.stopPropagation();
									const input = document.querySelector('input[type="file"]') as HTMLInputElement;
									if (input) input.click();
								}}
							>
								{t("browse_files")}
							</Button>
						</div>
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
						<Card>
							<CardHeader>
								<div className="flex items-center justify-between">
									<div>
										<CardTitle>{t("selected_files", { count: files.length })}</CardTitle>
										<CardDescription>
											{t("total_size")}: {formatFileSize(getTotalFileSize())}
										</CardDescription>
									</div>
									<Button
										variant="outline"
										size="sm"
										onClick={() => setFiles([])}
										disabled={isUploading}
									>
										{t("clear_all")}
									</Button>
								</div>
							</CardHeader>
							<CardContent>
								<div className="space-y-3 max-h-[400px] overflow-y-auto">
									<AnimatePresence>
										{files.map((file, index) => (
											<motion.div
												key={`${file.name}-${index}`}
												initial={{ opacity: 0, x: -20 }}
												animate={{ opacity: 1, x: 0 }}
												exit={{ opacity: 0, x: 20 }}
												className="flex items-center justify-between p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
											>
												<div className="flex items-center gap-3 flex-1 min-w-0">
													<FileType className="h-5 w-5 text-muted-foreground flex-shrink-0" />
													<div className="flex-1 min-w-0">
														<p className="font-medium truncate">{file.name}</p>
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
													onClick={() => removeFile(index)}
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
										className="mt-6 space-y-3"
									>
										<Separator />
										<div className="space-y-2">
											<div className="flex items-center justify-between text-sm">
												<span>{t("uploading_files")}</span>
												<span>{Math.round(uploadProgress)}%</span>
											</div>
											<Progress value={uploadProgress} className="h-2" />
										</div>
									</motion.div>
								)}

								<motion.div
									className="mt-6"
									initial={{ opacity: 0, y: 10 }}
									animate={{ opacity: 1, y: 0 }}
								>
									<Button
										className="w-full py-6 text-base font-medium"
										onClick={handleUpload}
										disabled={isUploading || files.length === 0}
									>
										{isUploading ? (
											<span className="flex items-center gap-2">
												<Loader2 className="h-5 w-5 animate-spin" />
												{t("uploading")}
											</span>
										) : (
											<span className="flex items-center gap-2">
												<CheckCircle2 className="h-5 w-5" />
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

			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<Tag className="h-5 w-5" />
						{t("supported_file_types")}
					</CardTitle>
					<CardDescription>{t("file_types_desc")}</CardDescription>
				</CardHeader>
				<CardContent>
					<div className="flex flex-wrap gap-2">
						{supportedExtensions.map((ext) => (
							<Badge key={ext} variant="outline" className="text-xs">
								{ext}
							</Badge>
						))}
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
