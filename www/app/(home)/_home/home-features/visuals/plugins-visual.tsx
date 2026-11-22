import { ChipMarquee } from "@/app/(home)/_home/home-features/chip-marquee";
import featuresScene from "@/app/(home)/_home/home-features/features-scene.webp";
import { GlassChip } from "@/app/(home)/_home/home-features/glass-chip";
import { PauseOffscreen } from "@/app/(home)/_home/home-features/pause-offscreen";
import { ScenePanel } from "@/app/(home)/_home/home-features/scene-panel";
import { WebCrawlLogo } from "@/components/site/logos/web-crawl-logo";
import { WebSearchLogo } from "@/components/site/logos/web-search-logo";
import { YoutubeLogo } from "@/components/site/logos/youtube-logo";

type Chip = {
	key: string;
	name: string;
	Logo: (props: React.SVGProps<SVGSVGElement>) => React.ReactElement;
};

function chip(name: string, Logo: Chip["Logo"], key = name): Chip {
	return { key, name, Logo };
}

// The three built into the app; each row names them twice to fill the panel.
const BUILT_IN = [
	chip("YouTube", YoutubeLogo),
	chip("Web Search", WebSearchLogo),
	chip("Web Crawl", WebCrawlLogo),
];
const BUILT_IN_ROWS = [BUILT_IN, [...BUILT_IN].reverse()].map((row) => [
	...row,
	...row.map((entry) => ({ ...entry, key: `${entry.key} again` })),
]);

const ROWS = BUILT_IN_ROWS;
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
