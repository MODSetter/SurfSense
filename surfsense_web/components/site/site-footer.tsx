import {
	IconBrandDiscord,
	IconBrandGithub,
	IconBrandLinkedin,
	IconBrandReddit,
	IconBrandTwitter,
} from "@tabler/icons-react";
import Image from "next/image";
import Link from "next/link";
import { FOOTER_COLUMNS, REPO_URL } from "@/components/site/site-content";

/**
 * Site footer.
 *
 * A port of the reference design's `Footer.svelte`: identity and legal on the
 * left, link columns on the right, all inside the same ruled column as the
 * sections above so the side borders run unbroken from the hero to the bottom
 * of the page. It is part of the page, not chrome wrapped around it.
 *
 * The oversized wordmark that closes the page is kept from the previous
 * footer.
 *
 * Rendered by `app/(home)/layout.tsx` for every route under `(home)` except the
 * auth pages. On a site-design route it sits inside the ruled column; elsewhere
 * it is held to the same width without the side borders.
 */

const SOCIALS = [
	{ title: "GitHub", href: REPO_URL, icon: IconBrandGithub },
	{ title: "Discord", href: "https://discord.gg/ejRNvftDp9", icon: IconBrandDiscord },
	{ title: "Twitter", href: "https://x.com/mod_setter", icon: IconBrandTwitter },
	{ title: "Reddit", href: "https://www.reddit.com/r/SurfSense/", icon: IconBrandReddit },
	{
		title: "LinkedIn",
		href: "https://www.linkedin.com/company/surfsense/",
		icon: IconBrandLinkedin,
	},
];

export function SiteFooter() {
	return (
		<footer className="ss-home-rule overflow-hidden">
			<div className="ss-home-pad flex flex-col gap-12 py-12 lg:flex-row lg:gap-16">
				<div className="shrink-0 lg:w-72">
					<Link href="/" className="inline-flex items-center gap-1.5">
						<Image
							src="/icon-128.svg"
							alt=""
							width={28}
							height={28}
							className="size-7 select-none invert"
						/>
						<span className="text-xl font-semibold tracking-tight text-[color:var(--foreground)]">
							SurfSense
						</span>
					</Link>

					<p className="ss-home-body mt-4 text-sm">
						&copy; SurfSense {new Date().getFullYear()}. Free and open source.
					</p>

					<ul className="mt-6 flex list-none flex-wrap gap-3 p-0">
						{SOCIALS.map((social) => {
							const Icon = social.icon;
							return (
								<li key={social.title}>
									<a
										href={social.href}
										target="_blank"
										rel="noreferrer noopener"
										aria-label={social.title}
										className="ss-home-footer-link inline-flex"
									>
										<Icon aria-hidden="true" className="size-5" />
									</a>
								</li>
							);
						})}
					</ul>
				</div>

				<div className="grid flex-1 grid-cols-2 gap-x-8 gap-y-10 sm:grid-cols-3">
					{FOOTER_COLUMNS.map((column) => (
						<div key={column.heading}>
							<p className="text-sm font-semibold text-[color:var(--foreground)]">
								{column.heading}
							</p>
							<ul className="mt-4 flex list-none flex-col gap-2.5 p-0">
								{column.links.map((link) => (
									<li key={link.title}>
										{link.external ? (
											<a
												href={link.href}
												target="_blank"
												rel="noreferrer noopener"
												className="ss-home-footer-link"
											>
												{link.title}
											</a>
										) : (
											<Link href={link.href} className="ss-home-footer-link">
												{link.title}
											</Link>
										)}
									</li>
								))}
							</ul>
						</div>
					))}
				</div>
			</div>

			{/* Decorative type, not a heading: it names nothing the page has not
			    already said, so it is hidden from assistive technology. */}
			<p className="ss-home-wordmark" aria-hidden="true">
				SurfSense
			</p>
		</footer>
	);
}
