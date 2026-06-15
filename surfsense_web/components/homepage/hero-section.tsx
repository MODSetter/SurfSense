"use client";
import {
	ChevronDown,
	Clock,
	CornerDownLeft,
	Download,
	Lightbulb,
	Monitor,
	Sparkles,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import React, { memo, useCallback, useEffect, useRef, useState } from "react";
import Balancer from "react-wrap-balancer";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
	Empty,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "@/components/ui/empty";
import { ExpandedMediaOverlay, useExpandedMedia } from "@/components/ui/expanded-gif-overlay";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
	GITHUB_RELEASES_URL,
	getAssetLabel,
	usePrimaryDownload,
} from "@/lib/desktop-download-utils";
import { cn } from "@/lib/utils";

type HeroUseCase = {
	id: string;
	title: string;
	description: string;
	src: string | null;
	comingSoon?: boolean;
	examples?: string[];
};

type HeroCategory = {
	id: string;
	label: string;
	desktopOnly?: boolean;
	useCases: HeroUseCase[];
};

const HERO_TUTORIAL = "/homepage/hero_tutorial";
const HERO_REALTIME = "/homepage/hero_realtime";

const CATEGORIES: HeroCategory[] = [
	{
		id: "desktop",
		label: "Desktop App",
		desktopOnly: true,
		useCases: [
			{
				id: "general",
				title: "General Assist",
				description: "Launch SurfSense instantly from any application with a global shortcut.",
				src: `${HERO_TUTORIAL}/general_assist.mp4`,
			},
			{
				id: "quick",
				title: "Quick Assist",
				description: "Select text anywhere, then ask AI to explain, rewrite, or act on it.",
				src: `${HERO_TUTORIAL}/quick_assist.mp4`,
			},
			{
				id: "screenshot",
				title: "Screenshot Assist",
				description: "Capture any region of your screen and ask AI about what’s in it.",
				src: `${HERO_TUTORIAL}/screenshot_assist.mp4`,
			},
			{
				id: "watch-folder",
				title: "Watch Local Folder",
				description: "Auto-sync a local folder to your knowledge base. Great for Obsidian vaults.",
				src: `${HERO_TUTORIAL}/folder_watch.mp4`,
			},
		],
	},
	{
		id: "deliverables",
		label: "Deliverable Studio",
		useCases: [
			{
				id: "report",
				title: "AI Report Generator",
				description:
					"Generate cited research reports from your documents, then export to PDF or Markdown.",
				src: `${HERO_TUTORIAL}/ReportGenGif_compressed.mp4`,
			},
			{
				id: "podcast",
				title: "AI Podcast Generator",
				description: "Turn any document or folder into a two-host AI podcast in under 20 seconds.",
				src: `${HERO_TUTORIAL}/PodcastGenGif.mp4`,
			},
			{
				id: "presentation",
				title: "AI Presentation & Video Maker",
				description: "Create editable slide decks and narrated video overviews from your sources.",
				src: `${HERO_TUTORIAL}/video_gen_surf.mp4`,
			},
			{
				id: "image",
				title: "AI Image Generator",
				description: "Generate high-quality images straight from your chats and documents.",
				src: `${HERO_TUTORIAL}/ImageGenGif.mp4`,
			},
			{
				id: "resume",
				title: "AI Resume Builder",
				description: "Tailor your existing resume to any job description and beat the ATS.",
				src: null,
				comingSoon: true,
				examples: [
					"Tailor my resume to this job description so it gets past ATS and lands an interview.",
					"Optimize my resume for ATS by matching the keywords in this job posting.",
					"Rewrite my resume bullet points to highlight the skills this role is asking for.",
					"Compare my resume against this job description and list the gaps to fix.",
					"Write a matching cover letter from my resume and this job description.",
				],
			},
		],
	},
	{
		id: "automations",
		label: "Automations",
		useCases: [
			{
				id: "schedule",
				title: "Scheduled AI Workflows",
				description: "Run an agent on a schedule: daily briefs, weekly digests, recurring reports.",
				src: null,
				comingSoon: true,
				examples: [
					"Email me a daily brief of new documents in my knowledge base every morning.",
					"Generate a weekly status report from my Slack and Gmail every Friday.",
					"Run a monthly competitor analysis report and save it to my workspace.",
					"Summarize my GitHub and Linear activity into a daily standup update.",
					"Create a recurring weekly research report on the topics I track.",
				],
			},
			{
				id: "event",
				title: "Event-Triggered Automations",
				description:
					"Fire an agent the moment a document lands in a folder, then post the result to your tools.",
				src: null,
				comingSoon: true,
				examples: [
					"When a PDF lands in my Research folder, generate a cited AI summary.",
					"When new meeting notes are added, turn them into meeting minutes with action items.",
					"When an invoice is uploaded, extract the vendor, total, and due date into a table.",
					"When a contract enters my Legal folder, flag key terms and renewal dates.",
					"When a resume is added to Candidates, screen it against the job description.",
				],
			},
			{
				id: "chat-built",
				title: "Chat-Built Automations",
				description: "Describe an automation in plain English and SurfSense builds it for you.",
				src: null,
				comingSoon: true,
				examples: [
					"Build an AI agent that emails me a summary of new Notion pages each morning.",
					"Create a no-code automation that posts a weekly research digest to Slack.",
					"Set up an AI note taker that turns new meeting notes into minutes.",
					"Make a workflow that extracts action items from meeting notes and assigns owners.",
					"Automate a daily email brief from my Gmail and Google Drive.",
				],
			},
		],
	},
	{
		id: "search-chat",
		label: "Search & Chat",
		useCases: [
			{
				id: "chat-docs",
				title: "Chat With Your PDFs & Docs",
				description: "Ask questions across all your files and get answers with inline citations.",
				src: `${HERO_TUTORIAL}/BQnaGif_compressed.mp4`,
			},
			{
				id: "search",
				title: "AI Search With Citations",
				description: "Hybrid semantic and keyword search across your entire knowledge base.",
				src: `${HERO_TUTORIAL}/BSNCGif.mp4`,
			},
			{
				id: "collab",
				title: "Collaborative AI Chat",
				description: "Work on AI conversations with your team in real time.",
				src: `${HERO_REALTIME}/RealTimeChatGif.mp4`,
			},
			{
				id: "comments",
				title: "Comments & Mentions",
				description: "Comment and tag teammates on any AI message.",
				src: `${HERO_REALTIME}/RealTimeCommentsFlow.mp4`,
			},
		],
	},
	{
		id: "connectors",
		label: "Connectors & Integrations",
		useCases: [
			{
				id: "connect",
				title: "Connect & Sync Your Tools",
				description:
					"Sync Notion, Slack, Google Drive, Gmail, GitHub, Linear and 25+ sources into one searchable corpus.",
				src: `${HERO_TUTORIAL}/ConnectorFlowGif.mp4`,
			},
			{
				id: "upload",
				title: "Chat With Uploaded Files",
				description: "Drop in PDFs, Office docs, images and audio. Instantly searchable.",
				src: `${HERO_TUTORIAL}/DocUploadGif.mp4`,
			},
			{
				id: "write-back",
				title: "Connector Write-Back",
				description: "Let the agent post results back to Notion, Slack, Linear and Drive.",
				src: null,
				comingSoon: true,
				examples: [
					"Post this research summary to my Notion workspace.",
					"Send these meeting action items to our team Slack channel.",
					"Create a Jira ticket from this bug report.",
					"Open a Linear issue from this feature request.",
					"Save this generated report to Google Drive as a doc.",
				],
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
						"relative mt-4 max-w-7xl text-left text-4xl font-bold tracking-tight text-balance text-neutral-900 sm:text-5xl md:text-6xl xl:text-8xl dark:text-neutral-50"
					)}
				>
					<Balancer>NotebookLM for Teams</Balancer>
				</h1>
				<div className="mt-4 flex w-full flex-col items-start justify-between gap-4 md:mt-12 md:flex-row md:items-end md:gap-10">
					<div>
						<p
							className={cn(
								"relative mb-8 max-w-2xl text-left text-sm tracking-wide text-neutral-600 antialiased sm:text-base md:text-xl dark:text-neutral-400"
							)}
						>
							A free, open source NotebookLM alternative for teams with no data limits. Use ChatGPT,
							Claude AI, and any AI model for free.
						</p>

						<div className="relative mb-4 flex w-full flex-col justify-center gap-y-2 sm:flex-row sm:justify-start sm:space-y-0 sm:space-x-4">
							<DownloadButton />
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
	return (
		<Button
			asChild
			variant="ghost"
			className="h-14 w-full rounded-lg bg-black text-center text-base font-medium text-white shadow-sm ring-1 shadow-black/10 ring-black/10 transition duration-150 active:scale-98 hover:bg-black sm:w-52 dark:bg-white dark:text-black dark:hover:bg-white"
		>
			<Link href="/login">Get Started</Link>
		</Button>
	);
}

function DownloadButton() {
	const { os, primary, alternatives, isMobileOS } = usePrimaryDownload();

	const fallbackUrl = GITHUB_RELEASES_URL;
	const mobileDisabledLabel = "Desktop app unavailable on mobile";

	if (isMobileOS) {
		return (
			<Button
				type="button"
				variant="ghost"
				disabled
				className="h-14 w-full gap-2 rounded-lg border border-neutral-200 bg-white text-center text-base font-medium text-neutral-700 shadow-sm transition duration-150 sm:w-auto sm:px-6 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200"
			>
				<Download className="size-4" />
				{mobileDisabledLabel}
			</Button>
		);
	}

	if (!primary) {
		return (
			<Button
				asChild
				variant="ghost"
				className="h-14 w-full gap-2 rounded-lg border border-neutral-200 bg-white text-center text-base font-medium text-neutral-700 shadow-sm transition duration-150 active:scale-98 hover:bg-neutral-50 sm:w-auto sm:px-6 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
			>
				<a href={fallbackUrl} target="_blank" rel="noopener noreferrer">
					<Download className="size-4" />
					Download for {os}
				</a>
			</Button>
		);
	}

	return (
		<div className="flex h-14 w-full items-stretch sm:w-auto">
			<Button
				asChild
				variant="ghost"
				className="h-auto flex-1 gap-2 rounded-l-lg rounded-r-none border border-r-0 border-neutral-200 bg-white px-5 text-base font-medium text-neutral-700 shadow-sm transition duration-150 active:scale-[0.99] hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
			>
				<a href={primary.url}>
					<Download className="size-4 shrink-0" />
					Download for {os}
				</a>
			</Button>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button
						type="button"
						variant="ghost"
						className="h-auto rounded-l-none rounded-r-lg border border-neutral-200 bg-white px-2.5 text-neutral-500 shadow-sm transition duration-150 hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-800"
					>
						<ChevronDown className="size-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end" className="w-64">
					{alternatives.map((asset) => (
						<DropdownMenuItem key={asset.name} asChild>
							<a href={asset.url} className="cursor-pointer">
								<Download className="mr-2 size-3.5" />
								{getAssetLabel(asset.name)}
							</a>
						</DropdownMenuItem>
					))}
					<DropdownMenuItem asChild>
						<a
							href={fallbackUrl}
							target="_blank"
							rel="noopener noreferrer"
							className="cursor-pointer"
						>
							All downloads
						</a>
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
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

const UseCasePlaceholder = ({ title }: { title: string }) => (
	<Empty className="size-full justify-center rounded-lg border border-dashed bg-muted/30 sm:rounded-xl">
		<EmptyHeader>
			<EmptyMedia variant="icon">
				<Clock aria-hidden="true" />
			</EmptyMedia>
			<EmptyTitle>Demo coming soon</EmptyTitle>
			<EmptyDescription className="text-pretty">{`A walkthrough of ${title} is on the way.`}</EmptyDescription>
		</EmptyHeader>
	</Empty>
);

const UseCaseExamples = ({ examples }: { examples: string[] }) => (
	<div className="flex size-full flex-col gap-3 rounded-lg border border-dashed bg-muted/30 p-4 sm:rounded-xl sm:p-5">
		<div className="flex items-center gap-2">
			<Lightbulb aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
			<p className="text-sm font-medium text-foreground">Try prompts like these today</p>
		</div>
		<ul className="flex min-w-0 flex-col gap-2">
			{examples.map((example) => (
				<li key={example}>
					<div className="flex items-start gap-2.5 rounded-md border bg-background px-3 py-2">
						<CornerDownLeft
							aria-hidden="true"
							className="mt-0.5 size-3.5 shrink-0 text-muted-foreground/70"
						/>
						<span className="min-w-0 text-sm text-pretty text-muted-foreground">{example}</span>
					</div>
				</li>
			))}
		</ul>
	</div>
);

const DesktopBadge = () => (
	<Tooltip>
		<TooltipTrigger asChild>
			<span className="ml-0.5 inline-flex items-center text-amber-600 dark:text-amber-400">
				<Monitor aria-hidden="true" className="size-3.5" />
				<span className="sr-only">Desktop app only</span>
			</span>
		</TooltipTrigger>
		<TooltipContent side="bottom">Desktop app only</TooltipContent>
	</Tooltip>
);

const UseCasePane = memo(function UseCasePane({
	useCase,
	reduceMotion,
}: {
	useCase: HeroUseCase;
	reduceMotion: boolean;
}) {
	const { expanded, open, close } = useExpandedMedia();
	const hasVideo = !useCase.comingSoon && Boolean(useCase.src);

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
			{useCase.examples && useCase.examples.length > 0 ? (
				<UseCaseExamples examples={useCase.examples} />
			) : (
				<div className="aspect-video w-full">
					<UseCasePlaceholder title={useCase.title} />
				</div>
			)}
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
			{category.desktopOnly && (
				<div className="flex items-start gap-2 rounded-lg border border-amber-300/60 bg-amber-50 px-3 py-2 text-xs text-amber-800 sm:text-sm dark:border-amber-500/40 dark:bg-amber-950/30 dark:text-amber-200">
					<Sparkles aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
					<span className="text-pretty">
						The desktop app includes everything in SurfSense, plus these native-only superpowers.
					</span>
				</div>
			)}
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
									className={cn(
										"h-auto shrink-0 touch-manipulation gap-1.5 rounded-md px-2.5 py-1 text-xs sm:text-sm",
										category.desktopOnly
											? "bg-amber-100/70 text-amber-800 hover:bg-amber-100 data-[state=active]:bg-amber-200/80 data-[state=active]:text-amber-900 data-[state=active]:shadow-sm dark:bg-amber-950/40 dark:text-amber-200 dark:hover:bg-amber-900/40 dark:data-[state=active]:bg-amber-900/60 dark:data-[state=active]:text-amber-50"
											: "data-[state=active]:bg-background data-[state=active]:shadow"
									)}
								>
									{category.label}
									{category.desktopOnly && <DesktopBadge />}
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
