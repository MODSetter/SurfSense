import featuresScene from "@/components/homepage/home/home-features/features-scene.webp";
import { GlassChip } from "@/components/homepage/home/home-features/glass-chip";
import { ScenePanel } from "@/components/homepage/home/home-features/scene-panel";
import {
	ArrowUp02Icon,
	File02Icon,
	PlusIcon,
	PodcastIcon,
	Presentation02Icon,
} from "@/components/ui/icons";

/** A prompt asking for an artifact, with the formats it could become above it. */
export function ArtifactsVisual() {
	return (
		<ScenePanel scene={featuresScene} position="center 45%">
			<div className="mx-5 flex max-w-md flex-col gap-3 rounded-3xl sm:mx-auto sm:w-full bg-black/20 p-3 backdrop-blur-sm sm:p-4">
				<div className="flex flex-wrap justify-center gap-1.5">
					<GlassChip icon={<PodcastIcon />} label="Podcast" />
					<GlassChip icon={<Presentation02Icon />} label="Slides" />
					<GlassChip icon={<File02Icon />} label="Report" />
				</div>
				<div className="flex items-center gap-2 rounded-full border border-white/25 bg-white/10 py-1.5 pr-1.5 pl-3 text-white">
					<PlusIcon className="size-4 shrink-0" />
					<span className="flex-1 truncate text-sm text-white/60">
						Turn these sources into a briefing
					</span>
					<span className="grid size-8 shrink-0 place-items-center rounded-full bg-white text-foreground">
						<ArrowUp02Icon className="size-4" />
					</span>
				</div>
			</div>
		</ScenePanel>
	);
}
