import { GUIDES_URL } from "@/components/site/site-content";
import { guidePoster, guideVideoSource, roughLength } from "./guide-video-source";
import { findUseCase, type UseCase, type UseCaseSlug } from "./use-cases";

export type ShownUseCase = UseCase & {
	src: string;
	poster: string;
	/** "Video, about 20 seconds, no sound." */
	caption: string;
	guideHref: string;
};

/**
 * The use cases whose videos are hosted, in the order asked. One whose video isn't
 * uploaded yet stays off the page, so a section with none renders nothing.
 */
export function shownUseCases(slugs: readonly UseCaseSlug[]): ShownUseCase[] {
	return slugs.flatMap((slug) => {
		const video = guideVideoSource(slug);
		if (!video) return [];
		const length = video.seconds ? `, ${roughLength(video.seconds)}` : "";
		return [
			{
				...findUseCase(slug),
				src: video.src,
				poster: guidePoster(slug),
				caption: `Video${length}, no sound.`,
				guideHref: `${GUIDES_URL}/${slug}`,
			},
		];
	});
}
