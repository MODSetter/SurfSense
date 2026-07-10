"use client";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import React, { memo, useCallback, useEffect, useRef, useState } from "react";
import Balancer from "react-wrap-balancer";
import { HeroChatDemo, type HeroChatDemoScript } from "@/components/homepage/hero-chat-demo";
import { Button } from "@/components/ui/button";
import { ExpandedMediaOverlay, useExpandedMedia } from "@/components/ui/expanded-gif-overlay";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { buildBackendUrl } from "@/lib/env-config";
import { trackLoginAttempt } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";

const GoogleLogo = ({ className }: { className?: string }) => (
	<svg
		className={className}
		viewBox="0 0 24 24"
		xmlns="http://www.w3.org/2000/svg"
		role="img"
		aria-label="Google logo"
	>
		<title>Google logo</title>
		<path
			d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
			fill="#4285F4"
		/>
		<path
			d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
			fill="#34A853"
		/>
		<path
			d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
			fill="#FBBC05"
		/>
		<path
			d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
			fill="#EA4335"
		/>
	</svg>
);

type HeroUseCase = {
	id: string;
	title: string;
	description: string;
	src: string | null;
	/** Scripted chat demo shown when there is no recorded video. */
	demo?: HeroChatDemoScript;
};

type HeroCategory = {
	id: string;
	label: string;
	useCases: HeroUseCase[];
};

const HERO_TUTORIAL = "/homepage/hero_tutorial";
const HERO_REALTIME = "/homepage/hero_realtime";

/*
 * Every scripted demo below mirrors a task the SurfSense agent has actually run
 * end-to-end (see backend agent e2e suite). Recorded videos take precedence via
 * `src`; everything else plays the chat demo.
 */
