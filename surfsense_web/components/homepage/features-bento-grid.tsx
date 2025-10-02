import { IconMessage, IconMicrophone, IconSearch, IconUsers } from "@tabler/icons-react";
import Image from "next/image";
import React from "react";
import { BentoGrid, BentoGridItem } from "@/components/ui/bento-grid";

export function FeaturesBentoGrid() {
	return (
		<BentoGrid className="max-w-7xl my-8 mx-auto md:auto-rows-[20rem]">
			{items.map((item, i) => (
				<BentoGridItem
					key={i}
					title={item.title}
					description={item.description}
					header={item.header}
					className={item.className}
					icon={item.icon}
				/>
			))}
		</BentoGrid>
	);
}

const CitationIllustration = () => (
	<div className="relative flex w-full h-full min-h-[6rem] items-center justify-center overflow-hidden rounded-xl bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 dark:from-blue-950/20 dark:via-purple-950/20 dark:to-pink-950/20 p-4">
		<svg viewBox="0 0 400 200" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
			<title>Citation feature illustration showing clickable source reference</title>
			{/* Background chat message */}
			<g>
				{/* Chat bubble */}
				<rect
					x="20"
					y="30"
					width="200"
					height="60"
					rx="12"
					className="fill-white dark:fill-neutral-800"
					opacity="0.9"
				/>
				{/* Text lines */}
				<line
					x1="35"
					y1="50"
					x2="150"
					y2="50"
					className="stroke-neutral-400 dark:stroke-neutral-600"
					strokeWidth="3"
					strokeLinecap="round"
				/>
				<line
					x1="35"
					y1="65"
					x2="180"
					y2="65"
					className="stroke-neutral-400 dark:stroke-neutral-600"
					strokeWidth="3"
					strokeLinecap="round"
				/>

				{/* Citation badge with glow */}
				<defs>
					<filter id="glow">
						<feGaussianBlur stdDeviation="2" result="coloredBlur" />
						<feMerge>
							<feMergeNode in="coloredBlur" />
							<feMergeNode in="SourceGraphic" />
						</feMerge>
					</filter>
				</defs>

				{/* Clickable citation */}
				<g className="cursor-pointer" filter="url(#glow)">
					<rect
						x="185"
						y="57"
						width="28"
						height="20"
						rx="6"
						className="fill-blue-500 dark:fill-blue-600"
					/>
					<text
						x="199"
						y="70"
						fontSize="12"
						fontWeight="bold"
						className="fill-white"
						textAnchor="middle"
					>
						[1]
					</text>
				</g>
			</g>

			{/* Connecting line with animation effect */}
			<g>
				<path
					d="M 199 77 Q 240 90, 260 110"
					className="stroke-blue-500 dark:stroke-blue-400"
					strokeWidth="2"
					strokeDasharray="4,4"
					fill="none"
					opacity="0.6"
				>
					<animate
						attributeName="stroke-dashoffset"
						from="8"
						to="0"
						dur="1s"
						repeatCount="indefinite"
					/>
				</path>

				{/* Arrow head */}
				<polygon
					points="258,113 262,110 260,106"
					className="fill-blue-500 dark:fill-blue-400"
					opacity="0.6"
				/>
			</g>

			{/* Citation popup card */}
			<g>
				{/* Card shadow */}
				<rect
					x="245"
					y="113"
					width="145"
					height="75"
					rx="10"
					className="fill-black"
					opacity="0.1"
					transform="translate(2, 2)"
				/>

				{/* Main card */}
				<rect
					x="245"
					y="113"
					width="145"
					height="75"
					rx="10"
					className="fill-white dark:fill-neutral-800 stroke-blue-500 dark:stroke-blue-400"
					strokeWidth="2"
				/>

				{/* Card header */}
				<rect
					x="245"
					y="113"
					width="145"
					height="25"
					rx="10"
					className="fill-blue-100 dark:fill-blue-900/50"
				/>
				<line
					x1="245"
					y1="138"
					x2="390"
					y2="138"
					className="stroke-blue-200 dark:stroke-blue-800"
					strokeWidth="1"
				/>

				{/* Header text */}
				<text
					x="317.5"
					y="128"
					fontSize="9"
					fontWeight="600"
					className="fill-blue-700 dark:fill-blue-300"
					textAnchor="middle"
				>
					Referenced Chunk
				</text>

				{/* Content lines */}
				<line
					x1="255"
					y1="150"
					x2="365"
					y2="150"
					className="stroke-neutral-600 dark:stroke-neutral-400"
					strokeWidth="2.5"
					strokeLinecap="round"
				/>
				<line
					x1="255"
					y1="162"
					x2="340"
					y2="162"
					className="stroke-neutral-500 dark:stroke-neutral-500"
					strokeWidth="2.5"
					strokeLinecap="round"
				/>
				<line
					x1="255"
					y1="174"
					x2="380"
					y2="174"
					className="stroke-neutral-400 dark:stroke-neutral-600"
					strokeWidth="2.5"
					strokeLinecap="round"
				/>
			</g>

			{/* Sparkle effects */}
			<g className="opacity-60">
				{/* Sparkle 1 */}
				<circle cx="195" cy="45" r="2" className="fill-yellow-400">
					<animate attributeName="opacity" values="0;1;0" dur="2s" repeatCount="indefinite" />
				</circle>
				<circle cx="195" cy="45" r="1" className="fill-white">
					<animate attributeName="opacity" values="0;1;0" dur="2s" repeatCount="indefinite" />
				</circle>

				{/* Sparkle 2 */}
				<circle cx="370" cy="125" r="2" className="fill-purple-400">
					<animate
						attributeName="opacity"
						values="0;1;0"
						dur="2.5s"
						begin="0.5s"
						repeatCount="indefinite"
					/>
				</circle>
				<circle cx="370" cy="125" r="1" className="fill-white">
					<animate
						attributeName="opacity"
						values="0;1;0"
						dur="2.5s"
						begin="0.5s"
						repeatCount="indefinite"
					/>
				</circle>

				{/* Sparkle 3 */}
				<circle cx="250" cy="95" r="1.5" className="fill-blue-400">
					<animate
						attributeName="opacity"
						values="0;1;0"
						dur="3s"
						begin="1s"
						repeatCount="indefinite"
					/>
				</circle>
			</g>

			{/* AI Sparkle icon in corner */}
			<g transform="translate(25, 100)">
				<path
					d="M 0,0 L 3,-8 L 6,0 L 14,3 L 6,6 L 3,14 L 0,6 L -8,3 Z"
					className="fill-purple-500 dark:fill-purple-400"
					opacity="0.7"
				>
					<animateTransform
						attributeName="transform"
						type="rotate"
						from="0 3 3"
						to="360 3 3"
						dur="8s"
						repeatCount="indefinite"
					/>
				</path>
			</g>
		</svg>
	</div>
);

