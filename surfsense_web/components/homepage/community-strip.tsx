import { IconBrandDiscord, IconBrandGithub, IconBrandReddit } from "@tabler/icons-react";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";
import { Button } from "@/components/ui/button";

const GITHUB_URL = "https://github.com/MODSetter/SurfSense";
const DISCORD_URL = "https://discord.gg/ejRNvftDp9";
const REDDIT_URL = "https://www.reddit.com/r/SurfSense/";

/** Closing CTA doubling as the GitHub/community strip (brief section 7). */
export function CommunityStrip() {
	return (
		<MarketingSection>
			<Reveal>
				<div className="rounded-2xl border bg-card p-8 text-center sm:p-12">
					<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
						Open source, built in public
					</h2>
					<p className="mx-auto mt-3 max-w-xl text-muted-foreground leading-relaxed">
						No CI incumbent can show you its code. SurfSense can. Star the repository, join the
						community, or self-host the whole platform. Start free, no credit card required.
					</p>
					<div className="mt-7 flex flex-wrap justify-center gap-3">
						<Button asChild size="lg">
							<Link href="/register">
								Start for free
								<ArrowRight className="size-4" />
							</Link>
						</Button>
						<Button asChild variant="outline" size="lg">
							<Link href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
								<IconBrandGithub className="size-4" />
								Star on GitHub
							</Link>
						</Button>
						<Button asChild variant="ghost" size="lg">
							<Link href={DISCORD_URL} target="_blank" rel="noopener noreferrer">
								<IconBrandDiscord className="size-4" />
								Join Discord
							</Link>
						</Button>
						<Button asChild variant="ghost" size="lg">
							<Link href={REDDIT_URL} target="_blank" rel="noopener noreferrer">
								<IconBrandReddit className="size-4" />
								r/SurfSense
							</Link>
						</Button>
					</div>
				</div>
			</Reveal>
		</MarketingSection>
	);
}