const CATEGORIES: HeroCategory[] = [
	{
		id: "connector-workflows",
		label: "Multi-Connector Workflows",
		useCases: [
			{
				id: "launch-impact",
				title: "Launch Impact, Across Every Platform",
				description:
					"One prompt chains Google Search, Reddit, and YouTube into a single cited brief on how a competitor launch actually landed.",
				src: null,
				demo: {
					prompt:
						"Our competitor launched v2 yesterday. Measure the reaction across search, Reddit, and YouTube.",
					steps: [
						{
							title: "Google Search",
							items: ["Scraping 8 SERPs · launch coverage + AI Overviews"],
						},
						{
							title: "Reddit",
							items: ['"competitor v2" · 23 threads in the past 48h'],
						},
						{
							title: "Youtube",
							items: ["6 launch videos · 1,904 comments pulled"],
						},
						{
							title: "Plan tasks",
							items: ["Merge all three signals into one launch-impact brief"],
						},
					],
					rows: [
						{
							primary: "5 of 8 SERPs show launch coverage",
							secondary: "2 already trigger AI Overviews citing their blog",
						},
						{
							primary: "Reddit: pricing backlash in 9 of 23 threads",
							secondary: '"v2 doubled the price" · top thread 412 upvotes',
						},
						{
							primary: "YouTube: creators praise UI, question pricing",
							secondary: "61% positive on features · pricing the top complaint",
						},
					],
					summary: "3 connectors, one cited brief · saved to your workspace",
				},
			},
			{
				id: "local-teardown",
				title: "Local Competitor Teardown",
				description:
					"Google Maps finds the players, the Web Crawler reads their sites, and Google Search shows who wins the query, in one run.",
				src: null,
				demo: {
					prompt:
						'Tear down the top-rated gyms in Austin: reviews, pricing pages, and who ranks for "gym austin".',
					steps: [
						{
							title: "Google Maps",
							items: ['"gym austin" · top 10 places + 2,400 reviews'],
						},
						{
							title: "Web Crawler",
							items: ["Visiting 10 gym sites", "Extracting pricing and membership pages"],
						},
						{
							title: "Google Search",
							items: ['SERP for "gym austin" · organic, ads, map pack'],
						},
					],
					rows: [
						{
							primary: "Review themes: crowding + billing complaints",
							secondary: "appear in 31% of 1-3★ reviews across 10 gyms",
						},
						{
							primary: "Pricing: $89–149/mo · 3 hide it behind forms",
							secondary: "extracted from all 10 sites with source pages",
						},
						{
							primary: "2 gyms buy ads on their own brand name",
							secondary: "map pack and organic top 3 don't overlap",
						},
					],
					summary: "Maps + Crawler + Search in one run · teardown saved",
				},
			},
			{
				id: "competitor-360",
				title: "Competitor 360, on a Schedule",
				description:
					"An automation chains four connectors every week: site changes, rank movements, Reddit sentiment, and YouTube reaction.",
				src: null,
				demo: {
					prompt:
						"Every Monday, build me a 360 on our top competitor: site changes, rankings, Reddit, and YouTube.",
					steps: [
						{
							title: "Web Crawler",
							items: ["pricing + changelog pages · 2 changes detected"],
						},
						{
							title: "Google Search",
							items: ["12 shared keywords · rank movements captured"],
						},
						{
							title: "Reddit",
							items: ["18 mentions this week · sentiment tagged"],
						},
						{
							title: "Youtube",
							items: ["2 new videos · comments and transcripts pulled"],
						},
						{
							title: "Create automation",
							items: ["Weekly 360 brief · Mondays 8:00"],
						},
					],
					rows: [
						{
							primary: "Shipped: usage-based pricing page",
							secondary: "pricing + changelog diff · detected Jul 3",
						},
						{
							primary: 'Took #2 on "competitive intelligence api"',
							secondary: "you hold #4 · gap widened two weeks in a row",
						},
						{
							primary: "Reddit sentiment down 12 pts since the change",
							secondary: "churn signals in 5 threads · quotes linked",
						},
					],
					summary: "4 connectors, 1 automation · first brief lands Monday 8:00",
				},
			},
		],
	},
	{
		id: "competitor-monitoring",
		label: "Competitor Monitoring",
		useCases: [
			{
				id: "pricing-watch",
				title: "Competitor Pricing Watch",
				description:
					"The agent extracts every plan from a competitor's pricing page, and an automation re-checks it so you hear about changes first.",
				src: null,
				demo: {
					prompt: "Extract every plan, price, and limit from our top 3 competitors' pricing pages.",
					steps: [
						{
							title: "Plan tasks",
							items: ["Crawl 3 pricing pages", "Extract plans, prices, limits into one table"],
						},
						{
							title: "Web Crawler",
							items: [
								"competitor-a.com/pricing · 4 plans",
								"competitor-b.com/pricing · 3 plans",
								"competitor-c.com/plans · 4 plans",
							],
						},
						{
							title: "Create automation",
							items: ["Daily pricing re-check · alert on any change"],
						},
					],
					rows: [
						{
							primary: "Competitor A — Pro $49/mo",
							secondary: "10k credits · 3 seats · raised from $39 on Jun 12",
						},
						{
							primary: "Competitor B — Team $99/mo",
							secondary: "50k credits · unlimited seats · annual-only",
						},
						{
							primary: "Competitor C — Free tier removed",
							secondary: "Trial now 7 days · card required",
						},
					],
					summary: "3 pages parsed · 11 plans in one table · daily re-check scheduled",
				},
			},
			{
				id: "site-diff",
				title: "Product & Changelog Tracking",
				description:
					"An automation crawls a rival's product, changelog, and careers pages and briefs you on what shipped.",
				src: null,
				demo: {
					prompt:
						"Every Monday, crawl our competitors' changelogs and brief me on what they shipped.",
					steps: [
						{
							title: "Web Crawler",
							items: [
								"competitor-a.com/changelog · 6 entries",
								"competitor-b.com/whats-new · 3 entries",
							],
						},
						{
							title: "Create automation",
							items: ["Weekly changelog brief · Mondays 8:00"],
						},
					],
					rows: [
						{
							primary: "Competitor A shipped SSO + audit logs",
							secondary: "changelog · Jun 30 · enterprise push",
						},
						{
							primary: "Competitor B launched API v2 beta",
							secondary: "whats-new · Jul 2 · targets developers",
						},
					],
					summary: "Brief saved to workspace · automation runs Mondays 8:00",
				},
			},
			{
				id: "serp-watch",
				title: "Rank & Ad Monitoring",
				description:
					"Automations track the Google rankings, paid ads, and AI Overview citations your market actually sees.",
				src: null,
				demo: {
					prompt: "Track who ranks and runs ads for our top 10 keywords in the US.",
					steps: [
						{
							title: "Google Search",
							items: ["Scraping 10 SERPs (US) · organic, ads, AI Overviews"],
						},
						{
							title: "Plan tasks",
							items: ["Diff against last capture", "Flag rank and ad movements"],
						},
						{
							title: "Create automation",
							items: ["Daily rank + ad watch on these keywords"],
						},
					],
					rows: [
						{
							primary: '"competitive intelligence tools" — you #4, ↓1',
							secondary: "Competitor A took #3 · runs 2 sponsored ads",
						},
						{
							primary: "AI Overview cites Competitor B",
							secondary: 'triggered on "brand monitoring software"',
						},
					],
					summary: "10 SERPs captured · 3 movements flagged · daily automation on",
				},
			},
		],
	},
	{
		id: "lead-generation",
		label: "B2B Lead Generation",
		useCases: [
			{
				id: "local-leads",
				title: "Local Business Leads",
				description:
					"Turn a category and a territory into a lead list with phones, websites, ratings, and decision-maker contacts.",
				src: null,
				demo: {
					prompt:
						"Find the top 5 burger places in San Jose and pull staff contacts from their websites.",
					steps: [
						{
							title: "Google Maps",
							items: ['Searching "burger san jose" · top 5 by rating and reviews'],
						},
						{
							title: "Web Crawler",
							items: ["Visiting 5 business sites", "Extracting staff and contact pages"],
						},
						{
							title: "Save document",
							items: ["Lead list with phones, sites, contacts"],
						},
					],
					rows: [
						{
							primary: "The Counter — 4.5★ (2,310 reviews)",
							secondary: "+1 408-423-9200 · thecounter.com · 2 contacts found",
						},
						{
							primary: "Paper Plane — 4.6★ (1,882 reviews)",
							secondary: "site crawled · owner + events email found",
						},
						{
							primary: "Smoking Pig BBQ — 4.4★ (3,041 reviews)",
							secondary: "+1 408-380-4784 · catering contact found",
						},
					],
					summary: "5 places · 9 contacts with provenance · saved as lead list",
				},
			},
			{
				id: "team-rosters",
				title: "Team Rosters & Contacts",
				description:
					"Spider any company site and pull the full team with emails, socials, and provenance, exported to CSV.",
				src: null,
				demo: {
					prompt: "Get the complete a16z team roster and save it as a CSV in my workspace.",
					steps: [
						{
							title: "Web Crawler",
							items: ["a16z.com/team · following profile links", "142 profiles found"],
						},
						{
							title: "Plan tasks",
							items: ["Enrich each profile with email or LinkedIn"],
						},
						{
							title: "Write file",
							items: ["a16z-team.csv · saved to workspace"],
						},
					],
					rows: [
						{
							primary: "142 team profiles extracted",
							secondary: "name, role, focus area, profile URL",
						},
						{
							primary: "89 enriched with email or LinkedIn",
							secondary: "pulled from bios and linked pages",
						},
						{ primary: "a16z-team.csv", secondary: "saved to your workspace · ready to export" },
					],
					summary: "Full roster in 94s · every row cites its source page",
				},
			},
			{
				id: "portfolio-mapping",
				title: "Portfolio & Market Mapping",
				description:
					"Map an investor's portfolio or a whole category, then enrich every company with pricing and contacts.",
				src: null,
				demo: {
					prompt: "Get the a16z team and their portfolio companies.",
					steps: [
						{
							title: "Web Crawler",
							items: ["a16z.com/team · 142 profiles", "a16z.com/portfolio · 312 companies"],
						},
						{
							title: "Plan tasks",
							items: [
								"Match partners to their portfolio boards",
								"Enrich your category with pricing",
							],
						},
					],
					rows: [
						{
							primary: "312 portfolio companies mapped",
							secondary: "sector, stage, website, one-line pitch",
						},
						{
							primary: "48 in your category",
							secondary: "enriched with pricing page + team size",
						},
					],
					summary: "Market map saved · new investments auto-added by automation",
				},
			},
		],
	},
	{
		id: "brand-listening",
		label: "Brand & Market Listening",
		useCases: [
			{
				id: "reddit-listening",
				title: "Reddit Brand Monitoring",
				description:
					"Hear what your market says about you, your competitors, and your category in the threads where buyers speak candidly.",
				src: null,
				demo: {
					prompt: "Give me 20 posts on Reddit where people ask for an alternative to NotebookLM.",
					steps: [
						{
							title: "Reddit",
							items: [
								'Searching "notebooklm alternative" across Reddit',
								"37 posts found · ranking by relevance and upvotes",
							],
						},
						{
							title: "Plan tasks",
							items: ["Tag each post: buying intent, churn signal, question"],
						},
					],
					rows: [
						{
							primary: "Best NotebookLM alternative that's open source?",
							secondary: "r/selfhosted · 214 upvotes · buying intent",
						},
						{
							primary: "NotebookLM keeps losing my sources, what else?",
							secondary: "r/artificial · 96 upvotes · churn signal",
						},
						{
							primary: "Anything like NotebookLM but with an API?",
							secondary: "r/LocalLLaMA · 71 upvotes · developer intent",
						},
					],
					summary: "20 posts · 8 with buying intent · daily tracking automation on",
				},
			},
			{
				id: "youtube-sentiment",
				title: "YouTube Audience Sentiment",
				description:
					"Pull videos, transcripts, and comments at scale to mine what audiences praise and complain about.",
				src: null,
				demo: {
					prompt:
						"Analyze the comments on our competitor's last 10 videos and cluster the complaints.",
					steps: [
						{
							title: "Youtube",
							items: ["Fetching last 10 videos", "4,812 comments pulled"],
						},
						{
							title: "Plan tasks",
							items: ["Cluster complaints by theme", "Score sentiment per cluster"],
						},
					],
					rows: [
						{
							primary: "Pricing complaints — 31% of negative comments",
							secondary: '"went from free to $20/mo overnight"',
						},
						{
							primary: "Export limits — 22%",
							secondary: '"can\'t get my own data out"',
						},
						{
							primary: "Praise: onboarding — 18% positive",
							secondary: "worth copying in your messaging",
						},
					],
					summary: "4,812 comments clustered · sentiment report saved",
				},
			},
			{
				id: "switcher-mining",
				title: "Switcher & Intent Mining",
				description:
					"Find the people actively looking for an alternative to a competitor, ranked by how ready they are to move.",
				src: null,
				demo: {
					prompt: "Find people asking for alternatives to our biggest competitor this month.",
					steps: [
						{
							title: "Reddit",
							items: [
								'Searching "alternative" mentions · past month',
								"12 active switcher threads",
							],
						},
						{
							title: "Plan tasks",
							items: ["Rank by recency and engagement", "Extract switching triggers"],
						},
					],
					rows: [
						{
							primary: "12 threads with active switchers",
							secondary: "ranked by recency and engagement",
						},
						{
							primary: "Top trigger: API price increase",
							secondary: "mentioned in 7 of 12 threads",
						},
					],
					summary: "Outreach-ready summaries drafted for the 5 hottest threads",
				},
			},
		],
	},
	{
		id: "market-research",
		label: "Market Research",
		useCases: [
			{
				id: "deep-research",
				title: "Deep Research on the Live Web",
				description:
					"The agent crawls dozens of live sources on a question and synthesizes a cited answer, not a stale index.",
				src: null,
				demo: {
					prompt: "Research the AI note-taking market and build a landscape brief with citations.",
					steps: [
						{
							title: "Research",
							items: ["Crawling 38 live sources", "Vendor sites, reviews, pricing pages"],
						},
						{
							title: "Generate report",
							items: ["Landscape brief · 24 inline citations"],
						},
					],
					rows: [
						{
							primary: "23 vendors mapped across 4 segments",
							secondary: "consumer, prosumer, team, developer-first",
						},
						{
							primary: "Pricing clusters at $10 and $20/mo",
							secondary: "3 vendors moved upmarket this quarter",
						},
					],
					summary: "Landscape brief saved · 24 inline citations you can check",
				},
			},
			{
				id: "geo-monitoring",
				title: "AI Overview & GEO Tracking",
				description:
					"Capture when Google's AI Overviews answer your market's queries, and exactly which sources they cite.",
				src: null,
				demo: {
					prompt: "Which of our target keywords trigger an AI Overview, and who gets cited?",
					steps: [
						{
							title: "Google Search",
							items: ["Scraping 25 SERPs", "Capturing AI Overviews and citations"],
						},
						{
							title: "Plan tasks",
							items: ["Map citations to competitors", "Compute your citation gap"],
						},
					],
					rows: [
						{
							primary: "9 of 25 keywords trigger an AI Overview",
							secondary: "up from 6 last month",
						},
						{
							primary: "Competitor A cited on 4 · you on 1",
							secondary: "their listicle wins 3 of those citations",
						},
					],
					summary: "Citation gap report saved · weekly re-check scheduled",
				},
			},
			{
				id: "cited-briefs",
				title: "Cited Briefs & Alerts",
				description:
					"Everything the agents gather lands in your workspace as briefs and alerts with sources you can check.",
				src: null,
				demo: {
					prompt: "Send me a Monday brief of every competitor change detected last week.",
					steps: [
						{
							title: "Plan tasks",
							items: ["Collect pricing, changelog, SERP, Reddit signals"],
						},
						{
							title: "Create automation",
							items: ["Weekly brief · Mondays 8:00 · workspace + email"],
						},
					],
					rows: [
						{
							primary: "Sources: pricing, changelogs, SERPs, Reddit",
							secondary: "everything your agents tracked this week",
						},
						{
							primary: "Delivered to workspace + email",
							secondary: "every claim links to its source",
						},
					],
					summary: "Automation created · first brief lands Monday 8:00",
				},
			},
		],
	},
	{
		id: "platform-agent",
		label: "SurfSense Agent",
		useCases: [
			{
				id: "chat-workspace",
				title: "Chat With Everything You Gather",
				description:
					"Ask questions across every crawl, mention, and document in your workspace and get answers with inline citations.",
				src: `${HERO_TUTORIAL}/BQnaGif_compressed.mp4`,
			},
			{
				id: "report",
				title: "AI Report Generator",
				description:
					"Turn your intelligence into cited research reports, then export to PDF or Markdown.",
				src: `${HERO_TUTORIAL}/ReportGenGif_compressed.mp4`,
			},
			{
				id: "podcast",
				title: "AI Podcast Generator",
				description: "Turn any brief or folder into a two-host AI podcast in under 20 seconds.",
				src: `${HERO_TUTORIAL}/PodcastGenGif.mp4`,
			},
			{
				id: "presentation",
				title: "AI Presentation & Video Maker",
				description: "Create editable slide decks and narrated video overviews from your findings.",
				src: `${HERO_TUTORIAL}/video_gen_surf.mp4`,
			},
			{
				id: "connect",
				title: "Build Your Knowledge Base",
				description:
					"Upload files or sync Google Drive, OneDrive, and Dropbox into one searchable knowledge base alongside everything your agents gather.",
				src: `${HERO_TUTORIAL}/ConnectorFlowGif.mp4`,
			},
			{
				id: "collab",
				title: "Collaborative AI Chat",
				description: "Work on AI conversations with your team in real time.",
				src: `${HERO_REALTIME}/RealTimeChatGif.mp4`,
			},
		],
	},
];

