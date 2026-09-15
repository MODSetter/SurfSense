import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import {
	BUG_REPORT_CHECKLIST,
	CALL_URL,
	CHANNELS,
	type Channel,
	DISCUSSIONS_URL,
	EMAIL,
} from "@/components/contact/contact-content";
import { HomeButton } from "@/components/homepage/home/home-button";

/**
 * Contact sections.
 *
 * Built from the same `ss-home-*` primitives as the landing and pricing pages:
 * one ruled column, cell grids drawn with a hairline gap, a split band. The
 * three read as one document rather than three designs behind a shared
 * navigation.
 *
 * All server components. The page it replaced was a client component carrying
 * `motion`, an animated map pin and a world map SVG, none of which said
 * anything about how to reach us.
 */

export function ContactHero() {
	return (
		<section className="ss-home-hero ss-home-pad">
			<div className="mx-auto max-w-3xl text-center">
				<h1 className="ss-home-display">
					Talk to the people who <span className="ss-home-accent">build it</span>
				</h1>
				<p className="ss-home-lede mx-auto mt-8 max-w-2xl">
					SurfSense is a small team, so there is no ticket queue and no contact form that goes
					nowhere. Pick whichever of the four below matches what you need.
				</p>
				<div className="mt-10 flex justify-center">
					<HomeButton asChild size="xl">
						<a href={CALL_URL} target="_blank" rel="noreferrer noopener">
							Book a call
							<ArrowUpRight aria-hidden="true" />
						</a>
					</HomeButton>
				</div>
			</div>
		</section>
	);
}

function ChannelCell({ channel }: { channel: Channel }) {
	const { label, href, external } = channel.action;

	return (
		<div className="ss-home-cell flex flex-col">
			<p className="ss-home-eyebrow">{channel.eyebrow}</p>
			<h2 className="ss-home-h3 mt-3">{channel.title}</h2>
			<p className="ss-home-body mt-2 max-w-md text-sm">{channel.body}</p>

			{/* Pinned to the foot of the cell so the four links sit on one line
			    however each body wraps. */}
			<p className="mt-auto pt-6">
				{external ? (
					<a className="ss-home-forward" href={href} target="_blank" rel="noreferrer noopener">
						{label}
						<ArrowUpRight aria-hidden="true" className="size-4" />
					</a>
				) : (
					<a className="ss-home-forward" href={href}>
						{label}
						<ArrowUpRight aria-hidden="true" className="size-4" />
					</a>
				)}
			</p>
		</div>
	);
}

export function ContactChannels() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-head">
				<p className="ss-home-eyebrow">Where to write</p>
				<p className="ss-home-body mt-2 text-sm">
					Four addresses, each for a different kind of message. A bug report sent to a sales call
					helps nobody.
				</p>
			</div>

			<div className="ss-home-grid ss-home-grid-2">
				{CHANNELS.map((channel) => (
					<ChannelCell key={channel.title} channel={channel} />
				))}
			</div>
		</section>
	);
}

/**
 * The argument on the left, the checklist as a bento grid on the right: the
 * same split the landing page uses for its claims.
 */
export function ContactBugReports() {
	return (
		<section className="ss-home-rule">
			<div className="ss-home-split">
				<div className="ss-home-statement">
					<h2 className="ss-home-h2">Reporting something broken</h2>
					<p className="ss-home-body mt-6">
						SurfSense runs on your machine, which means we cannot look at your logs, your index or
						your model settings. Everything we know about a bug is what the report tells us.
					</p>
					<p className="ss-home-body mt-3">
						Four details turn a report into a fix rather than a round trip. Nothing here asks for
						your documents. Describe the failure, not the file it happened on.
					</p>
					<p className="mt-6">
						<a
							className="ss-home-forward"
							href={DISCUSSIONS_URL}
							target="_blank"
							rel="noreferrer noopener"
						>
							Not sure it is a bug? Ask in Discussions
							<ArrowUpRight aria-hidden="true" className="size-4" />
						</a>
					</p>
				</div>

				<div className="ss-home-grid ss-home-grid-2">
					{BUG_REPORT_CHECKLIST.map((item) => (
						<div key={item.title} className="ss-home-cell">
							<p className="ss-home-h3">{item.title}</p>
							<p className="ss-home-body mt-1.5 max-w-sm text-sm">{item.body}</p>
						</div>
					))}
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
		<section className="ss-home-rule ss-home-pad flex flex-col gap-6 py-12">
			<h2 className="ss-home-h2 max-w-3xl">Enterprise, volume and procurement</h2>
			<p className="ss-home-body max-w-3xl">
				Above 25 seats, or where security review, invoicing and purchase orders are part of the
				process, the published{" "}
				<Link className="ss-home-link" href="/pricing">
					pricing
				</Link>{" "}
				stops being the whole answer. Write to{" "}
				<a className="ss-home-link" href={`mailto:${EMAIL}`}>
					{EMAIL}
				</a>{" "}
				with your seat count and what your procurement team needs, and you will get a reply from a
				person rather than a form.
			</p>
		</section>
	);
}
