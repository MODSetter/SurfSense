import { ChipMarquee } from "@/components/homepage/home/home-features/chip-marquee";
import featuresScene from "@/components/homepage/home/home-features/features-scene.webp";
import { GlassChip } from "@/components/homepage/home/home-features/glass-chip";
import { PauseOffscreen } from "@/components/homepage/home/home-features/pause-offscreen";
import { ScenePanel } from "@/components/homepage/home/home-features/scene-panel";
import { AmazonLogo } from "@/components/homepage/icons/amazon-logo";
import { GoogleMapsLogo } from "@/components/homepage/icons/google-maps-logo";
import { GoogleSearchLogo } from "@/components/homepage/icons/google-search-logo";
import { IndeedLogo } from "@/components/homepage/icons/indeed-logo";
import { InstagramLogo } from "@/components/homepage/icons/instagram-logo";
import { RedditLogo } from "@/components/homepage/icons/reddit-logo";
import { TiktokLogo } from "@/components/homepage/icons/tiktok-logo";
import { WalmartLogo } from "@/components/homepage/icons/walmart-logo";
import { WebCrawlLogo } from "@/components/homepage/icons/web-crawl-logo";
import { YoutubeLogo } from "@/components/homepage/icons/youtube-logo";

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
