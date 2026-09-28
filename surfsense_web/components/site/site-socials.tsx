import { DiscordLogo } from "@/components/homepage/icons/discord-logo";
import { GithubLogo } from "@/components/homepage/icons/github-logo";
import { LinkedinLogo } from "@/components/homepage/icons/linkedin-logo";
import { RedditLogo } from "@/components/homepage/icons/reddit-logo";
import { XLogo } from "@/components/homepage/icons/x-logo";
import { REPO_URL } from "@/components/site/site-content";

/**
 * The footer's social links, drawn with each brand's official mark.
 *
 * Each mark is shown in its brand's official colour. GitHub and X are black
 * marks, which would vanish on the dark footer, so they use the white version
 * both brands publish for dark backgrounds. Reddit's and LinkedIn's marks are
 * full-colour and bring their own.
 */

type Social = {
	title: string;
	href: string;
	Logo: (props: React.SVGProps<SVGSVGElement>) => React.ReactNode;
	color?: string;
};

const DARK_GROUND_MARK = "#ffffff";

const SOCIALS: Social[] = [
	{ title: "GitHub", href: REPO_URL, Logo: GithubLogo, color: DARK_GROUND_MARK },
	{ title: "Discord", href: "https://discord.gg/ejRNvftDp9", Logo: DiscordLogo, color: "#5865F2" },
	{ title: "X", href: "https://x.com/mod_setter", Logo: XLogo, color: DARK_GROUND_MARK },
	{ title: "Reddit", href: "https://www.reddit.com/r/SurfSense/", Logo: RedditLogo },
	{ title: "LinkedIn", href: "https://www.linkedin.com/company/surfsense/", Logo: LinkedinLogo },
];

export function SiteSocials() {
	return (
		<ul className="flex list-none flex-wrap gap-4 p-0">
			{SOCIALS.map(({ title, href, Logo, color }) => (
				<li key={title}>
					<a
						href={href}
						target="_blank"
						rel="noreferrer noopener"
						style={color ? { color } : undefined}
						className="inline-flex transition-opacity duration-100 hover:opacity-80 focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#d9aa90]"
					>
						<Logo className="size-5" />
						<span className="sr-only">{title}</span>
					</a>
				</li>
			))}
		</ul>
	);
}
