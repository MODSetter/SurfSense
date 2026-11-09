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
import { WebSearchLogo } from "@/components/site/logos/web-search-logo";
import { YoutubeLogo } from "@/components/site/logos/youtube-logo";
import { BUSINESS_LAUNCHED } from "@/features/business-launch/business-launched.mts";

type Chip = {
	key: string;
	name: string;
	Logo: (props: React.SVGProps<SVGSVGElement>) => React.ReactElement;
};

function chip(name: string, Logo: Chip["Logo"], key = name): Chip {
	return { key, name, Logo };
}

// From Business on, the three built into the app; each row names them twice to fill the panel.
const BUILT_IN = [
	chip("YouTube", YoutubeLogo),
	chip("Web Search", WebSearchLogo),
	chip("Web Crawl", WebCrawlLogo),
];
const BUILT_IN_ROWS = [BUILT_IN, [...BUILT_IN].reverse()].map((row) => [
	...row,
	...row.map((entry) => ({ ...entry, key: `${entry.key} again` })),
]);

// The ten platforms `/plugins` lists as shipping first, five to a row.
const PLATFORM_ROWS = [
	[
		chip("Reddit", RedditLogo),
		chip("YouTube", YoutubeLogo),
		chip("Instagram", InstagramLogo),
		chip("TikTok", TiktokLogo),
		chip("Google Maps", GoogleMapsLogo),
	],
	[
		chip("Google Search", GoogleSearchLogo),
		chip("Indeed", IndeedLogo),
		chip("Amazon", AmazonLogo),
		chip("Walmart", WalmartLogo),
		chip("Web Crawl", WebCrawlLogo),
	],
];
const ROWS = BUSINESS_LAUNCHED ? BUILT_IN_ROWS : PLATFORM_ROWS;
const SECONDS = [30, 26];

/** The first plugins drifting past over the meadow, alternate rows reversed. */
export function PluginsVisual() {
	return (
		<ScenePanel scene={featuresScene} position="center 85%">
			<PauseOffscreen className="flex flex-col gap-5 py-10">
				{ROWS.map((row, index) => (
					<ChipMarquee key={row[0].key} seconds={SECONDS[index]} reverse={index % 2 === 1}>
						{row.map(({ key, name, Logo }) => (
							<GlassChip key={key} icon={<Logo />} label={name} large />
						))}
					</ChipMarquee>
				))}
			</PauseOffscreen>
		</ScenePanel>
	);
}
