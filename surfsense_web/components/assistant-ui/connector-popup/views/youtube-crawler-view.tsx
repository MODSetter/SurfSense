"use client";

import { TagInput, type Tag as TagType } from "emblor";
import { useAtom } from "jotai";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { type FC, useState } from "react";
import { toast } from "sonner";
import { createDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";

const youtubeRegex =
	/^(https:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})$/;

interface YouTubeCrawlerViewProps {
	searchSpaceId: string;
	onBack: () => void;
}

export const YouTubeCrawlerView: FC<YouTubeCrawlerViewProps> = ({ searchSpaceId, onBack }) => {
	const t = useTranslations("add_youtube");
	const router = useRouter();
	const [videoTags, setVideoTags] = useState<TagType[]>([]);
	const [activeTagIndex, setActiveTagIndex] = useState<number | null>(null);
	const [error, setError] = useState<string | null>(null);

	// Use the createDocumentMutationAtom
	const [createDocumentMutation] = useAtom(createDocumentMutationAtom);
	const { mutate: createYouTubeDocument, isPending: isSubmitting } = createDocumentMutation;

	const isValidYoutubeUrl = (url: string): boolean => {
		return youtubeRegex.test(url);
	};

	const extractVideoId = (url: string): string | null => {
		const match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
		return match ? match[1] : null;
	};

	const handleSubmit = async () => {
		if (videoTags.length === 0) {
			setError(t("error_no_video"));
			return;
		}

		const invalidUrls = videoTags.filter((tag) => !isValidYoutubeUrl(tag.text));
		if (invalidUrls.length > 0) {
			setError(t("error_invalid_urls", { urls: invalidUrls.map((tag) => tag.text).join(", ") }));
			return;
		}

		setError(null);

		toast(t("processing_toast"), {
			description: t("processing_toast_desc"),
		});

		const videoUrls = videoTags.map((tag) => tag.text);

		// Use the mutation to create YouTube documents
		createYouTubeDocument(
			{
				document_type: "YOUTUBE_VIDEO",
				content: videoUrls,
				search_space_id: parseInt(searchSpaceId, 10),
			},
			{
				onSuccess: () => {
					toast(t("success_toast"), {
						description: t("success_toast_desc"),
					});
					// Close the popup and navigate to documents
					onBack();
					router.push(`/dashboard/${searchSpaceId}/documents`);
				},
				onError: (error: unknown) => {
					const errorMessage = error instanceof Error ? error.message : t("error_generic");
					setError(errorMessage);
					toast(t("error_toast"), {
						description: `${t("error_toast_desc")}: ${errorMessage}`,
					});
				},
			}
		);
	};

	const handleAddTag = (text: string) => {
		if (!isValidYoutubeUrl(text)) {
			toast(t("invalid_url_toast"), {
				description: t("invalid_url_toast_desc"),
			});
			return;
		}

		if (videoTags.some((tag) => tag.text === text)) {
			toast(t("duplicate_url_toast"), {
				description: t("duplicate_url_toast_desc"),
			});
			return;
		}

		const newTag: TagType = {
			id: Date.now().toString(),
			text: text,
		};

		setVideoTags([...videoTags, newTag]);
	};

	return (
		<div className="flex-1 flex flex-col min-h-0 overflow-hidden">
			{/* Header */}
			<div className="flex-shrink-0 px-6 sm:px-12 pt-8 sm:pt-10">
				<button
					type="button"
					onClick={onBack}
					className="flex items-center gap-2 text-xs sm:text-sm text-muted-foreground hover:text-foreground mb-6 w-fit"
				>
					<ArrowLeft className="size-4" />
					Back to connectors
				</button>

				<div className="flex items-center gap-4 mb-6">
					<div className="flex h-14 w-14 items-center justify-center rounded-xl border border-slate-400/30">
						{getConnectorIcon(EnumConnectorName.YOUTUBE_CONNECTOR, "h-7 w-7")}
					</div>
					<div>
						<h2 className="text-xl sm:text-2xl font-semibold tracking-tight">{t("title")}</h2>
						<p className="text-xs sm:text-base text-muted-foreground mt-1">{t("subtitle")}</p>
					</div>
				</div>
			</div>

			{/* Form Content - Scrollable */}
			<div className="flex-1 min-h-0 overflow-y-auto px-6 sm:px-12">
				<div className="space-y-4 pb-6">
					<div className="space-y-2">
						<Label htmlFor="video-input" className="text-sm sm:text-base">
							{t("label")}
						</Label>
						<TagInput
							id="video-input"
							tags={videoTags}
							setTags={setVideoTags}
							placeholder={t("placeholder")}
							onAddTag={handleAddTag}
							styleClasses={{
								inlineTagsContainer:
									"border border-slate-400/20 rounded-lg bg-muted/50 shadow-sm shadow-black/5 transition-shadow focus-within:border-slate-400/40 focus-within:outline-none focus-within:ring-[3px] focus-within:ring-ring/20 p-1 gap-1",
								input:
									"w-full min-w-[80px] focus-visible:outline-none shadow-none px-2 h-7 text-foreground/90 placeholder:text-muted-foreground bg-transparent",
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

					{videoTags.length > 0 && (
						<div className="mt-4 space-y-2">
							<h4 className="font-medium">{t("preview")}:</h4>
							<div className="grid grid-cols-1 gap-3">
								{videoTags.map((tag, _index) => {
									const videoId = extractVideoId(tag.text);
									return videoId ? (
										<div
											key={tag.id}
											className="relative aspect-video rounded-lg overflow-hidden border"
										>
											<iframe
												width="100%"
												height="100%"
												src={`https://www.youtube.com/embed/${videoId}`}
												title="YouTube video player"
												allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
												allowFullScreen
											/>
										</div>
									) : null;
								})}
							</div>
						</div>
					)}
				</div>
			</div>

			{/* Fixed Footer - Action buttons */}
			<div className="flex-shrink-0 flex items-center justify-between px-6 sm:px-12 py-6 bg-muted border-t border-border">
				<Button
					variant="ghost"
					onClick={onBack}
					disabled={isSubmitting}
					className="text-xs sm:text-sm"
				>
					{t("cancel")}
				</Button>
				<Button
					onClick={handleSubmit}
					disabled={isSubmitting || videoTags.length === 0}
					className="text-xs sm:text-sm min-w-[140px] disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none"
				>
					{isSubmitting ? (
						<>
							<Spinner size="sm" className="mr-2" />
							{t("processing")}
						</>
					) : (
						t("submit")
					)}
				</Button>
			</div>
		</div>
	);
};
