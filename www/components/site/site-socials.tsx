import { HomeButton } from "@/components/site/home-button";
import { DiscordLogo } from "@/components/site/logos/discord-logo";
import { GithubLogo } from "@/components/site/logos/github-logo";
import { LinkedinLogo } from "@/components/site/logos/linkedin-logo";
import { RedditLogo } from "@/components/site/logos/reddit-logo";
import { XLogo } from "@/components/site/logos/x-logo";
import { REPO_URL } from "@/components/site/site-content";

/**
 * The footer's social links, each in a small bordered square.
 *
 * GitHub, Discord and X are single-colour marks and take the card's ink.
 * Reddit's and LinkedIn's marks are full-colour by design and keep their own.
 */

type Social = {
	title: string;
	href: string;
	Logo: (props: React.SVGProps<SVGSVGElement>) => React.ReactNode;
};

const SOCIALS: Social[] = [
	{ title: "GitHub", href: REPO_URL, Logo: GithubLogo },
	{ title: "Discord", href: "https://discord.gg/ejRNvftDp9", Logo: DiscordLogo },
	{ title: "X", href: "https://x.com/mod_setter", Logo: XLogo },
	{ title: "Reddit", href: "https://www.reddit.com/r/SurfSenseAI/", Logo: RedditLogo },
	{ title: "LinkedIn", href: "https://www.linkedin.com/company/surfsense/", Logo: LinkedinLogo },
];

export function SiteSocials() {
	return (
		<ul className="flex list-none flex-wrap gap-3 p-0">
			{SOCIALS.map(({ title, href, Logo }) => (
				<li key={title}>
					<HomeButton
						asChild
						variant="bare"
						className={`grid size-11 place-items-center rounded-lg border border-foreground/15 bg-background/60 text-foreground hover:bg-background focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring`}
					>
						<a href={href} target="_blank" rel="noreferrer noopener">
							<Logo className="size-[1.125rem]" />
							<span className="sr-only">{title}</span>
						</a>
					</HomeButton>
				</li>
			))}
		</ul>
	);
}
