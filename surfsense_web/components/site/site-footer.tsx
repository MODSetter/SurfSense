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
import { SiteFooterGlass } from "@/components/site/site-footer-glass";

/**
 * Site footer.
 *
 * A dark fluted glass panel that closes the page: identity, tagline and socials
 * on the left, link columns on the right. The panel paints its own ground and
 * its own text colours rather than reading the page's tokens, so it looks the
 * same under the dark site design and under the older light routes. It is the
 * end of the page, and it reads as one object everywhere.
 *
 * It replaces the oversized watermark wordmark that used to close the page,
 * which dominated the viewport without saying anything the footer above it had
 * not already said.
 *
 * Rendered by `app/(home)/layout.tsx` for every route under `(home)` except the
 * auth pages. On a route in the site design it sits inside the ruled column; elsewhere
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

const LINK_CLASS =
	"text-sm text-[#e8e3da]/65 transition-colors duration-100 hover:text-[#e8e3da] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#f26a4b] focus-visible:rounded-xs";

export function SiteFooter() {
	return (
		<footer className="ss-home-rule relative isolate overflow-hidden bg-[#1a1816]">
			{/* Decorative: the shader is texture, not content. */}
			<div className="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
				<SiteFooterGlass />
			</div>

			<div className="ss-home-pad flex flex-col gap-12 py-16 lg:flex-row lg:justify-between lg:gap-16">
				<div className="flex max-w-sm shrink-0 flex-col justify-between gap-12">
					<div>
						<Link href="/" className="inline-flex items-center gap-1.5">
							<Image
								src="/icon-128.svg"
								alt=""
								width={28}
								height={28}
								className="size-7 select-none invert"
							/>
							<span className="text-xl font-semibold tracking-tight text-[#e8e3da]">SurfSense</span>
						</Link>

						<p className="mt-4 text-lg font-medium leading-snug text-[#e8e3da]/90">
							One private workspace for everything
							<br />
							you read, save and ask.
						</p>
					</div>

					<div>
						<ul className="flex list-none flex-wrap gap-4 p-0">
							{SOCIALS.map((social) => {
								const Icon = social.icon;
								return (
									<li key={social.title}>
										<a
											href={social.href}
											target="_blank"
											rel="noreferrer noopener"
											aria-label={social.title}
											className={`${LINK_CLASS} inline-flex`}
										>
											<Icon aria-hidden="true" className="size-5" />
										</a>
									</li>
								);
							})}
						</ul>

						<p className="mt-4 text-xs text-[#e8e3da]/55">
							&copy; SurfSense {new Date().getFullYear()}. Free and open source.
						</p>
					</div>
				</div>

				<div className="grid grid-cols-2 gap-x-8 gap-y-10 sm:grid-cols-3 lg:gap-x-16">
					{FOOTER_COLUMNS.map((column) => (
						<div key={column.heading}>
							<p className="text-base font-semibold text-[#e8e3da]">{column.heading}</p>
							<ul className="mt-4 flex list-none flex-col gap-3 p-0">
								{column.links.map((link) => (
									<li key={link.title}>
										{link.external ? (
											<a
												href={link.href}
												target="_blank"
												rel="noreferrer noopener"
												className={LINK_CLASS}
											>
												{link.title}
											</a>
										) : (
											<Link href={link.href} className={LINK_CLASS}>
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
		</footer>
	);
}
