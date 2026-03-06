import { VideoIcon } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";

type VideoStep = "generating_script" | "rendering" | "running";

interface VideoLoadingStateProps {
	topic: string;
	step?: VideoStep;
	progress?: number;
}

const STEP_LABELS: Record<VideoStep, string> = {
	running: "Preparing video generation...",
	generating_script: "Generating video script with AI...",
	rendering: "Rendering video...",
};

export function VideoLoadingState({ topic, step = "running", progress }: VideoLoadingStateProps) {
	const label = STEP_LABELS[step];
	const showProgress = step === "rendering" && progress !== undefined;

	return (
		<div className="my-4 overflow-hidden rounded-xl border border-primary/20 bg-gradient-to-br from-primary/5 to-primary/10 p-4 sm:p-6">
			<div className="flex items-center gap-3 sm:gap-4">
				<div className="relative shrink-0">
					<div className="flex size-12 sm:size-16 items-center justify-center rounded-full bg-primary/20">
						<VideoIcon className="size-6 sm:size-8 text-primary" />
					</div>
					{!showProgress && (
						<div className="absolute inset-1 animate-ping rounded-full bg-primary/20" />
					)}
				</div>
				<div className="flex-1 min-w-0">
					<h3 className="font-semibold text-foreground text-sm sm:text-lg leading-tight line-clamp-2">
						{topic}
					</h3>
					<div className="mt-1.5 sm:mt-2 flex items-center gap-1.5 sm:gap-2 text-muted-foreground">
						<Spinner size="sm" className="size-3 sm:size-4" />
						<span className="text-xs sm:text-sm">{label}</span>
					</div>
					{showProgress && (
						<div className="mt-2 sm:mt-3">
							<div className="h-1 sm:h-1.5 w-full overflow-hidden rounded-full bg-primary/10">
								<div
									className="h-full rounded-full bg-primary transition-all duration-500"
									style={{ width: `${Math.round(progress * 100)}%` }}
								/>
							</div>
							<p className="text-muted-foreground text-[10px] sm:text-xs mt-1 text-right">
								{Math.round(progress * 100)}%
							</p>
						</div>
					)}
					{!showProgress && (
						<div className="mt-2 sm:mt-3">
							<div className="h-1 sm:h-1.5 w-full overflow-hidden rounded-full bg-primary/10">
								<div className="h-full w-1/3 animate-pulse rounded-full bg-primary" />
							</div>
						</div>
					)}
				</div>
			</div>
		</div>
	);
}
