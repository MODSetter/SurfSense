import { ChipMarquee } from "@/app/(home)/_home/home-features/chip-marquee";
import featuresScene from "@/app/(home)/_home/home-features/features-scene.webp";
import { GlassChip } from "@/app/(home)/_home/home-features/glass-chip";
import { PauseOffscreen } from "@/app/(home)/_home/home-features/pause-offscreen";
import { ScenePanel } from "@/app/(home)/_home/home-features/scene-panel";
import { AmazonLogo } from "@/components/site/logos/amazon-logo";
import { GoogleMapsLogo } from "@/components/site/logos/google-maps-logo";
import { GoogleSearchLogo } from "@/components/site/logos/google-search-logo";
import { IndeedLogo } from "@/components/site/logos/indeed-logo";
import { InstagramLogo } from "@/components/site/logos/instagram-logo";
import { RedditLogo } from "@/components/site/logos/reddit-logo";
import { TiktokLogo } from "@/components/site/logos/tiktok-logo";
import { WalmartLogo } from "@/components/site/logos/walmart-logo";
import { WebCrawlLogo } from "@/components/site/logos/web-crawl-logo";
import { YoutubeLogo } from "@/components/site/logos/youtube-logo";

// The ten platforms `/plugins` lists as shipping first, five to a row.
const ROWS = [
	[
		{ name: "Reddit", Logo: RedditLogo },
		{ name: "YouTube", Logo: YoutubeLogo },
		{ name: "Instagram", Logo: InstagramLogo },
		{ name: "TikTok", Logo: TiktokLogo },
		{ name: "Google Maps", Logo: GoogleMapsLogo },
	],
	[
		{ name: "Google Search", Logo: GoogleSearchLogo },
		{ name: "Indeed", Logo: IndeedLogo },
		{ name: "Amazon", Logo: AmazonLogo },
		{ name: "Walmart", Logo: WalmartLogo },
		{ name: "Web Crawl", Logo: WebCrawlLogo },
	],
];
const SECONDS = [30, 26];

/** The first plugins drifting past over the meadow, alternate rows reversed. */
export function PluginsVisual() {
	return (
		<ScenePanel scene={featuresScene} position="center 85%">
			<PauseOffscreen className="flex flex-col gap-5 py-10">
				{ROWS.map((row, index) => (
					<ChipMarquee key={row[0].name} seconds={SECONDS[index]} reverse={index % 2 === 1}>
						{row.map(({ name, Logo }) => (
							<GlassChip key={name} icon={<Logo />} label={name} large />
						))}
					</ChipMarquee>
				))}
			</PauseOffscreen>
		</ScenePanel>
	);
}
