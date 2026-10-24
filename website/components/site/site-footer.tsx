import Image from "next/image";
import Link from "next/link";
import { FOOTER_COLUMNS, REPO_URL } from "@/components/site/site-content";
import footerScene from "@/components/site/site-footer-scene.webp";
import { SiteSocials } from "@/components/site/site-socials";
import { cn } from "@/components/ui/cn";

/**
 * Site footer: the site's links set straight on the page's ground, which fades
 * into an engraved Golden Gate Bridge that fills the open band below.
 * Rendered by `app/(home)/layout.tsx` for every route under `(home)` except the
 * auth pages.
 */

const LINK_CLASS =
	"text-[0.9375rem] text-muted-foreground transition-colors duration-100 hover:text-foreground focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring";

const WORDMARK_CLASS =
	"font-[family-name:var(--font-brand)] font-semibold [font-variation-settings:'SOFT'_75,'WONK'_0]";

export function SiteFooter() {
	return (
		<footer className="relative isolate overflow-hidden">
			{/* Sized by width and anchored to the bottom, so the bridge stays in the open band
			    however tall the links make the footer. Covering the footer instead would
			    blow the 3:1 scene up well past its 4344px source and blur the linework.
			    From lg the whole panorama shows; below it the scene is wider than the screen
			    and the left offsets keep the main tower, a third of the way in, on screen. */}
			<div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
				<div className="absolute bottom-0 -left-[60%] aspect-[4344/1448] w-[360%] sm:-left-[15%] sm:w-[220%] lg:left-0 lg:w-full">
					<Image
						src={footerScene}
						alt=""
						fill
						sizes="(max-width: 639px) 360vw, (max-width: 1023px) 220vw, 100vw"
						quality={85}
						placeholder="blur"
						className="object-cover object-bottom select-none"
					/>
					<div className="absolute inset-x-0 top-0 h-[45%] bg-linear-to-b from-background via-background/80 to-transparent" />
				</div>
			</div>

			<div className="mx-auto max-w-(--home-max) px-6 pt-20 md:px-10 md:pt-28">
				<div className="flex flex-col gap-12 lg:flex-row lg:justify-between lg:gap-16">
					<div className="max-w-sm">
						<Link href="/" className="inline-flex items-center gap-2 select-none">
							<Image src="/icon-128.svg" alt="" width={32} height={32} className="size-8" />
							<span className={cn(WORDMARK_CLASS, "text-2xl text-foreground")}>SurfSense</span>
						</Link>
						<p className="mt-5 text-[0.9375rem] leading-relaxed text-pretty text-muted-foreground">
							One private workspace for everything you read, save and ask.
						</p>
						<div className="mt-8">
							<SiteSocials />
						</div>
					</div>

					<div className="grid grid-cols-2 gap-x-8 gap-y-10 sm:grid-cols-3 sm:gap-x-16 lg:gap-x-24">
						{FOOTER_COLUMNS.map((column) => (
							<div key={column.heading}>
								<p className="text-base font-medium text-foreground">{column.heading}</p>
								<ul className="mt-5 flex list-none flex-col gap-3.5 p-0">
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

				<div className="mt-16 flex flex-col gap-3 border-t border-foreground/15 pt-6 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
					<p>&copy; {new Date().getFullYear()} SurfSense. All rights reserved.</p>
					<p>
						Free and{" "}
						<a
							href={REPO_URL}
							target="_blank"
							rel="noreferrer noopener"
							className="text-foreground underline underline-offset-4 transition-colors duration-100 hover:text-foreground/80 focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
						>
							open source
						</a>
					</p>
				</div>
			</div>

			{/* The open band the bridge shows through. From lg it is 75% of the scene's
			    height, so the tower rises behind the copyright row at every width. */}
			<div aria-hidden="true" className="h-96 lg:aspect-4/1 lg:h-auto" />
		</footer>
	);
}
