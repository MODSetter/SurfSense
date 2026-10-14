import Image from "next/image";
import Link from "next/link";
import { siteText } from "@/components/site/site-text";
import { ArrowRightIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

/**
 * A numbered walkthrough in the site design: one rounded card per step, prose
 * on one side and that step's screenshot on the other, in the homepage's
 * "What you get" row shape.
 *
 * Shared by `/sunset` and `/license/activate` so the two guides stay the same
 * page shape. Both hold the same kind of instruction and a reader may well
 * follow one after the other.
 *
 * `shot` is optional, and a step without one runs its prose across the whole
 * card rather than beside an empty half. Steps whose action is on this site
 * rather than in the app tend not to want a picture: a screenshot of a button
 * already on screen only shows the reader what they can see.
 */

export type GuideStep = {
	title: string;
	body: React.ReactNode;
	/** Rendered under the body, for a step whose control lives on the page. */
	control?: React.ReactNode;
	action?: { href: string; label: string };
	shot?: { src: string; alt: string; width: number; height: number };
};

export function GuideSteps({ steps }: { steps: GuideStep[] }) {
	return (
		<ol className="m-0 flex list-none flex-col gap-4 p-0">
			{steps.map((step, index) => (
				<li
					key={step.title}
					className="flex flex-col overflow-hidden rounded-3xl bg-muted p-2 lg:flex-row"
				>
					<div
						className={cn(
							"flex flex-col justify-center p-6 md:p-10",
							step.shot ? "lg:w-1/2" : "flex-1"
						)}
					>
						<span className="grid size-8 place-items-center rounded-full bg-foreground font-mono text-xs text-background">
							{index + 1}
						</span>
						<h3 className={cn(siteText.h3, "mt-5")}>{step.title}</h3>
						<p className={cn(siteText.body, "mt-3 max-w-xl")}>{step.body}</p>
						{step.control}
						{step.action ? (
							<p className="mt-5">
								<Link className={siteText.forward} href={step.action.href}>
									{step.action.label} <ArrowRightIcon aria-hidden="true" className="size-4" />
								</Link>
							</p>
						) : null}
					</div>

					{/* Capped at half its pixel width, because the shots are taken at a
					    device scale factor of 2: left to fill the half, the smaller ones (a
					    dialog, a single settings row) would be drawn above their own
					    resolution and land soft on a retina screen. */}
					{step.shot ? (
						<div className="flex items-center justify-center rounded-2xl bg-card p-6 md:p-10 lg:w-1/2">
							<Image
								src={step.shot.src}
								alt={step.shot.alt}
								width={step.shot.width}
								height={step.shot.height}
								style={{ maxWidth: step.shot.width / 2 }}
								draggable={false}
								className="h-auto w-full rounded-xl border border-border shadow-xs select-none"
							/>
						</div>
					) : null}
				</li>
			))}
		</ol>
	);
}
