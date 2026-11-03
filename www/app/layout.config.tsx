import type { BaseLayoutProps } from "fumadocs-ui/layouts/shared";
import Image from "next/image";
import { DiscordLogo } from "@/components/site/logos/discord-logo";
import { DISCORD_URL, REPO_URL } from "@/components/site/site-content";

export const baseOptions: BaseLayoutProps = {
	nav: {
		title: (
			<>
				<Image src="/icon-128.svg" alt="SurfSense" width={24} height={24} className="dark:invert" />
				SurfSense Docs
			</>
		),
	},
	githubUrl: REPO_URL,
	// Fumadocs ships no Discord icon, so it takes the site's own mark.
	links: [
		{
			type: "icon",
			icon: <DiscordLogo />,
			text: "Discord",
			label: "Discord",
			url: DISCORD_URL,
			external: true,
		},
	],
	themeSwitch: { enabled: false },
};
