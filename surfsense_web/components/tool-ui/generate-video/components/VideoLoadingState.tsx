import { VideoIcon } from "lucide-react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";

interface VideoLoadingStateProps {
	topic: string;
}

export function VideoLoadingState({ topic }: VideoLoadingStateProps) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-card">
			<div className="flex w-full items-center gap-2 sm:gap-3 bg-muted/30 px-4 py-5 sm:px-6 sm:py-6">
				<div className="flex size-8 sm:size-12 shrink-0 items-center justify-center rounded-lg bg-primary/10">
					<VideoIcon className="size-4 sm:size-6 text-primary" />
				</div>
				<div className="min-w-0 flex-1">
					<h3 className="font-semibold text-foreground text-sm sm:text-base leading-tight line-clamp-2">
						{topic}
					</h3>
					<TextShimmerLoader text="Generating video" size="sm" />
				</div>
			</div>
		</div>
	);
}
