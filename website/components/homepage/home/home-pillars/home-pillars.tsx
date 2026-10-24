import type { ReactNode } from "react";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { PILLARS } from "@/components/homepage/home/home-content";
import { PillarCard } from "@/components/homepage/home/home-pillars/pillar-card";
import { InstallerPreview } from "@/components/homepage/home/home-pillars/previews/installer-preview";
import { ModelPreview } from "@/components/homepage/home/home-pillars/previews/model-preview";
import { NoAccountPreview } from "@/components/homepage/home/home-pillars/previews/no-account-preview";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/lib/utils";

// In `PILLARS` order: no account, own model, installer.
const PREVIEWS: ReactNode[] = [
	<NoAccountPreview key="account" />,
	<ModelPreview key="model" />,
	<InstallerPreview key="install" />,
];

/**
 * H2 #2, #3, #4 as three cards. The headline is a `<p>` styled like an H2,
 * because the three real H2s are the card titles and a fourth would leave the
 * section carrying two.
 */
export function HomePillars() {
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Why it is different</HomeBadge>
				<p className={cn(siteText.h2, "mt-4")}>Three things NotebookLM cannot do</p>
			</div>

			<div className="mt-10 grid gap-4 md:grid-cols-3 lg:mt-14">
				{PILLARS.map((pillar, index) => (
					<PillarCard key={pillar.title} pillar={pillar} preview={PREVIEWS[index]} />
				))}
			</div>
		</section>
	);
}
