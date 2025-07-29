"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Calendar, CheckCircle2, FileType, Tag, Upload, X } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

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
	// Use the useParams hook to get the params
	const params = useParams();
	const search_space_id = params.search_space_id as string;

	const [files, setFiles] = useState<File[]>([]);
	const [isUploading, setIsUploading] = useState(false);
	const router = useRouter();
	const fileInputRef = useRef<HTMLInputElement>(null);

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
	});

	const handleClick = () => {
		fileInputRef.current?.click();
	};

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

		const formData = new FormData();
		files.forEach((file) => {
			formData.append("files", file);
		});

		formData.append("search_space_id", search_space_id);

		try {
			// toast("File Upload", {
			//     description: "Files Uploading Initiated",
			// })

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL!}/api/v1/documents/fileupload`,
				{
					method: "POST",
					headers: {
						Authorization: `Bearer ${window.localStorage.getItem("surfsense_bearer_token")}`,
					},
					body: formData,
				}
			);

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
			toast("Upload Error", {
				description: `Error uploading files: ${error.message}`,
			});
		}
	};

	const mainVariant = {
		initial: {
			x: 0,
			y: 0,
		},
		animate: {
			x: 20,
			y: -20,
			opacity: 0.9,
		},
	};

	const secondaryVariant = {
		initial: {
			opacity: 0,
		},
		animate: {
			opacity: 1,
		},
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
				className="w-full max-w-3xl mx-auto"
				initial="hidden"
				animate="visible"
				variants={containerVariants}
			>
				<motion.div
					className="bg-background rounded-xl shadow-lg overflow-hidden border border-border"
					variants={itemVariants}
				>
					<motion.div
						className="p-10 group/file block rounded-lg cursor-pointer w-full relative overflow-hidden"
						whileHover="animate"
						onClick={handleClick}
					>
						{/* Grid background pattern */}
						<div className="absolute inset-0 [mask-image:radial-gradient(ellipse_at_center,white,transparent)]">
							<GridPattern />
						</div>

						<div className="relative z-10">
							{/* Dropzone area */}
							<div {...getRootProps()} className="flex flex-col items-center justify-center">
								<input {...getInputProps()} ref={fileInputRef} className="hidden" />

								<p className="relative z-20 font-sans font-bold text-neutral-700 dark:text-neutral-300 text-xl">
									Upload files
								</p>
								<p className="relative z-20 font-sans font-normal text-neutral-400 dark:text-neutral-400 text-base mt-2">
									Drag or drop your files here or click to upload
								</p>

								<div className="relative w-full mt-10 max-w-xl mx-auto">
									{!files.length && (
										<motion.div
											layoutId="file-upload"
											variants={mainVariant}
											transition={{
												type: "spring",
												stiffness: 300,
												damping: 20,
											}}
											className="relative group-hover/file:shadow-2xl z-40 bg-white dark:bg-neutral-900 flex items-center justify-center h-32 mt-4 w-full max-w-[8rem] mx-auto rounded-md shadow-[0px_10px_50px_rgba(0,0,0,0.1)]"
											key="upload-icon"
											initial={{ opacity: 0 }}
											animate={{ opacity: 1 }}
											exit={{ opacity: 0 }}
										>
											{isDragActive ? (
												<motion.p
													initial={{ opacity: 0 }}
													animate={{ opacity: 1 }}
													className="text-neutral-600 flex flex-col items-center"
												>
													Drop it
													<Upload className="h-4 w-4 text-neutral-600 dark:text-neutral-400 mt-2" />
												</motion.p>
											) : (
												<Upload className="h-8 w-8 text-neutral-600 dark:text-neutral-300" />
											)}
										</motion.div>
									)}

									{!files.length && (
										<motion.div
											variants={secondaryVariant}
											className="absolute opacity-0 border border-dashed border-primary inset-0 z-30 bg-transparent flex items-center justify-center h-32 mt-4 w-full max-w-[8rem] mx-auto rounded-md"
											key="upload-border"
											initial={{ opacity: 0 }}
											animate={{ opacity: 1 }}
											exit={{ opacity: 0 }}
										></motion.div>
									)}
								</div>
							</div>
						</div>
					</motion.div>

					{/* File list section */}
					<AnimatePresence mode="wait">
						{files.length > 0 && (
							<motion.div
								className="px-8 pb-8"
								initial={{ opacity: 0, height: 0 }}
								animate={{ opacity: 1, height: "auto" }}
								exit={{ opacity: 0, height: 0 }}
								transition={{ duration: 0.3 }}
							>
								<div className="mb-4 flex items-center justify-between">
									<h3 className="font-medium">Selected Files ({files.length})</h3>
									<Button
										variant="ghost"
										size="sm"
										onClick={() => {
											// Use AnimatePresence to properly handle the transition
											// This will ensure the file icon reappears properly
											setFiles([]);

											// Force a re-render after animation completes
											setTimeout(() => {
												const event = new Event("resize");
												window.dispatchEvent(event);
											}, 350);
										}}
										disabled={isUploading}
									>
										Clear all
									</Button>
								</div>

								<div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
									<AnimatePresence>
										{files.map((file, index) => (
											<motion.div
												key={`${file.name}-${index}`}
												layoutId={index === 0 ? "file-upload" : `file-upload-${index}`}
												className="relative overflow-hidden z-40 bg-white dark:bg-neutral-900 flex flex-col items-start justify-start p-4 w-full mx-auto rounded-md shadow-sm border border-border"
												initial="hidden"
												animate="visible"
												exit="exit"
												variants={fileItemVariants}
											>
												<div className="flex justify-between w-full items-center gap-4">
													<motion.p
														initial={{ opacity: 0 }}
														animate={{ opacity: 1 }}
														layout
														className="text-base text-neutral-700 dark:text-neutral-300 truncate max-w-xs font-medium"
													>
														{file.name}
													</motion.p>
													<div className="flex items-center gap-2">
														<motion.p
															initial={{ opacity: 0 }}
															animate={{ opacity: 1 }}
															layout
															className="rounded-lg px-2 py-1 w-fit flex-shrink-0 text-sm text-neutral-600 dark:bg-neutral-800 dark:text-white bg-neutral-100"
														>
															{formatFileSize(file.size)}
														</motion.p>
														<Button
															variant="ghost"
															size="icon"
															onClick={() => removeFile(index)}
															disabled={isUploading}
															className="h-8 w-8"
															aria-label={`Remove ${file.name}`}
														>
															<X className="h-4 w-4" />
														</Button>
													</div>
												</div>

												<div className="flex text-sm md:flex-row flex-col items-start md:items-center w-full mt-2 justify-between text-neutral-600 dark:text-neutral-400">
													<motion.div
														initial={{ opacity: 0 }}
														animate={{ opacity: 1 }}
														layout
														className="flex items-center gap-1 px-2 py-1 rounded-md bg-gray-100 dark:bg-neutral-800"
													>
														<FileType className="h-3 w-3" />
														<span>{file.type || "Unknown type"}</span>
													</motion.div>

													<motion.div
														initial={{ opacity: 0 }}
														animate={{ opacity: 1 }}
														layout
														className="flex items-center gap-1 mt-2 md:mt-0"
													>
														<Calendar className="h-3 w-3" />
														<span>modified {new Date(file.lastModified).toLocaleDateString()}</span>
													</motion.div>
												</div>
											</motion.div>
										))}
									</AnimatePresence>
								</div>

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
							</motion.div>
						)}
					</AnimatePresence>

					{/* File type information */}
					<motion.div className="px-8 pb-8" variants={itemVariants}>
						<div className="p-4 bg-muted rounded-lg">
							<div className="flex items-center gap-2 mb-3">
								<Tag className="h-4 w-4 text-primary" />
								<p className="text-sm font-medium">Supported file types:</p>
							</div>
							<div className="flex flex-wrap gap-2">
								{supportedExtensions.map((ext) => (
									<motion.span
										key={ext}
										className="px-2 py-1 bg-primary/10 text-primary text-xs rounded-full"
										whileHover={{ scale: 1.05, backgroundColor: "rgba(var(--primary), 0.2)" }}
										initial={{ opacity: 1 }}
										animate={{ opacity: 1 }}
										exit={{ opacity: 1 }}
										layout
									>
										{ext}
									</motion.span>
								))}
							</div>
						</div>
					</motion.div>
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
