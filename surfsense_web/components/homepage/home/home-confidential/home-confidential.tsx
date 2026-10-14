import Image from "next/image";
import Link from "next/link";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import meadow from "@/components/homepage/home/home-confidential/confidential-meadow.png";
import { CONFIDENTIAL } from "@/components/homepage/home/home-content";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { siteText } from "@/components/site/site-text";
import { ArrowRightIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

/**
 * H2 #8 — follows H2 #7 (*Private by construction*) because it answers the
 * question that one raises: privacy for whom. One banner, not a section,
 * because the business page makes the full argument.
 */
export function HomeConfidential() {
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>{CONFIDENTIAL.eyebrow}</HomeBadge>
				<h2 className={cn(siteText.h2, "mt-4")}>{CONFIDENTIAL.heading}</h2>
			</div>

			<div className="relative isolate mt-10 overflow-hidden rounded-[2rem] border border-border bg-white lg:mt-14">
				{/* The hill overflows the card by a fifth, which clips away most of the cut
				    edge the image has on its left, as the inspiration does. */}
				<Image
					src={meadow}
					alt=""
					aria-hidden="true"
					sizes="(max-width: 639px) 100vw, 900px"
					className="pointer-events-none absolute right-0 bottom-0 -z-10 w-full max-w-none translate-y-[30%] select-none sm:h-[125%] sm:w-auto"
				/>

				<div className="flex flex-col items-start gap-8 px-6 pt-8 pb-20 sm:pb-48 md:px-12 md:py-12 lg:flex-row lg:items-center lg:justify-between">
					<p className={cn(siteText.body, "max-w-2xl text-foreground/75 md:text-lg")}>
						{CONFIDENTIAL.body}
					</p>
					<Link
						href={CONFIDENTIAL.action.href}
						className="group inline-flex h-12 shrink-0 items-center gap-2.5 rounded-full bg-foreground pr-1.5 pl-6 text-sm font-semibold text-background shadow-lg transition-colors duration-150 hover:bg-foreground/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
					>
						{CONFIDENTIAL.action.label}
						<span className="grid size-9 place-items-center rounded-full bg-background text-foreground">
							<ArrowRightIcon
								aria-hidden="true"
								className="size-4 transition-transform duration-150 group-hover:translate-x-0.5 motion-reduce:transition-none"
							/>
						</span>
					</Link>
				</div>
			</div>
		</section>
	);
}
