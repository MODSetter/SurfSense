import type { ReactNode } from "react";
import { FEATURES } from "@/app/(home)/_home/home-content";
import { FeatureRow } from "@/app/(home)/_home/home-features/feature-row";
import { ArtifactsVisual } from "@/app/(home)/_home/home-features/visuals/artifacts-visual";
import { PluginsVisual } from "@/app/(home)/_home/home-features/visuals/plugins-visual";
import { PrivateVisual } from "@/app/(home)/_home/home-features/visuals/private-visual";
import { HomeBadge } from "@/components/site/home-badge";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";

const VISUALS: Record<(typeof FEATURES)[number]["key"], ReactNode> = {
	artifacts: <ArtifactsVisual />,
	plugins: <PluginsVisual />,
	private: <PrivateVisual />,
};

/**
 * "What you get": three rows, each a claim beside a mock-up on a painted
 * scene. The headline is a `<p>` because the three real H2s are the rows'.
 */
export function HomeFeatures() {
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>What you get</HomeBadge>
				<p className={cn(siteText.h2, "mt-4")}>Three things worth knowing before you install</p>
			</div>

			<div className="mt-10 flex flex-col gap-5 lg:mt-14">
				{FEATURES.map((feature, index) => (
					<FeatureRow
						key={feature.key}
						feature={feature}
						visual={VISUALS[feature.key]}
						flip={index % 2 === 1}
					/>
				))}
			</div>
		</section>
	);
}
