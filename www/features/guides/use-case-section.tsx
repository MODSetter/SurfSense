import Link from "next/link";
import { HomeBadge } from "@/components/site/home-badge";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { GUIDES_URL } from "@/components/site/site-content";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { ArrowRightIcon } from "@/components/ui/icons";
import { HomeDownloadButton } from "@/features/downloads/home-download-button";
import { shownUseCases } from "./shown-use-cases";
import { UseCaseTabs } from "./use-case-tabs";
import type { UseCaseSlug } from "./use-cases";

/**
 * A band of use-case videos: a badge over a headline, a tab per use case with its video
 * and steps, then the download. The homepage and the For pages share it. The headline is
 * a `<p>` styled like an H2, so a page's H2s keep their count and order. Renders nothing
 * until one of its videos is hosted.
 */
export function UseCaseSection({
	badge,
	headline,
	slugs,
	placement,
}: {
	badge: string;
	headline: string;
	slugs: readonly UseCaseSlug[];
	placement: "home" | "for-page";
}) {
	const useCases = shownUseCases(slugs);
	if (useCases.length === 0) return null;
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>{badge}</HomeBadge>
				<p className={cn(siteText.h2, "mt-4")}>{headline}</p>
			</div>

			<div className="mt-10 lg:mt-14">
				<UseCaseTabs useCases={useCases} placement={placement} />
			</div>

			<div className="mt-10 flex flex-wrap items-center justify-center gap-x-8 gap-y-5 lg:mt-14">
				<HomeDownloadButton tone="dark" placement="use-case-video" />
				<Link className={siteText.forward} href={GUIDES_URL}>
					All step-by-step guides <ArrowRightIcon aria-hidden="true" className="size-4" />
				</Link>
			</div>
		</section>
	);
}