export function HeroSection() {
	return (
		<div className="mx-auto w-full max-w-7xl min-w-0 pt-36">
			<div className="mt-4 flex w-full min-w-0 flex-col items-start px-2 md:px-8 xl:px-0">
				<h1
					className={cn(
						"relative mt-4 max-w-4xl text-left text-4xl font-bold tracking-tight text-balance text-neutral-900 sm:text-5xl md:text-6xl dark:text-neutral-50"
					)}
				>
					<Balancer>Give your AI agents competitive intelligence.</Balancer>
				</h1>
				<div className="mt-4 flex w-full flex-col items-start justify-between gap-4 md:mt-8 md:flex-row md:items-end md:gap-10">
					<div>
						<p
							className={cn(
								"relative mb-8 max-w-2xl text-left text-sm text-neutral-600 antialiased sm:text-base md:text-lg dark:text-neutral-400"
							)}
						>
							SurfSense is an open-source competitive intelligence platform. Your AI agents monitor
							competitors, track rankings, and listen to your market with live data from platforms
							like Reddit, Instagram, YouTube, Google Maps, Google Search, and the open web.
						</p>

						<div className="relative mb-4 flex w-full flex-col justify-center gap-y-2 sm:flex-row sm:justify-start sm:space-y-0 sm:space-x-4">
							<GetStartedButton />
						</div>
					</div>
				</div>
				<BrowserWindow />
			</div>
		</div>
	);
}