const CollaborationIllustration = () => (
	<div className="relative flex w-full h-full min-h-44 flex-1 flex-col items-center justify-center overflow-hidden pointer-events-none select-none">
		<div
			role="img"
			aria-label="Illustration of a realtime collaboration in a text editor."
			className="pointer-events-none absolute inset-0 flex flex-col items-start justify-center pl-4 select-none"
		>
			<div className="relative flex h-fit w-fit flex-col items-start">
				<div className="w-full text-2xl sm:text-3xl lg:text-4xl leading-tight text-neutral-700 dark:text-neutral-300">
					<span className="flex items-stretch flex-wrap">
						{/* <span>Real-time </span> */}
						<span className="relative bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 px-1">
							Real-time
						</span>
						<span className="relative z-10 inline-flex items-stretch justify-start">
							<span className="absolute h-full w-0.5 rounded-b-sm bg-blue-500"></span>
							<span className="absolute inline-flex h-6 sm:h-7 -translate-y-full items-center rounded-t-sm rounded-r-sm px-2 py-0.5 text-xs sm:text-sm font-medium text-white bg-blue-500">
								Sarah
							</span>
						</span>
						<span>collabo</span>
						<span>orat</span>
						<span className="relative z-10 inline-flex items-stretch justify-start">
							<span className="absolute h-full w-0.5 rounded-b-sm bg-purple-600 dark:bg-purple-500"></span>
							<span className="absolute inline-flex h-6 sm:h-7 -translate-y-full items-center rounded-t-sm rounded-r-sm px-2 py-0.5 text-xs sm:text-sm font-medium text-white bg-purple-600 dark:bg-purple-500">
								Josh
							</span>
						</span>
						<span>ion</span>
					</span>
				</div>
			</div>
			{/* Bottom gradient fade */}
			<div className="absolute -right-4 bottom-0 -left-4 h-24 bg-gradient-to-t from-white dark:from-black to-transparent"></div>
			{/* Right gradient fade */}
			<div className="absolute top-0 -right-4 bottom-0 w-20 bg-gradient-to-l from-white dark:from-black to-transparent"></div>
		</div>
	</div>
);

