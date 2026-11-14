import Link from "next/link";
import { AUDIENCES, type AudienceCard, JOBS_STRIP } from "@/app/(home)/_home/home-content";
import { HomeBadge } from "@/components/site/home-badge";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import {
	ArrowRightIcon,
	Briefcase01Icon,
	Calculator01Icon,
	type Icon,
	JusticeScale01Icon,
	Mortarboard01Icon,
	TeacherIcon,
} from "@/components/ui/icons";

/**
 * Who it's for: a card per reader, each linking the page written for them, with the paid
 * jobs in a strip below. Sits under the use-case videos so a visitor can pick their page
 * before the argument starts. See `AUDIENCES` in `home-content.ts`.
 */

const ICONS: Record<AudienceCard["key"], Icon> = {
	lawyers: JusticeScale01Icon,
	accountants: Calculator01Icon,
	students: Mortarboard01Icon,
	teachers: TeacherIcon,
	business: Briefcase01Icon,
};

const CARDS = AUDIENCES.cards;

/** Five cards fill two rows evenly on six columns: three, then two wider. */
function cardSpan(index: number, count: number) {
	if (count !== 5) return "md:col-span-2";
	return index < 3 ? "md:col-span-2" : "md:col-span-3";
}

export function HomeAudiences() {
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>{AUDIENCES.eyebrow}</HomeBadge>
				<p className={cn(siteText.h2, "mt-4")}>{AUDIENCES.headline}</p>
			</div>

			<ul className="m-0 mt-10 grid list-none gap-4 p-0 md:grid-cols-6 lg:mt-14">
				{CARDS.map((card, index) => {
					const CardIcon = ICONS[card.key];
					return (
						<li
							key={card.key}
							className={cn(
								"flex flex-col rounded-2xl border border-border bg-card p-6 shadow-xs md:p-8",
								cardSpan(index, CARDS.length)
							)}
						>
							<span
								aria-hidden="true"
								className="grid size-11 place-items-center rounded-xl bg-secondary text-foreground"
							>
								<CardIcon className="size-5" />
							</span>
							<h3 className={cn(siteText.h3, "mt-6")}>{card.title}</h3>
							<p className={cn(siteText.body, "mt-2 text-sm")}>{card.body}</p>
							<p className="mt-auto pt-5">
								<Link className={siteText.forward} href={card.action.href}>
									{card.action.label} <ArrowRightIcon aria-hidden="true" className="size-4" />
								</Link>
							</p>
						</li>
					);
				})}
			</ul>

			<div className="mt-4 flex flex-col gap-4 rounded-3xl bg-muted px-6 py-6 sm:flex-row sm:items-center sm:justify-between md:px-8">
				<p className={cn(siteText.body, "text-sm")}>{JOBS_STRIP.body}</p>
				<div className="flex flex-wrap gap-x-6 gap-y-2">
					{JOBS_STRIP.actions.map((action) => (
						<Link key={action.href} className={siteText.forward} href={action.href}>
							{action.label} <ArrowRightIcon aria-hidden="true" className="size-4" />
						</Link>
					))}
				</div>
			</div>
		</section>
	);
}
