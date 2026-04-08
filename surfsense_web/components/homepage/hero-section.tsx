"use client";
import { Download, Monitor } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import React, { memo, useCallback, useEffect, useRef, useState } from "react";
import Balancer from "react-wrap-balancer";
import { ExpandedMediaOverlay, useExpandedMedia } from "@/components/ui/expanded-gif-overlay";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { AUTH_TYPE, BACKEND_URL } from "@/lib/env-config";
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

const TAB_ITEMS = [
	{
		title: "General Assist",
		description: "Launch SurfSense instantly from any application.",
		src: "/homepage/hero_tutorial/general_assist.mp4",
		featured: true,
	},
	{
		title: "Quick Assist",
		description: "Select text anywhere, then ask AI to explain, rewrite, or act on it.",
		src: "/homepage/hero_tutorial/quick_assist.mp4",
		featured: true,
	},
	{
		title: "Extreme Assist",
		description: "Get inline writing suggestions powered by your knowledge base as you type in any app.",
		src: "/homepage/hero_tutorial/extreme_assist.mp4",
		featured: true,
	},
	{
		title: "Watch Local Folder",
		description: "Watch a local folder and automatically sync file changes to your knowledge base. Works great with Obsidian vaults.",
		src: "/homepage/hero_tutorial/folder_watch.mp4",
		featured: true,
	},
	// {
	// 	title: "Connect & Sync",
	// 	description:
	// 		"Connect data sources like Notion, Drive and Gmail. Automatically sync to keep them updated.",
	// 	src: "/homepage/hero_tutorial/ConnectorFlowGif.mp4",
	// 	featured: true,
	// },
	// {
	// 	title: "Upload Documents",
	// 	description: "Upload documents directly, from images to massive PDFs.",
	// 	src: "/homepage/hero_tutorial/DocUploadGif.mp4",
	// 	featured: true,
	// },
	{
		title: "Video & Presentations",
		description: "Create short videos and editable presentations with AI-generated visuals and narration from your sources.",
		src: "/homepage/hero_tutorial/video_gen_surf.mp4",
		featured: false,
	},
	{
		title: "Search & Citation",
		description: "Ask questions and get cited responses from your knowledge base.",
		src: "/homepage/hero_tutorial/BSNCGif.mp4",
		featured: false,
	},
	{
		title: "Document Q&A",
		description: "Mention specific documents in chat for targeted answers.",
		src: "/homepage/hero_tutorial/BQnaGif_compressed.mp4",
		featured: false,
	},
	{
		title: "Reports",
		description: "Generate reports from your sources in many formats.",
		src: "/homepage/hero_tutorial/ReportGenGif_compressed.mp4",
		featured: false,
	},
	{
		title: "Podcasts",
		description: "Turn anything into a podcast in under 20 seconds.",
		src: "/homepage/hero_tutorial/PodcastGenGif.mp4",
		featured: false,
	},
	{
		title: "Image Generation",
		description: "Generate high-quality images easily from your conversations.",
		src: "/homepage/hero_tutorial/ImageGenGif.mp4",
		featured: false,
	},
	{
		title: "Collaborative Chat",
		description: "Collaborate on AI-powered conversations in realtime with your team.",
		src: "/homepage/hero_realtime/RealTimeChatGif.mp4",
		featured: false,
	},
	{
		title: "Comments",
		description: "Add comments and tag teammates on any message.",
		src: "/homepage/hero_realtime/RealTimeCommentsFlow.mp4",
		featured: false,
	},
] as const;

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
						<h2
							className={cn(
								"relative mb-8 max-w-2xl text-left text-sm tracking-wide text-neutral-600 antialiased sm:text-base md:text-xl dark:text-neutral-400"
							)}
						>
							An open source, privacy focused alternative to NotebookLM for teams with no data
							limits.
						</h2>

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
	const isGoogleAuth = AUTH_TYPE === "GOOGLE";

	const handleGoogleLogin = () => {
		trackLoginAttempt("google");
		window.location.href = `${BACKEND_URL}/auth/google/authorize-redirect`;
	};

	if (isGoogleAuth) {
		return (
			<button
				type="button"
				onClick={handleGoogleLogin}
				className="flex h-14 w-full cursor-pointer items-center justify-center gap-3 rounded-lg bg-white text-center text-base font-medium text-neutral-700 shadow-sm ring-1 shadow-black/10 ring-black/10 transition duration-150 active:scale-98 hover:bg-neutral-50 sm:w-56 dark:bg-neutral-900 dark:text-neutral-200 dark:ring-neutral-700/50 dark:hover:bg-neutral-800"
			>
				<GoogleLogo className="h-5 w-5" />
				<span>Continue with Google</span>
			</button>
		);
	}

	return (
		<Link
			href="/login"
			className="flex h-14 w-full items-center justify-center rounded-lg bg-black text-center text-base font-medium text-white shadow-sm ring-1 shadow-black/10 ring-black/10 transition duration-150 active:scale-98 sm:w-52 dark:bg-white dark:text-black"
		>
			Get Started
		</Link>
	);
}

function useUserOS() {
	const [os, setOs] = useState<"macOS" | "Windows" | "Linux">("macOS");
	useEffect(() => {
		const ua = navigator.userAgent;
		if (/Windows/i.test(ua)) setOs("Windows");
		else if (/Linux/i.test(ua)) setOs("Linux");
		else setOs("macOS");
	}, []);
	return os;
}

function DownloadButton() {
	const os = useUserOS();
	return (
		<a
			href={GITHUB_RELEASES_URL}
			target="_blank"
			rel="noopener noreferrer"
			className="flex h-14 w-full items-center justify-center gap-2 rounded-lg border border-neutral-200 bg-white text-center text-base font-medium text-neutral-700 shadow-sm transition duration-150 active:scale-98 hover:bg-neutral-50 sm:w-56 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
		>
			<Download className="size-4" />
			Download for {os}
		</a>
	);
}

