"use client";

import { IconBrandYoutube } from "@tabler/icons-react";
import { type Tag, TagInput } from "emblor";
import { Loader2 } from "lucide-react";
import { motion, type Variants } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";

// YouTube video ID validation regex
const youtubeRegex =
	/^(https:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})$/;

export default function YouTubeVideoAdder() {
	const t = useTranslations("add_youtube");
	const params = useParams();
	const router = useRouter();
	const search_space_id = params.search_space_id as string;

	const [videoTags, setVideoTags] = useState<Tag[]>([]);
	const [activeTagIndex, setActiveTagIndex] = useState<number | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	// Function to validate a YouTube URL
	const isValidYoutubeUrl = (url: string): boolean => {
		return youtubeRegex.test(url);
	};

	// Function to extract video ID from URL
	const extractVideoId = (url: string): string | null => {
		const match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
		return match ? match[1] : null;
	};

	// Function to handle video URL submission
	const handleSubmit = async () => {
		// Validate that we have at least one video URL
		if (videoTags.length === 0) {
			setError(t("error_no_video"));
			return;
		}

		// Validate all URLs
		const invalidUrls = videoTags.filter((tag) => !isValidYoutubeUrl(tag.text));
		if (invalidUrls.length > 0) {
			setError(t("error_invalid_urls", { urls: invalidUrls.map((tag) => tag.text).join(", ") }));
			return;
		}

		setError(null);
		setIsSubmitting(true);

		try {
			toast(t("processing_toast"), {
				description: t("processing_toast_desc"),
			});

			// Extract URLs from tags
			const videoUrls = videoTags.map((tag) => tag.text);

			// Make API call to backend
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents`,
				{
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					body: JSON.stringify({
						document_type: "YOUTUBE_VIDEO",
						content: videoUrls,
						search_space_id: parseInt(search_space_id),
					}),
				}
			);

			if (!response.ok) {
				throw new Error("Failed to process YouTube videos");
			}

			await response.json();

			toast(t("success_toast"), {
				description: t("success_toast_desc"),
			});

			// Redirect to documents page
			router.push(`/dashboard/${search_space_id}/documents`);
		} catch (error: any) {
			setError(error.message || t("error_generic"));
			toast(t("error_toast"), {
				description: `${t("error_toast_desc")}: ${error.message}`,
			});
		} finally {
			setIsSubmitting(false);
		}
	};

	// Function to add a new video URL tag
	const handleAddTag = (text: string) => {
		// Basic URL validation
		if (!isValidYoutubeUrl(text)) {
			toast(t("invalid_url_toast"), {
				description: t("invalid_url_toast_desc"),
			});
			return;
		}

		// Check for duplicates
		if (videoTags.some((tag) => tag.text === text)) {
			toast(t("duplicate_url_toast"), {
				description: t("duplicate_url_toast_desc"),
			});
			return;
		}

		// Add the new tag
		const newTag: Tag = {
			id: Date.now().toString(),
			text: text,
		};

		setVideoTags([...videoTags, newTag]);
	};

	// Animation variants
	const containerVariants: Variants = {
		hidden: { opacity: 0 },
		visible: {
			opacity: 1,
			transition: {
				staggerChildren: 0.1,
			},
		},
	};

	const itemVariants: Variants = {
		hidden: { y: 20, opacity: 0 },
		visible: {
			y: 0,
			opacity: 1,
			transition: {
				type: "spring",
				stiffness: 300,
				damping: 24,
			},
		},
	};

	return (
		<div className="container mx-auto py-8">
			<motion.div initial="hidden" animate="visible" variants={containerVariants}>
				<Card className="max-w-2xl mx-auto">
					<motion.div variants={itemVariants}>
						<CardHeader>
							<CardTitle className="flex items-center gap-2">
								<IconBrandYoutube className="h-5 w-5" />
								{t("title")}
							</CardTitle>
							<CardDescription>{t("subtitle")}</CardDescription>
						</CardHeader>
					</motion.div>

					<motion.div variants={itemVariants}>
						<CardContent>
							<div className="space-y-4">
								<div className="space-y-2">
									<Label htmlFor="video-input">{t("label")}</Label>
									<TagInput
										id="video-input"
										tags={videoTags}
										setTags={setVideoTags}
										placeholder={t("placeholder")}
										onAddTag={handleAddTag}
										styleClasses={{
											inlineTagsContainer:
												"border-input rounded-lg bg-background shadow-sm shadow-black/5 transition-shadow focus-within:border-ring focus-within:outline-none focus-within:ring-[3px] focus-within:ring-ring/20 p-1 gap-1",
											input: "w-full min-w-[80px] focus-visible:outline-none shadow-none px-2 h-7",
											tag: {
												body: "h-7 relative bg-background border border-input hover:bg-background rounded-md font-medium text-xs ps-2 pe-7 flex",
												closeButton:
													"absolute -inset-y-px -end-px p-0 rounded-e-lg flex size-7 transition-colors outline-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring/70 text-muted-foreground/80 hover:text-foreground",
											},
										}}
										activeTagIndex={activeTagIndex}
										setActiveTagIndex={setActiveTagIndex}
									/>
									<p className="text-xs text-muted-foreground mt-1">{t("hint")}</p>
								</div>

								{error && (
									<motion.div
										className="text-sm text-red-500 mt-2"
										initial={{ opacity: 0, scale: 0.9 }}
										animate={{ opacity: 1, scale: 1 }}
										transition={{ type: "spring", stiffness: 500, damping: 30 }}
									>
										{error}
									</motion.div>
								)}

								<motion.div variants={itemVariants} className="bg-muted/50 rounded-lg p-4 text-sm">
									<h4 className="font-medium mb-2">{t("tips_title")}</h4>
									<ul className="list-disc pl-5 space-y-1 text-muted-foreground">
										<li>{t("tip_1")}</li>
										<li>{t("tip_2")}</li>
										<li>{t("tip_3")}</li>
										<li>{t("tip_4")}</li>
									</ul>
								</motion.div>

								{videoTags.length > 0 && (
									<motion.div variants={itemVariants} className="mt-4 space-y-2">
										<h4 className="font-medium">{t("preview")}:</h4>
										<div className="grid grid-cols-1 gap-3">
											{videoTags.map((tag, index) => {
												const videoId = extractVideoId(tag.text);
												return videoId ? (
													<motion.div
														key={tag.id}
														initial={{ opacity: 0, y: 10 }}
														animate={{ opacity: 1, y: 0 }}
														transition={{ delay: index * 0.1 }}
														className="relative aspect-video rounded-lg overflow-hidden border"
													>
														<iframe
															width="100%"
															height="100%"
															src={`https://www.youtube.com/embed/${videoId}`}
															title="YouTube video player"
															allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
															allowFullScreen
														></iframe>
													</motion.div>
												) : null;
											})}
										</div>
									</motion.div>
								)}
							</div>
						</CardContent>
					</motion.div>

					<motion.div variants={itemVariants}>
						<CardFooter className="flex justify-between">
							<Button
								variant="outline"
								onClick={() => router.push(`/dashboard/${search_space_id}/documents`)}
							>
								{t("cancel")}
							</Button>
							<Button
								onClick={handleSubmit}
								disabled={isSubmitting || videoTags.length === 0}
								className="relative overflow-hidden"
							>
								{isSubmitting ? (
									<>
										<Loader2 className="mr-2 h-4 w-4 animate-spin" />
										{t("processing")}
									</>
								) : (
									<>
										<motion.span
											initial={{ x: -5, opacity: 0 }}
											animate={{ x: 0, opacity: 1 }}
											transition={{ delay: 0.2 }}
											className="mr-2"
										>
											<IconBrandYoutube className="h-4 w-4" />
										</motion.span>
										{t("submit")}
									</>
								)}
								<motion.div
									className="absolute inset-0 bg-primary/10"
									initial={{ x: "-100%" }}
									animate={isSubmitting ? { x: "0%" } : { x: "-100%" }}
									transition={{ duration: 0.5, ease: "easeInOut" }}
								/>
							</Button>
						</CardFooter>
					</motion.div>
				</Card>
			</motion.div>
		</div>
	);
}