function GetStartedButton() {
	const [isRedirecting, setIsRedirecting] = useState(false);

	const handleGoogleLogin = () => {
		if (isRedirecting) return;
		setIsRedirecting(true);
		trackLoginAttempt("google");
		window.location.href = buildBackendUrl("/auth/google/authorize-redirect");
	};

	return (
		<>
			<Button
				type="button"
				variant="ghost"
				onClick={handleGoogleLogin}
				disabled={isRedirecting}
				className="runtime-auth-google h-14 w-full cursor-pointer gap-3 rounded-lg border border-white bg-white text-center text-base font-medium text-[#1f1f1f] shadow-sm transition duration-150 hover:bg-zinc-100 hover:text-[#1f1f1f] sm:w-56 dark:border-white"
			>
				<GoogleLogo className="h-5 w-5" />
				<span>Continue with Google</span>
			</Button>
			<Button
				asChild
				variant="ghost"
				className="runtime-auth-local h-14 w-full rounded-lg bg-black text-center text-base font-medium text-white shadow-sm ring-1 shadow-black/10 ring-black/10 transition duration-150 active:scale-98 hover:bg-black sm:w-52 dark:bg-white dark:text-black dark:hover:bg-white"
			>
				<Link href="/login">Get Started</Link>
			</Button>
		</>
	);
}

