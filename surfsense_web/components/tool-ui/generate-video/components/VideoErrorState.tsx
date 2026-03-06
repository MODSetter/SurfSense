import { VideoIcon } from "lucide-react";

interface VideoErrorStateProps {
	title: string;
	error: string;
}

export function VideoErrorState({ title, error }: VideoErrorStateProps) {
	return (
		<div className="my-4 overflow-hidden rounded-xl border bg-card">
			<div className="flex items-center gap-2 sm:gap-3 bg-muted/30 px-4 py-5 sm:px-6 sm:py-6">
				<div className="flex size-8 sm:size-12 shrink-0 items-center justify-center rounded-lg bg-muted/60">
					<VideoIcon className="size-4 sm:size-6 text-muted-foreground" />
				</div>
				<div className="min-w-0 flex-1">
					<h3 className="font-semibold text-muted-foreground text-sm sm:text-base leading-tight line-clamp-2">
						{title}
					</h3>
					<p className="text-muted-foreground/60 text-[11px] sm:text-xs mt-0.5 line-clamp-2">
						{error}
					</p>
				</div>
			</div>
		</div>
	);
}
