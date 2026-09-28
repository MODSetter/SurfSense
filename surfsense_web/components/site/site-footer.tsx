import Image from "next/image";
import Link from "next/link";
import { FOOTER_COLUMNS } from "@/components/site/site-content";
import { SiteFooterGlass } from "@/components/site/site-footer-glass";
import { SiteSocials } from "@/components/site/site-socials";

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

const LINK_CLASS =
	"text-sm text-[#e8e3da]/65 transition-colors duration-100 hover:text-[#e8e3da] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#d9aa90] focus-visible:rounded-xs";

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
						<Link href="/" className="select-none inline-flex items-center gap-1.5">
							<Image src="/icon-128.svg" alt="" width={28} height={28} className="size-6 invert" />
							<span className="ss-home-wordmark text-xl text-[#e8e3da]">SurfSense</span>
						</Link>

						<p className="mt-4 text-lg font-medium leading-snug text-[#e8e3da]/90">
							One private workspace for everything
							<br />
							you read, save and ask.
						</p>
					</div>

					<div>
						<SiteSocials />

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
