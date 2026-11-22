import type { Metadata } from "next";
import { HomeBadge } from "@/components/site/home-badge";
import { HomeButton } from "@/components/site/home-button";
import { sectionSpacing } from "@/components/site/home-section-spacing";
import { REPO_URL } from "@/components/site/site-content";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { SUNSET_DOWNLOADS, SUNSET_OTHER_DOWNLOADS_URL } from "./sunset-downloads";

/**
 * "SurfSense is now free: get the new app", for the legacy 0.0.x desktop app.
 *
 * At startup that app reads `api.surfsense.com/health` (now `www/static-hosts/`), sees
 * `sunset: true` and loads this page in its window instead of its hosted sign-in. Its window
 * opens a link in the user's browser only through a new window, so every link here has
 * `target="_blank"`, and `<base target="_blank">` covers any that might not. The download
 * links go through `/downloads/<platform>`, counted as `src=legacy`.
 */

export const metadata: Metadata = {
	title: "SurfSense is now free: get the new app",
	description:
		"The old SurfSense desktop app's hosted service has closed. The new SurfSense app is free, runs on your own computer and needs no account.",
	robots: { index: false, follow: false },
};

const NEW_WINDOW = { target: "_blank", rel: "noreferrer noopener" } as const;

export default function SunsetPage() {
	return (
		<>
			<base target="_blank" />
			<section className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>SurfSense is now free</HomeBadge>
				<h1 className={cn(siteText.display, "mx-auto mt-4 max-w-3xl")}>
					SurfSense is now free: <span className="text-primary">get the new app</span>
				</h1>
				<p className={cn(siteText.lede, "mx-auto mt-8 max-w-2xl")}>
					This is the old SurfSense desktop app, and the hosted service it signed in to has closed.
					The new SurfSense app runs entirely on your own computer, is free with every feature, and
					needs no account.
				</p>

				<ul className="m-0 mx-auto mt-10 flex max-w-2xl list-none flex-wrap justify-center gap-3 p-0">
					{SUNSET_DOWNLOADS.map((download, index) => (
						<li key={download.href}>
							<HomeButton
								asChild
								size="xl"
								variant={index === 0 ? "default" : "secondary"}
								className="h-11 rounded-full px-5 text-[0.9375rem]"
							>
								<a href={download.href} {...NEW_WINDOW}>
									{download.label}
								</a>
							</HomeButton>
						</li>
					))}
				</ul>
				<p className={cn(siteText.body, "mt-5 text-sm")}>
					On an Intel Mac, or want another file?{" "}
					<a className={siteText.link} href={SUNSET_OTHER_DOWNLOADS_URL} {...NEW_WINDOW}>
						See every download
					</a>
				</p>
			</section>

			<section className={sectionSpacing.foot}>
				<div className="mx-auto max-w-2xl rounded-3xl border border-border bg-card px-6 py-8 text-left shadow-xs md:px-10">
					<h2 className={siteText.h3}>Moving to the new app</h2>
					<ul className={cn(siteText.body, "mt-4 flex list-disc flex-col gap-2 pl-5")}>
						<li>
							The download opens in your browser. Install it like any other app; it is a separate
							app from this one.
						</li>
						<li>
							The new app has no account and no cloud. Add your files to it again, and they stay on
							your computer.
						</li>
						<li>
							Chat with a model that runs on your computer, or with your own key for a provider such
							as OpenAI or Anthropic.
						</li>
						<li>Once the new app is running, you can uninstall this one.</li>
					</ul>
					<p className={cn(siteText.body, "mt-6 text-sm")}>
						SurfSense Inc. wound down on 27 November 2026. SurfSense carries on as a free,
						open-source app,{" "}
						<a className={siteText.link} href={REPO_URL} {...NEW_WINDOW}>
							on GitHub
						</a>
						, maintained by its creator.
					</p>
				</div>
			</section>
		</>
	);
}