const TabVideo = memo(function TabVideo({
	src,
	title,
	reduceMotion,
}: {
	src: string;
	title: string;
	reduceMotion: boolean;
}) {
	const videoRef = useRef<HTMLVideoElement>(null);
	const [hasLoaded, setHasLoaded] = useState(false);

	useEffect(() => {
		setHasLoaded(false);
		const video = videoRef.current;
		if (!video) return;
		video.currentTime = 0;
		// Respect reduced-motion: show the first frame and expose controls instead of autoplaying.
		if (!reduceMotion) {
			video.play().catch(() => {});
		}
	}, [reduceMotion]);

	const handleCanPlay = useCallback(() => {
		setHasLoaded(true);
	}, []);

	return (
		<div className="relative">
			<video
				ref={videoRef}
				key={src}
				src={src}
				preload={reduceMotion ? "metadata" : "auto"}
				aria-label={`${title} demo`}
				autoPlay={!reduceMotion}
				controls={reduceMotion}
				loop
				muted
				playsInline
				onCanPlay={handleCanPlay}
				className="aspect-video w-full rounded-lg sm:rounded-xl"
			/>
			{!hasLoaded && (
				<Skeleton className="absolute inset-0 aspect-video w-full rounded-lg bg-neutral-100 motion-reduce:animate-none sm:rounded-xl dark:bg-neutral-800" />
			)}
		</div>
	);
});

