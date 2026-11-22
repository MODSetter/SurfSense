import type { ReactNode } from "react";
import {
	CHANNELS,
	type Channel,
	DISCUSSIONS_URL,
	ISSUES_URL,
} from "@/app/(home)/contact/contact-content";
import { HomeBadge } from "@/components/site/home-badge";
import { HomeButton } from "@/components/site/home-button";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { DiscordLogo } from "@/components/site/logos/discord-logo";
import { GithubLogo } from "@/components/site/logos/github-logo";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { ArrowUpRight01Icon, Mail01Icon } from "@/components/ui/icons";

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

// In `CHANNELS` order: email, issue, community.
const CHANNEL_ICONS: ReactNode[] = [
	<Mail01Icon key="email" className="size-5" />,
	<GithubLogo key="issue" className="size-5" />,
	<DiscordLogo key="discord" className="size-5" />,
];

export function ContactHero() {
	return (
		<section className={cn("text-center", sectionSpacing.head)}>
			<HomeBadge>Contact</HomeBadge>
			<h1 className={cn(siteText.display, "mx-auto mt-4 max-w-4xl")}>
				Talk to the person who <span className="text-primary">builds it</span>
			</h1>
			<p className={cn(siteText.lede, "mx-auto mt-8 max-w-2xl")}>
				SurfSense is free and open source, kept up by its creator as a side project, so there is no
				ticket queue and no contact form that goes nowhere. Pick whichever of the three below
				matches what you need.
			</p>
			<div className="mt-10 flex justify-center">
				<HomeButton asChild variant="bare" className={PILL}>
					<a href={ISSUES_URL} target="_blank" rel="noreferrer noopener">
						Open an issue
						<ArrowUpRight01Icon aria-hidden="true" className="size-4" />
					</a>
				</HomeButton>
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
					Three addresses, each for a different kind of message. A bug report filed in public gets
					fixed sooner than one sent by email.
				</p>
			</div>

			<ul className="m-0 mt-10 grid list-none gap-4 p-0 lg:mt-14 lg:grid-cols-3">
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
