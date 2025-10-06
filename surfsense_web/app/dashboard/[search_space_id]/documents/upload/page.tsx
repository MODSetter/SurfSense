"use client";

import { CheckCircle2, FileType, Info, Tag, Upload, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";

// Grid pattern component inspired by Aceternity UI
function GridPattern() {
	const columns = 41;
	const rows = 11;
	return (
		<div className="flex bg-gray-100 dark:bg-neutral-900 flex-shrink-0 flex-wrap justify-center items-center gap-x-px gap-y-px scale-105">
			{Array.from({ length: rows }).map((_, row) =>
				Array.from({ length: columns }).map((_, col) => {
					const index = row * columns + col;
					return (
						<div
							key={`${col}-${row}`}
							className={`w-10 h-10 flex flex-shrink-0 rounded-[2px] ${
								index % 2 === 0
									? "bg-gray-50 dark:bg-neutral-950"
									: "bg-gray-50 dark:bg-neutral-950 shadow-[0px_0px_1px_3px_rgba(255,255,255,1)_inset] dark:shadow-[0px_0px_1px_3px_rgba(0,0,0,1)_inset]"
							}`}
						/>
					);
				})
			)}
		</div>
	);
}

export default function FileUploader() {
	const params = useParams();
	const search_space_id = params.search_space_id as string;

	const [files, setFiles] = useState<File[]>([]);
	const [isUploading, setIsUploading] = useState(false);
	const [uploadProgress, setUploadProgress] = useState(0);
	const router = useRouter();

	// Audio files are always supported (using whisper)
	const audioFileTypes = {
		"audio/mpeg": [".mp3", ".mpeg", ".mpga"],
		"audio/mp4": [".mp4", ".m4a"],
		"audio/wav": [".wav"],
		"audio/webm": [".webm"],
		"text/markdown": [".md", ".markdown"],
		"text/plain": [".txt"],
	};

	// Conditionally set accepted file types based on ETL service
	const getAcceptedFileTypes = () => {
		const etlService = process.env.NEXT_PUBLIC_ETL_SERVICE;

		if (etlService === "LLAMACLOUD") {
			return {
				// LlamaCloud supported file types
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
				"application/vnd.apple.keynote": [".key"],
				"application/vnd.apple.pages": [".pages"],
				"application/vnd.apple.numbers": [".numbers"],
				"application/vnd.wordperfect": [".wpd"],
				"application/vnd.oasis.opendocument.text": [".odt"],
				"application/vnd.oasis.opendocument.presentation": [".odp"],
				"application/vnd.oasis.opendocument.graphics": [".odg"],
				"application/vnd.oasis.opendocument.spreadsheet": [".ods"],
				"application/vnd.oasis.opendocument.formula": [".fods"],
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
				"application/dbase": [".dbf"],
				"application/vnd.lotus-1-2-3": [".123"],
				"text/x-web-markdown": [
					".602",
					".abw",
					".cgm",
					".cwk",
					".hwp",
					".lwp",
					".mw",
					".mcw",
					".pbd",
					".sda",
					".sdd",
					".sdp",
					".sdw",
					".sgl",
					".sti",
					".sxi",
					".sxw",
					".stw",
					".sxg",
					".uof",
					".uop",
					".uot",
					".vor",
					".wps",
					".zabw",
				],
				"text/x-spreadsheet": [
					".dif",
					".sylk",
					".slk",
					".prn",
					".et",
					".uos1",
					".uos2",
					".wk1",
					".wk2",
					".wk3",
					".wk4",
					".wks",
					".wq1",
					".wq2",
					".wb1",
					".wb2",
					".wb3",
					".qpw",
					".xlr",
					".eth",
				],
				// Audio files (always supported)
				...audioFileTypes,
			};
		} else if (etlService === "DOCLING") {
			return {
				// Docling supported file types
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
				// Audio files (always supported)
				...audioFileTypes,
			};
		} else {
			return {
				// Unstructured supported file types
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
				// Audio files (always supported)
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
		maxSize: 50 * 1024 * 1024, // 50MB
		noClick: false, // Ensure clicking is enabled
		noKeyboard: false, // Ensure keyboard navigation is enabled
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

		formData.append("search_space_id", search_space_id);

		try {
			// Simulate progress for better UX
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

			toast("Upload Task Initiated", {
				description: "Files Uploading Initiated",
			});

			router.push(`/dashboard/${search_space_id}/documents`);
		} catch (error: any) {
			setIsUploading(false);
			setUploadProgress(0);
			toast("Upload Error", {
				description: `Error uploading files: ${error.message}`,
			});
		}
	};

	const getTotalFileSize = () => {
		return files.reduce((total, file) => total + file.size, 0);
	};

	const containerVariants = {
		hidden: { opacity: 0, y: 20 },
		visible: {
			opacity: 1,
			y: 0,
			transition: {
				duration: 0.5,
				when: "beforeChildren",
				staggerChildren: 0.1,
			},
		},
	};

	const itemVariants = {
		hidden: { opacity: 0, y: 10 },
		visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
	};

	const fileItemVariants = {
		hidden: { opacity: 0, x: -20 },
		visible: { opacity: 1, x: 0, transition: { duration: 0.3 } },
		exit: { opacity: 0, x: 20, transition: { duration: 0.2 } },
	};

	return (
		<div className="grow flex items-center justify-center p-4 md:p-8">
			<motion.div
				className="w-full max-w-4xl mx-auto space-y-6"
				initial="hidden"
				animate="visible"
				variants={containerVariants}
			>
				{/* Header Card */}
				<motion.div variants={itemVariants}>
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2">
								<Upload className="h-5 w-5" />
								Upload Documents
							</CardTitle>
							<CardDescription>
								Upload your files to make them searchable and accessible through AI-powered
								conversations.
							</CardDescription>
						</CardHeader>
						<CardContent>
							<Alert>
								<Info className="h-4 w-4" />
								<AlertDescription>
									Maximum file size: 50MB per file. Supported formats vary based on your ETL service
									configuration.
								</AlertDescription>
							</Alert>
						</CardContent>
					</Card>
				</motion.div>

				{/* Upload Area Card */}
				<motion.div variants={itemVariants}>
					<Card className="relative overflow-hidden">
						{/* Grid background pattern */}
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
										<p className="text-lg font-medium text-primary">Drop files here</p>
									</motion.div>
								) : (
									<motion.div
										initial={{ opacity: 0 }}
										animate={{ opacity: 1 }}
										className="flex flex-col items-center gap-4"
									>
										<Upload className="h-12 w-12 text-muted-foreground" />
										<div className="text-center">
											<p className="text-lg font-medium">Drag & drop files here</p>
											<p className="text-sm text-muted-foreground mt-1">or click to browse</p>
										</div>
									</motion.div>
								)}

								{/* Fallback button for better accessibility */}
								<div className="mt-4">
									<Button
										variant="outline"
										size="sm"
										onClick={(e) => {
											e.stopPropagation();
											const input = document.querySelector(
												'input[type="file"]'
											) as HTMLInputElement;
											if (input) input.click();
										}}
									>
										Browse Files
									</Button>
								</div>
							</div>
						</CardContent>
					</Card>
				</motion.div>

				{/* File List Card */}
				<AnimatePresence mode="wait">
					{files.length > 0 && (
						<motion.div
							variants={itemVariants}
							initial={{ opacity: 0, height: 0 }}
							animate={{ opacity: 1, height: "auto" }}
							exit={{ opacity: 0, height: 0 }}
							transition={{ duration: 0.3 }}
						>
							<Card>
								<CardHeader>
									<div className="flex items-center justify-between">
										<div>
											<CardTitle>Selected Files ({files.length})</CardTitle>
											<CardDescription>
												Total size: {formatFileSize(getTotalFileSize())}
											</CardDescription>
										</div>
										<Button
											variant="outline"
											size="sm"
											onClick={() => setFiles([])}
											disabled={isUploading}
										>
											Clear all
										</Button>
									</div>
								</CardHeader>
								<CardContent>
									<div className="space-y-3 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
										<AnimatePresence>
											{files.map((file, index) => (
												<motion.div
													key={`${file.name}-${index}`}
													variants={fileItemVariants}
													initial="hidden"
													animate="visible"
													exit="exit"
													className="flex items-center justify-between p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
												>
													<div className="flex items-center gap-3 flex-1 min-w-0">
														<div className="flex-shrink-0">
															<FileType className="h-5 w-5 text-muted-foreground" />
														</div>
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
													<div className="flex items-center gap-2">
														<Button
															variant="ghost"
															size="icon"
															onClick={() => removeFile(index)}
															disabled={isUploading}
															className="h-8 w-8"
														>
															<X className="h-4 w-4" />
														</Button>
													</div>
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
													<span>Uploading files...</span>
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
										transition={{ delay: 0.2 }}
									>
										<Button
											className="w-full py-6 text-base font-medium"
											onClick={handleUpload}
											disabled={isUploading || files.length === 0}
										>
											{isUploading ? (
												<motion.div
													className="flex items-center gap-2"
													initial={{ opacity: 0 }}
													animate={{ opacity: 1 }}
												>
													<motion.div
														animate={{ rotate: 360 }}
														transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
													>
														<Upload className="h-5 w-5" />
													</motion.div>
													<span>Uploading...</span>
												</motion.div>
											) : (
												<motion.div
													className="flex items-center gap-2"
													whileHover={{ scale: 1.02 }}
													whileTap={{ scale: 0.98 }}
												>
													<CheckCircle2 className="h-5 w-5" />
													<span>
														Upload {files.length} {files.length === 1 ? "file" : "files"}
													</span>
												</motion.div>
											)}
										</Button>
									</motion.div>
								</CardContent>
							</Card>
						</motion.div>
					)}
				</AnimatePresence>

				{/* Supported File Types Card */}
				<motion.div variants={itemVariants}>
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2">
								<Tag className="h-5 w-5" />
								Supported File Types
							</CardTitle>
							<CardDescription>
								These file types are supported based on your current ETL service configuration.
							</CardDescription>
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
			</motion.div>

			<style jsx global>{`
                .custom-scrollbar::-webkit-scrollbar {
                    width: 6px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: transparent;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background-color: rgba(var(--muted-foreground), 0.3);
                    border-radius: 20px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background-color: rgba(var(--muted-foreground), 0.5);
                }
            `}</style>
		</div>
	);
}