const UseCasePane = memo(function UseCasePane({
	useCase,
	reduceMotion,
}: {
	useCase: HeroUseCase;
	reduceMotion: boolean;
}) {
	const { expanded, open, close } = useExpandedMedia();
	const hasVideo = Boolean(useCase.src);

	const media = hasVideo ? (
		<Button
			type="button"
			variant="ghost"
			onClick={open}
			aria-label={`Expand ${useCase.title} demo`}
			className="h-auto w-full cursor-pointer rounded-none bg-neutral-50 p-2 hover:bg-neutral-50 sm:p-3 dark:bg-neutral-950 dark:hover:bg-neutral-950"
		>
			<TabVideo src={useCase.src as string} title={useCase.title} reduceMotion={reduceMotion} />
		</Button>
	) : (
		<div className="bg-neutral-50 p-2 sm:p-3 dark:bg-neutral-950">
			{useCase.demo && <HeroChatDemo demo={useCase.demo} reduceMotion={reduceMotion} />}
		</div>
	);

	const card = (
		<div className="relative overflow-hidden rounded-tl-xl rounded-tr-xl bg-white shadow-sm ring-1 shadow-black/10 ring-black/10 dark:bg-neutral-950">
			<div className="flex items-center gap-3 border-b border-neutral-200/60 px-4 py-3 sm:px-6 sm:py-4 dark:border-neutral-700/60">
				<div className="min-w-0">
					<h3 className="truncate text-base font-semibold text-neutral-900 sm:text-lg dark:text-white">
						{useCase.title}
					</h3>
					<p className="text-sm text-neutral-500 text-pretty dark:text-neutral-400">
						{useCase.description}
					</p>
				</div>
			</div>
			{media}
		</div>
	);

	return (
		<>
			{reduceMotion ? (
				card
			) : (
				<motion.div
					initial={{ opacity: 0, scale: 0.99, filter: "blur(10px)" }}
					animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
					transition={{ duration: 0.3, ease: "easeOut" }}
					className="will-change-transform"
				>
					{card}
				</motion.div>
			)}

			<AnimatePresence>
				{expanded && hasVideo && (
					<ExpandedMediaOverlay
						src={useCase.src as string}
						alt={`${useCase.title} demo`}
						onClose={close}
					/>
				)}
			</AnimatePresence>
		</>
	);
});

