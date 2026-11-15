import { USE_CASES } from "@/app/(home)/_home/home-content";
import { UseCaseSection } from "@/features/guides/use-case-section";

/**
 * Use-case videos: a tab per job SurfSense does, each video beside its steps, then the
 * download. Sits under the logos, so the first thing past the hero is the app at work.
 * See `USE_CASES` in `home-content.ts`.
 */
export function HomeUseCases() {
	return (
		<UseCaseSection
			badge={USE_CASES.eyebrow}
			headline={USE_CASES.headline}
			slugs={USE_CASES.slugs}
			placement="home"
		/>
	);
}
