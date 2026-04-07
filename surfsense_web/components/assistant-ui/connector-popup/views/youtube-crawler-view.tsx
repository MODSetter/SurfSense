"use client";

import { TagInput, type Tag as TagType } from "emblor";
import { useAtom } from "jotai";
import { ArrowLeft, Info } from "lucide-react";
import { useTranslations } from "next-intl";
import { type FC, useCallback, useState } from "react";
import { toast } from "sonner";
import { createDocumentMutationAtom } from "@/atoms/documents/document-mutation.atoms";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { baseApiService } from "@/lib/apis/base-api.service";

const YOUTUBE_VIDEO_URL_RE =
	/(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/watch\?[^\s]*v=[\w-]{11}|youtu\.be\/[\w-]{11})[^\s]*/;

const YOUTUBE_PLAYLIST_URL_RE =
	/(?:https?:\/\/)?(?:www\.)?youtube\.com\/[^\s]*[?&]list=[\w-]+[^\s]*/;

const YOUTUBE_ANY_URL_RE =
	/(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch[^\s]*|playlist[^\s]*)|youtu\.be\/[\w-]+[^\s]*)/gi;

function isYoutubeVideoUrl(url: string): boolean {
	return YOUTUBE_VIDEO_URL_RE.test(url.trim());
}

function isYoutubePlaylistUrl(url: string): boolean {
	return YOUTUBE_PLAYLIST_URL_RE.test(url.trim());
}

function extractYoutubeUrls(text: string): string[] {
	const matches = text.match(YOUTUBE_ANY_URL_RE);
	return matches ? [...new Set(matches)] : [];
}

interface YouTubeCrawlerViewProps {
	searchSpaceId: string;
	onBack: () => void;
}