const BrowserWindow = () => {
	const [selectedIndex, setSelectedIndex] = useState(0);
	const selectedItem = TAB_ITEMS[selectedIndex];
	const { expanded, open, close } = useExpandedMedia();

	return (
		<>
			<motion.div className="relative my-4 flex w-full flex-col items-start justify-start overflow-hidden rounded-2xl shadow-2xl md:my-12">
				<div className="flex w-full items-center justify-start overflow-hidden bg-gray-200 py-4 pl-4 dark:bg-neutral-800">
					<div className="mr-6 flex items-center gap-2">
						<div className="size-3 rounded-full bg-red-500" />
						<div className="size-3 rounded-full bg-yellow-500" />
						<div className="size-3 rounded-full bg-green-500" />
					</div>
					<div className="no-visible-scrollbar flex min-w-0 shrink flex-row items-center justify-start gap-2 overflow-x-auto mask-l-from-98% py-0.5 pr-2 pl-2 md:pl-4">
						{TAB_ITEMS.map((item, index) => (
							<React.Fragment key={item.title}>
								<button
									type="button"
									onClick={() => setSelectedIndex(index)}
									className={cn(
										"flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-xs transition duration-150 hover:bg-white sm:text-sm dark:hover:bg-neutral-950",
										selectedIndex === index &&
											!item.featured &&
											"bg-white shadow ring-1 shadow-black/10 ring-black/10 dark:bg-neutral-900",
										selectedIndex === index &&
											item.featured &&
											"bg-amber-50 shadow ring-1 shadow-amber-200/50 ring-amber-400/60 dark:bg-amber-950/40 dark:shadow-amber-900/30 dark:ring-amber-500/50",
										item.featured &&
											selectedIndex !== index &&
											"hover:bg-amber-50 dark:hover:bg-amber-950/30"
									)}
								>
									{item.title}
									{item.featured && (
										<Tooltip>
											<TooltipTrigger asChild>
												<span className="inline-flex shrink-0 items-center justify-center rounded border border-amber-300 bg-amber-100 p-0.5 text-amber-700 dark:border-amber-700 dark:bg-amber-900/50 dark:text-amber-400">
													<Monitor className="size-3" />
												</span>
											</TooltipTrigger>
											<TooltipContent side="bottom">Desktop app only</TooltipContent>
										</Tooltip>
									)}
								</button>
								{index !== TAB_ITEMS.length - 1 && (
									<div className="h-4 w-px shrink-0 rounded-full bg-neutral-300 dark:bg-neutral-700" />
								)}
							</React.Fragment>
						))}
					</div>
				</div>
				<div className="w-full overflow-hidden bg-gray-100/50 px-4 pt-4 perspective-distant dark:bg-neutral-950">
					<AnimatePresence mode="wait">
						<motion.div
							initial={{
								opacity: 0,
								scale: 0.99,
								filter: "blur(10px)",
							}}
							animate={{
								opacity: 1,
								scale: 1,
								filter: "blur(0px)",
							}}
							exit={{
								opacity: 0,
								scale: 0.98,
								filter: "blur(10px)",
							}}
							transition={{
								duration: 0.3,
								ease: "easeOut",
							}}
							key={selectedItem.title}
							className="relative overflow-hidden rounded-tl-xl rounded-tr-xl bg-white shadow-sm ring-1 shadow-black/10 ring-black/10 will-change-transform dark:bg-neutral-950"
						>
							<div className="flex items-center gap-3 border-b border-neutral-200/60 px-4 py-3 sm:px-6 sm:py-4 dark:border-neutral-700/60">
								<div className="min-w-0">
									<h3 className="truncate text-base font-semibold text-neutral-900 sm:text-lg dark:text-white">
										{selectedItem.title}
									</h3>
									<p className="text-sm text-neutral-500 dark:text-neutral-400">
										{selectedItem.description}
									</p>
								</div>
							</div>
							<button
								type="button"
								className="cursor-pointer bg-neutral-50 p-2 sm:p-3 dark:bg-neutral-950 w-full"
								onClick={open}
							>
								<TabVideo src={selectedItem.src} />
							</button>
						</motion.div>
					</AnimatePresence>
				</div>
			</motion.div>

			<AnimatePresence>
				{expanded && (
					<ExpandedMediaOverlay src={selectedItem.src} alt={selectedItem.title} onClose={close} />
				)}
			</AnimatePresence>
		</>
	);
};

const TabVideo = memo(function TabVideo({ src }: { src: string }) {
	const videoRef = useRef<HTMLVideoElement>(null);
	const [hasLoaded, setHasLoaded] = useState(false);

	useEffect(() => {
		setHasLoaded(false);
		const video = videoRef.current;
		if (!video) return;
		video.currentTime = 0;
		video.play().catch(() => {});
	}, [src]);

	const handleCanPlay = useCallback(() => {
		setHasLoaded(true);
	}, []);

	return (
		<div className="relative">
			<video
				ref={videoRef}
				key={src}
				src={src}
				preload="auto"
				loop
				muted
				playsInline
				onCanPlay={handleCanPlay}
				className="aspect-video w-full rounded-lg sm:rounded-xl"
			/>
			{!hasLoaded && (
				<div className="absolute inset-0 aspect-video w-full animate-pulse rounded-lg bg-neutral-100 sm:rounded-xl dark:bg-neutral-800" />
			)}
		</div>
	);
});

const GITHUB_RELEASES_URL = "https://github.com/MODSetter/SurfSense/releases/latest";