const AnnotationIllustration = () => (
	<div className="relative flex w-full h-full min-h-44 flex-1 flex-col items-center justify-center overflow-hidden pointer-events-none select-none">
		<div
			role="img"
			aria-label="Illustration of a text editor with annotation comments."
			className="pointer-events-none absolute inset-0 flex flex-col items-start justify-center pl-4 select-none md:left-1/2"
		>
			<div className="relative flex h-fit w-fit flex-col items-start justify-center gap-3.5">
				{/* Text above the comment box */}
				<div className="absolute left-0 h-fit -translate-x-full pr-7 text-3xl sm:text-4xl lg:text-5xl tracking-tight whitespace-nowrap text-neutral-400 dark:text-neutral-600">
					<span className="relative">
						Add context with
						<div className="absolute inset-0 bg-gradient-to-r from-white dark:from-black via-white dark:via-black to-transparent"></div>
					</span>{" "}
					<span className="bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300">
						comments
					</span>
				</div>

				{/* Comment card */}
				<div className="flex flex-col items-start gap-4 rounded-xl bg-neutral-100 dark:bg-neutral-900/50 px-6 py-5 text-xl sm:text-2xl lg:text-3xl max-w-md">
					<div className="truncate leading-normal text-neutral-600 dark:text-neutral-400">
						<span>Let's discuss this tomorrow!</span>
					</div>

					{/* Reaction icons */}
					<div className="flex items-center gap-3 opacity-30">
						{/* @ icon */}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							width="32"
							height="32"
							fill="none"
							viewBox="0 0 24 24"
							className="w-6 h-6 sm:w-7 sm:h-7 lg:w-8 lg:h-8"
						>
							<title>Mention icon</title>
							<g
								stroke="currentColor"
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth="1.8"
							>
								<path d="M11.998 15.6a3.6 3.6 0 1 0 0-7.2 3.6 3.6 0 0 0 0 7.2Z" />
								<path d="M15.602 8.4v4.44c0 1.326 1.026 2.52 2.28 2.52a2.544 2.544 0 0 0 2.52-2.52V12a8.4 8.4 0 1 0-3.36 6.72" />
							</g>
						</svg>

						{/* Emoji icon */}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							width="32"
							height="32"
							fill="none"
							viewBox="0 0 24 24"
							className="w-6 h-6 sm:w-7 sm:h-7 lg:w-8 lg:h-8"
						>
							<title>Emoji icon</title>
							<g
								stroke="currentColor"
								strokeLinecap="round"
								strokeLinejoin="round"
								strokeWidth="1.8"
							>
								<path d="M12.002 20.4a8.4 8.4 0 1 0 0-16.8 8.4 8.4 0 0 0 0 16.8Z" />
								<path d="M9 13.8s.9 1.8 3 1.8 3-1.8 3-1.8M9.6 9.6h.008M14.398 9.6h.009M9.597 9.9a.3.3 0 1 0 0-.6.3.3 0 0 0 0 .6ZM14.402 9.9a.3.3 0 1 0 0-.6.3.3 0 0 0 0 .6Z" />
							</g>
						</svg>

						{/* Attachment icon */}
						<svg
							width="32"
							height="32"
							viewBox="0 0 24 24"
							fill="none"
							xmlns="http://www.w3.org/2000/svg"
							className="w-6 h-6 sm:w-7 sm:h-7 lg:w-8 lg:h-8"
						>
							<title>Attachment icon</title>
							<path
								d="M16.8926 14.0829L12.425 18.4269C10.565 20.2353 7.47136 20.2353 5.61136 18.4269C3.75976 16.6269 3.75976 13.6029 5.61136 11.8029L12.4886 5.11529C13.7294 3.90809 15.7934 3.90689 17.0354 5.11169C18.2714 6.31169 18.2738 8.33009 17.039 9.53249L10.1462 16.2189C9.83929 16.5093 9.43285 16.6711 9.01036 16.6711C8.58786 16.6711 8.18142 16.5093 7.87456 16.2189C7.72623 16.0757 7.60817 15.9042 7.52737 15.7146C7.44656 15.525 7.40466 15.321 7.40416 15.1149C7.40416 14.7009 7.57216 14.3037 7.87456 14.0109L12.4178 9.59849"
								stroke="currentColor"
								strokeWidth="1.8"
							/>
						</svg>
					</div>
				</div>
			</div>

			{/* Bottom gradient fade */}
			<div className="absolute -right-4 bottom-0 -left-4 h-20 bg-gradient-to-t from-white dark:from-black to-transparent"></div>
			{/* Right gradient fade */}
			<div className="absolute top-0 -right-4 bottom-0 w-20 bg-gradient-to-l from-white dark:from-black to-transparent"></div>
		</div>
	</div>
);

const AudioCommentIllustration = () => (
	<div className="relative flex w-full h-full min-h-[6rem] overflow-hidden rounded-xl">
		<Image
			src="/homepage/comments-audio.webp"
			alt="Audio Comment Illustration"
			fill
			className="object-cover"
		/>
	</div>
);

const items = [
	{
		title: "Find, Ask, Act",
		description:
			"Get instant information, detailed updates, and cited answers across company and personal knowledge.",
		header: <CitationIllustration />,
		className: "md:col-span-2",
		icon: <IconSearch className="h-4 w-4 text-neutral-500" />,
	},
	{
		title: "Work Together in Real Time",
		description:
			"Transform your company docs into multiplayer spaces with live edits, synced content, and presence.",
		header: <CollaborationIllustration />,
		className: "md:col-span-1",
		icon: <IconUsers className="h-4 w-4 text-neutral-500" />,
	},
	{
		title: "Collaborate Beyond Text",
		description:
			"Create podcasts and multimedia your team can comment on, share, and refine together.",
		header: <AudioCommentIllustration />,
		className: "md:col-span-1",
		icon: <IconMicrophone className="h-4 w-4 text-neutral-500" />,
	},
	{
		title: "Context Where It Counts",
		description: "Add comments directly to your chats and docs for clear, in-the-moment feedback.",
		header: <AnnotationIllustration />,
		className: "md:col-span-2",
		icon: <IconMessage className="h-4 w-4 text-neutral-500" />,
	},
];
