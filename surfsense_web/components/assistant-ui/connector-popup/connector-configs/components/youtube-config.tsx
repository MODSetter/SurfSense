"use client";

import { IconBrandYoutube } from "@tabler/icons-react";
import { Info } from "lucide-react";
import { TagInput, type Tag as TagType } from "emblor";
import { useState, useEffect } from "react";
import type { FC } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import type { ConnectorConfigProps } from "../index";

const youtubeRegex =
	/^(https:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})$/;

export const YouTubeConfig: FC<ConnectorConfigProps> = ({
	connector,
	onConfigChange,
}) => {
	// Initialize with existing YouTube URLs from connector config
	const existingUrls = (connector.config?.youtube_urls as string[] | undefined) || [];
	const [youtubeTags, setYoutubeTags] = useState<TagType[]>(
		existingUrls.map((url) => ({
			id: url,
			text: url,
		}))
	);
	const [activeTagIndex, setActiveTagIndex] = useState<number | null>(null);

	// Update YouTube tags when connector config changes
	useEffect(() => {
		const urls = (connector.config?.youtube_urls as string[] | undefined) || [];
		setYoutubeTags(
			urls.map((url) => ({
				id: url,
				text: url,
			}))
		);
	}, [connector.config]);

	const isValidYoutubeUrl = (url: string): boolean => {
		return youtubeRegex.test(url);
	};

	const handleTagsChange = (tags: TagType[]) => {
		setYoutubeTags(tags);
		if (onConfigChange) {
			// Extract URLs from tags and validate
			const urls = tags.map((tag) => tag.text).filter(isValidYoutubeUrl);
			onConfigChange({
				...connector.config,
				youtube_urls: urls,
			});
		}
	};

	const handleAddTag = (text: string) => {
		if (!isValidYoutubeUrl(text)) {
			toast("Invalid YouTube URL", {
				description: "Please enter a valid YouTube video URL (youtube.com/watch?v= or youtu.be/)",
			});
			return;
		}

		if (youtubeTags.some((tag) => tag.text === text)) {
			toast("Duplicate URL", {
				description: "This YouTube video has already been added",
			});
			return;
		}

		const newTag: TagType = {
			id: Date.now().toString(),
			text: text,
		};

		handleTagsChange([...youtubeTags, newTag]);
	};

	return (
		<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
			<div className="space-y-1 sm:space-y-2">
				<h3 className="font-medium text-sm sm:text-base flex items-center gap-2">
					<IconBrandYoutube className="h-4 w-4" />
					YouTube Video URLs
				</h3>
				<p className="text-xs sm:text-sm text-muted-foreground">
					Add YouTube video URLs to index. Enter a URL and press Enter to add multiple videos.
				</p>
			</div>

			<div className="space-y-2">
				<Label htmlFor="youtube-urls" className="text-xs sm:text-sm">
					Enter YouTube Video URLs
				</Label>
				<TagInput
					id="youtube-urls"
					tags={youtubeTags}
					setTags={handleTagsChange}
					placeholder="Enter a YouTube URL and press Enter"
					onAddTag={handleAddTag}
					styleClasses={{
						inlineTagsContainer:
							"border-input rounded-lg bg-background shadow-sm shadow-black/5 transition-shadow focus-within:border-ring focus-within:outline-none focus-within:ring-[3px] focus-within:ring-ring/20 p-1 gap-1",
						input: "w-full min-w-[80px] focus-visible:outline-none shadow-none px-2 h-7 text-xs sm:text-sm",
						tag: {
							body: "h-7 relative bg-background border border-input hover:bg-background rounded-md font-medium text-xs ps-2 pe-7 flex",
							closeButton:
								"absolute -inset-y-px -end-px p-0 rounded-e-lg flex size-7 transition-colors outline-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring/70 text-muted-foreground/80 hover:text-foreground",
						},
					}}
					activeTagIndex={activeTagIndex}
					setActiveTagIndex={setActiveTagIndex}
				/>
				<p className="text-[10px] sm:text-xs text-muted-foreground">
					Add multiple YouTube URLs by pressing Enter after each one
				</p>
			</div>

			{youtubeTags.length > 0 && (
				<div className="p-2 sm:p-3 bg-muted rounded-lg text-xs sm:text-sm space-y-1 sm:space-y-2">
					<p className="font-medium">
						{youtubeTags.length} video{youtubeTags.length > 1 ? "s" : ""} added
					</p>
				</div>
			)}

			<div className="bg-muted/50 rounded-lg p-3 sm:p-4 text-xs sm:text-sm">
				<h4 className="font-medium mb-2">Tips for adding YouTube videos:</h4>
				<ul className="list-disc pl-5 space-y-1 text-muted-foreground">
					<li>Use standard YouTube URLs (youtube.com/watch?v= or youtu.be/)</li>
					<li>Make sure videos are publicly accessible</li>
					<li>Supported formats: youtube.com/watch?v=VIDEO_ID or youtu.be/VIDEO_ID</li>
					<li>Processing may take some time depending on video length</li>
				</ul>
			</div>

			<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 p-2 sm:p-3 flex items-center gap-2 [&>svg]:relative [&>svg]:left-0 [&>svg]:top-0 [&>svg+div]:translate-y-0">
				<Info className="h-3 w-3 sm:h-4 sm:w-4 shrink-0" />
				<AlertDescription className="text-[10px] sm:text-xs !pl-0">
					YouTube URLs are used when indexing. You can change this selection when you start indexing.
				</AlertDescription>
			</Alert>
		</div>
	);
};