export const YouTubeCrawlerView: FC<YouTubeCrawlerViewProps> = ({ searchSpaceId, onBack }) => {
	const t = useTranslations("add_youtube");
	const [videoTags, setVideoTags] = useState<TagType[]>([]);
	const [activeTagIndex, setActiveTagIndex] = useState<number | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [isFetchingPlaylist, setIsFetchingPlaylist] = useState(false);

	const [createDocumentMutation] = useAtom(createDocumentMutationAtom);
	const { mutate: createYouTubeDocument, isPending: isSubmitting } = createDocumentMutation;

	const extractVideoId = (url: string): string | null => {
		const match = url.match(/(?:[?&]v=|youtu\.be\/)([\w-]{11})/);
		return match ? match[1] : null;
	};

	const resolvePlaylist = useCallback(
		async (url: string) => {
			setIsFetchingPlaylist(true);
			toast(t("resolving_playlist_toast"), {
				description: t("resolving_playlist_toast_desc"),
			});

			try {
				const response = (await baseApiService.get(
					`/api/v1/youtube/playlist-videos?url=${encodeURIComponent(url)}`
				)) as { video_urls: string[]; count: number };

				const resolvedUrls: string[] = response.video_urls ?? [];

				setVideoTags((prev) => {
					const existingTexts = new Set(prev.map((tag) => tag.text));
					const newTags = resolvedUrls
						.filter((vUrl) => !existingTexts.has(vUrl))
						.map((vUrl) => ({
							id: `${Date.now()}-${Math.random()}`,
							text: vUrl,
						}));
					return newTags.length > 0 ? [...prev, ...newTags] : prev;
				});

				toast(t("playlist_resolved_toast"), {
					description: t("playlist_resolved_toast_desc", { count: resolvedUrls.length }),
				});
			} catch (err) {
				const message = err instanceof Error ? err.message : t("error_generic");
				toast(t("playlist_error_toast"), { description: message });
			} finally {
				setIsFetchingPlaylist(false);
			}
		},
		[t]
	);

	const handlePaste = useCallback(
		async (e: React.ClipboardEvent<HTMLDivElement>) => {
			const text = e.clipboardData.getData("text/plain");
			if (!text) return;

			const urls = extractYoutubeUrls(text);
			if (urls.length === 0) return;

			e.preventDefault();

			const playlistUrls: string[] = [];
			const videoUrls: string[] = [];

			for (const url of urls) {
				if (isYoutubePlaylistUrl(url)) {
					playlistUrls.push(url);
				} else if (isYoutubeVideoUrl(url)) {
					videoUrls.push(url);
				}
			}

			if (videoUrls.length > 0) {
				setVideoTags((prev) => {
					const existingTexts = new Set(prev.map((tag) => tag.text));
					const newTags = videoUrls
						.filter((url) => !existingTexts.has(url.trim()))
						.map((url) => ({
							id: `${Date.now()}-${Math.random()}`,
							text: url.trim(),
						}));
					if (newTags.length === 0) {
						toast(t("duplicate_url_toast"), {
							description: t("duplicate_url_toast_desc"),
						});
					}
					return newTags.length > 0 ? [...prev, ...newTags] : prev;
				});
			}

			for (const url of playlistUrls) {
				await resolvePlaylist(url);
			}
		},
		[resolvePlaylist, t]
	);

	const handleSubmit = async () => {
		if (videoTags.length === 0) {
			setError(t("error_no_video"));
			return;
		}

		const invalidUrls = videoTags.filter((tag) => !isYoutubeVideoUrl(tag.text));
		if (invalidUrls.length > 0) {
			setError(t("error_invalid_urls", { urls: invalidUrls.map((tag) => tag.text).join(", ") }));
			return;
		}

		setError(null);

		toast(t("processing_toast"), {
			description: t("processing_toast_desc"),
		});

		const videoUrls = videoTags.map((tag) => tag.text);

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
					onBack();
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
		if (isYoutubePlaylistUrl(text)) {
			resolvePlaylist(text);
			return;
		}

		if (!isYoutubeVideoUrl(text)) {
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
			<div className="shrink-0 px-6 sm:px-12 pt-8 sm:pt-10">
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
						{/* Wrapper intercepts paste events for auto-detection of YouTube URLs */}
						<div onPasteCapture={handlePaste}>
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
						</div>
						<p className="text-xs text-muted-foreground mt-1">{t("hint")}</p>
					</div>

					{isFetchingPlaylist && (
						<div className="flex items-center gap-2 text-sm text-muted-foreground">
							<Spinner size="sm" />
							<span>{t("resolving_playlist")}</span>
						</div>
					)}

					{error && <div className="text-sm text-red-500 mt-2">{error}</div>}

					<div className="flex items-start gap-3 rounded-lg border border-blue-200/50 bg-blue-50/50 dark:border-blue-500/20 dark:bg-blue-950/20 p-4 text-sm">
						<Info className="size-4 mt-0.5 shrink-0 text-blue-600 dark:text-blue-400" />
						<p className="text-muted-foreground">{t("chat_tip")}</p>
					</div>

					<div className="bg-muted/50 rounded-lg p-4 text-sm">
						<h4 className="font-medium mb-2">{t("tips_title")}</h4>
						<ul className="list-disc pl-5 space-y-1 text-muted-foreground">
							<li>{t("tip_1")}</li>
							<li>{t("tip_2")}</li>
							<li>{t("tip_3")}</li>
							<li>{t("tip_4")}</li>
							<li>{t("tip_5")}</li>
						</ul>
					</div>

					{videoTags.length > 0 && videoTags.length <= 3 && (
						<div className="mt-4 space-y-2">
							<h4 className="font-medium">{t("preview")}:</h4>
							<div className="grid grid-cols-1 gap-3">
								{videoTags.map((tag) => {
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
			<div className="shrink-0 flex items-center justify-between px-6 sm:px-12 py-6 bg-muted border-t border-border">
				<Button
					variant="ghost"
					onClick={onBack}
					disabled={isSubmitting || isFetchingPlaylist}
					className="text-xs sm:text-sm"
				>
					{t("cancel")}
				</Button>
				<Button
					onClick={handleSubmit}
					disabled={isSubmitting || isFetchingPlaylist || videoTags.length === 0}
					className="relative text-xs sm:text-sm min-w-[140px] disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none"
				>
					<span className={isSubmitting ? "opacity-0" : ""}>{t("submit")}</span>
					{isSubmitting && <Spinner size="sm" className="absolute" />}
				</Button>
			</div>
		</div>
	);
};
