import Link from "next/link";
import type { ReactNode } from "react";
import {
	CALL_URL,
	CHANNELS,
	type Channel,
	DISCUSSIONS_URL,
	EMAIL,
} from "@/components/contact/contact-content";
import { HomeBadge } from "@/components/homepage/home/home-badge";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { DiscordLogo } from "@/components/homepage/icons/discord-logo";
import { GithubLogo } from "@/components/homepage/icons/github-logo";
import { siteText } from "@/components/site/site-text";
import { ArrowUpRight01Icon, Calendar03Icon, Mail01Icon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

/**
 * Contact sections, in the homepage's shapes: centred badge heads, rounded
 * cards and the dark pill the homepage banners use. No motion beyond instant
 * hover colours.
 *
 * All server components. The page it replaced was a client component carrying
 * `motion`, an animated map pin and a world map SVG, none of which said
 * anything about how to reach us.
 */

const PILL =
	"inline-flex h-12 shrink-0 items-center gap-2 rounded-full bg-foreground px-6 text-sm font-semibold text-background shadow-lg hover:bg-foreground/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring";

// In `CHANNELS` order: call, email, issue, community.
const CHANNEL_ICONS: ReactNode[] = [
	<Calendar03Icon key="call" className="size-5" />,
	<Mail01Icon key="email" className="size-5" />,
	<GithubLogo key="issue" className="size-5" />,
	<DiscordLogo key="discord" className="size-5" />,
];

export function ContactHero() {
	return (
		<section className={cn("text-center", sectionSpacing.head)}>
			<HomeBadge>Contact</HomeBadge>
			<h1 className={cn(siteText.display, "mx-auto mt-4 max-w-4xl")}>
				Talk to the people who <span className="text-primary">build it</span>
			</h1>
			<p className={cn(siteText.lede, "mx-auto mt-8 max-w-2xl")}>
				SurfSense is a small team, so there is no ticket queue and no contact form that goes
				nowhere. Pick whichever of the four below matches what you need.
			</p>
			<div className="mt-10 flex justify-center">
				<a className={PILL} href={CALL_URL} target="_blank" rel="noreferrer noopener">
					Book a call
					<ArrowUpRight01Icon aria-hidden="true" className="size-4" />
				</a>
			</div>
		</section>
	);
}

function ChannelCard({ channel, icon }: { channel: Channel; icon: ReactNode }) {
	const { label, href, external } = channel.action;

	return (
		<div className="flex h-full flex-col rounded-2xl border border-border bg-card p-6 shadow-xs md:p-8">
			<span
				aria-hidden="true"
				className="grid size-11 place-items-center rounded-xl bg-secondary text-foreground"
			>
				{icon}
			</span>
			<p className={cn(siteText.eyebrow, "mt-6")}>{channel.eyebrow}</p>
			<h2 className={cn(siteText.h3, "mt-2")}>{channel.title}</h2>
			<p className={cn(siteText.body, "mt-2 text-sm")}>{channel.body}</p>

			{/* At the foot of the card so the links line up however each body wraps. */}
			<p className="mt-auto pt-6">
				<a
					className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:text-foreground focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
					href={href}
					{...(external ? { target: "_blank", rel: "noreferrer noopener" } : {})}
				>
					{label}
					<ArrowUpRight01Icon aria-hidden="true" className="size-4" />
				</a>
			</p>
		</div>
	);
}

export function ContactChannels() {
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Where to write</HomeBadge>
				<p className={cn(siteText.body, "mx-auto mt-4 max-w-xl")}>
					Four addresses, each for a different kind of message. A bug report sent to a sales call
					helps nobody.
				</p>
			</div>

			<ul className="m-0 mt-10 grid list-none gap-4 p-0 sm:grid-cols-2 lg:mt-14">
				{CHANNELS.map((channel, index) => (
					<li key={channel.title}>
						<ChannelCard channel={channel} icon={CHANNEL_ICONS[index]} />
					</li>
				))}
			</ul>
		</section>
	);
}

export function ContactBugReports() {
	return (
		<section className={sectionSpacing.foot}>
			<div className="rounded-3xl bg-muted p-2">
				<div className="rounded-2xl bg-card px-6 py-10 md:px-12 md:py-14">
					<h2 className={siteText.h2}>Reporting something broken</h2>
					<p className={cn(siteText.body, "mt-6 max-w-3xl")}>
						SurfSense runs on your machine, which means we cannot look at your logs, your index or
						your model settings. Everything we know about a bug is what the report tells us.
					</p>
					<p className={cn(siteText.body, "mt-3 max-w-3xl")}>
						Four details turn a report into a fix rather than a round trip. Nothing here asks for
						your documents. Describe the failure, not the file it happened on.
					</p>
					<p className="mt-6">
						<a
							className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:text-foreground focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
							href={DISCUSSIONS_URL}
							target="_blank"
							rel="noreferrer noopener"
						>
							Not sure it is a bug? Ask in Discussions
							<ArrowUpRight01Icon aria-hidden="true" className="size-4" />
						</a>
					</p>
				</div>
			</div>
		</section>
	);
}

/**
 * The page's last band: the one thing a licence buyer needs that none of the
 * four channels above states outright: that terms are negotiable, and that
 * there is a human to negotiate them with.
 */
export function ContactEnterprise() {
	return (
		<section className={sectionSpacing.foot}>
			<div className="flex flex-col items-start gap-8 rounded-4xl border border-border bg-card px-6 py-8 shadow-xs md:px-12 md:py-12 lg:flex-row lg:items-center lg:justify-between">
				<div className="max-w-2xl">
					<h2 className={siteText.h2}>Enterprise, volume and procurement</h2>
					<p className={cn(siteText.body, "mt-4")}>
						Above 25 seats, or where security review, invoicing and purchase orders are part of the
						process, the published{" "}
						<Link className={siteText.link} href="/pricing">
							pricing
						</Link>{" "}
						stops being the whole answer. Write with your seat count and what your procurement team
						needs, and you will get a reply from a person rather than a form.
					</p>
				</div>
				<a className={PILL} href={`mailto:${EMAIL}`}>
					<Mail01Icon aria-hidden="true" className="size-4" />
					{EMAIL}
				</a>
			</div>
		</section>
	);
}