const CategoryPanel = memo(function CategoryPanel({
	category,
	reduceMotion,
}: {
	category: HeroCategory;
	reduceMotion: boolean;
}) {
	return (
		<div className="flex w-full flex-col gap-3">
			<Tabs
				defaultValue={category.useCases[0]?.id}
				orientation="vertical"
				className="flex w-full flex-col gap-3 md:flex-row md:gap-4"
			>
				<ScrollArea className="w-full md:w-56 md:shrink-0">
					<TabsList className="flex h-auto w-max gap-1 bg-transparent p-0 md:w-full md:flex-col md:items-stretch">
						{category.useCases.map((useCase) => (
							<TabsTrigger
								key={useCase.id}
								value={useCase.id}
								className="h-auto shrink-0 touch-manipulation justify-start rounded-md px-3 py-2 text-left text-xs whitespace-normal data-[state=active]:bg-background data-[state=active]:shadow-sm sm:text-sm md:w-full"
							>
								{useCase.title}
							</TabsTrigger>
						))}
					</TabsList>
					<ScrollBar orientation="horizontal" className="md:hidden" />
				</ScrollArea>
				<div className="min-w-0 flex-1">
					{category.useCases.map((useCase) => (
						<TabsContent key={useCase.id} value={useCase.id} className="mt-0">
							<UseCasePane useCase={useCase} reduceMotion={reduceMotion} />
						</TabsContent>
					))}
				</div>
			</Tabs>
		</div>
	);
});

const BrowserWindow = () => {
	const [activeCategory, setActiveCategory] = useState(CATEGORIES[0].id);
	const reduceMotion = useReducedMotion() ?? false;

	return (
		<Tabs
			value={activeCategory}
			onValueChange={setActiveCategory}
			className="relative my-4 flex w-full flex-col items-start justify-start gap-0 overflow-hidden rounded-2xl shadow-2xl md:my-12"
		>
			<div className="flex w-full items-center justify-start overflow-hidden bg-gray-200 py-4 pl-4 dark:bg-neutral-800">
				<div className="mr-6 flex items-center gap-2">
					<div className="size-3 rounded-full bg-red-500" />
					<div className="size-3 rounded-full bg-yellow-500" />
					<div className="size-3 rounded-full bg-green-500" />
				</div>
				<ScrollArea className="min-w-0 flex-1">
					<TabsList className="flex h-auto w-max items-center gap-1 bg-transparent p-0 pr-4">
						{CATEGORIES.map((category, index) => (
							<React.Fragment key={category.id}>
								<TabsTrigger
									value={category.id}
									className="h-auto shrink-0 touch-manipulation gap-1.5 rounded-md px-2.5 py-1 text-xs data-[state=active]:bg-background data-[state=active]:shadow sm:text-sm"
								>
									{category.label}
								</TabsTrigger>
								{index !== CATEGORIES.length - 1 && (
									<Separator
										orientation="vertical"
										className="h-4 bg-neutral-300 dark:bg-neutral-700"
									/>
								)}
							</React.Fragment>
						))}
					</TabsList>
					<ScrollBar orientation="horizontal" />
				</ScrollArea>
			</div>
			<div className="w-full overflow-hidden bg-gray-100/50 px-4 pt-4 dark:bg-neutral-950">
				{CATEGORIES.map((category) => (
					<TabsContent key={category.id} value={category.id} className="mt-0">
						<CategoryPanel category={category} reduceMotion={reduceMotion} />
					</TabsContent>
				))}
			</div>
		</Tabs>
	);
};
