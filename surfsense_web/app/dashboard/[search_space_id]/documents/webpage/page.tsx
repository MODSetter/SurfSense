"use client";

import { type Tag, TagInput } from "emblor";
import { Globe, Loader2 } from "lucide-react";
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

// URL validation regex
const urlRegex = /^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*\/?$/;

export default function WebpageCrawler() {
	const t = useTranslations("add_webpage");
	const params = useParams();
	const router = useRouter();
	const search_space_id = params.search_space_id as string;

	const [urlTags, setUrlTags] = useState<Tag[]>([]);
	const [activeTagIndex, setActiveTagIndex] = useState<number | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	// Function to validate a URL
	const isValidUrl = (url: string): boolean => {
		return urlRegex.test(url);
	};

	// Function to handle URL submission
	const handleSubmit = async () => {
		// Validate that we have at least one URL
		if (urlTags.length === 0) {
			setError(t("error_no_url"));
			return;
		}

		// Validate all URLs
		const invalidUrls = urlTags.filter((tag) => !isValidUrl(tag.text));
		if (invalidUrls.length > 0) {
			setError(t("error_invalid_urls", { urls: invalidUrls.map((tag) => tag.text).join(", ") }));
			return;
		}

		setError(null);
		setIsSubmitting(true);

		try {
			toast(t("crawling_toast"), {
				description: t("crawling_toast_desc"),
			});

			// Extract URLs from tags
			const urls = urlTags.map((tag) => tag.text);

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
						document_type: "CRAWLED_URL",
						content: urls,
						search_space_id: parseInt(search_space_id),
					}),
				}
			);

			if (!response.ok) {
				throw new Error("Failed to crawl URLs");
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

	// Function to add a new URL tag
	const handleAddTag = (text: string) => {
		// Basic URL validation
		if (!isValidUrl(text)) {
			toast(t("invalid_url_toast"), {
				description: t("invalid_url_toast_desc"),
			});
			return;
		}

		// Check for duplicates
		if (urlTags.some((tag) => tag.text === text)) {
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

		setUrlTags([...urlTags, newTag]);
	};

	return (
		<div className="container mx-auto py-8">
			<Card className="max-w-2xl mx-auto">
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<Globe className="h-5 w-5" />
						{t("title")}
					</CardTitle>
					<CardDescription>{t("subtitle")}</CardDescription>
				</CardHeader>
				<CardContent>
					<div className="space-y-4">
						<div className="space-y-2">
							<Label htmlFor="url-input">{t("label")}</Label>
							<TagInput
								id="url-input"
								tags={urlTags}
								setTags={setUrlTags}
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

						{error && <div className="text-sm text-red-500 mt-2">{error}</div>}

						<div className="bg-muted/50 rounded-lg p-4 text-sm">
							<h4 className="font-medium mb-2">{t("tips_title")}</h4>
							<ul className="list-disc pl-5 space-y-1 text-muted-foreground">
								<li>{t("tip_1")}</li>
								<li>{t("tip_2")}</li>
								<li>{t("tip_3")}</li>
								<li>{t("tip_4")}</li>
							</ul>
						</div>
					</div>
				</CardContent>
				<CardFooter className="flex justify-between">
					<Button
						variant="outline"
						onClick={() => router.push(`/dashboard/${search_space_id}/documents`)}
					>
						{t("cancel")}
					</Button>
					<Button onClick={handleSubmit} disabled={isSubmitting || urlTags.length === 0}>
						{isSubmitting ? (
							<>
								<Loader2 className="mr-2 h-4 w-4 animate-spin" />
								{t("submitting")}
							</>
						) : (
							t("submit")
						)}
					</Button>
				</CardFooter>
			</Card>
		</div>
	);
}
