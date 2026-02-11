"use client";

import Image from "next/image";
import type React from "react";

interface Integration {
	name: string;
	icon: string;
}

const INTEGRATIONS: Integration[] = [
	// Search
	{ name: "Tavily", icon: "/connectors/tavily.svg" },
	{ name: "Elasticsearch", icon: "/connectors/elasticsearch.svg" },
	{ name: "Baidu Search", icon: "/connectors/baidu-search.svg" },
	{ name: "SearXNG", icon: "/connectors/searxng.svg" },

	// Communication
	{ name: "Slack", icon: "/connectors/slack.svg" },
	{ name: "Discord", icon: "/connectors/discord.svg" },
	{ name: "Gmail", icon: "/connectors/google-gmail.svg" },
	{ name: "Microsoft Teams", icon: "/connectors/microsoft-teams.svg" },

	// Project Management
	{ name: "Linear", icon: "/connectors/linear.svg" },
	{ name: "Jira", icon: "/connectors/jira.svg" },
	{ name: "ClickUp", icon: "/connectors/clickup.svg" },
	{ name: "Airtable", icon: "/connectors/airtable.svg" },

	// Documentation & Knowledge
	{ name: "Confluence", icon: "/connectors/confluence.svg" },
	{ name: "Notion", icon: "/connectors/notion.svg" },
	{ name: "BookStack", icon: "/connectors/bookstack.svg" },
	{ name: "Obsidian", icon: "/connectors/obsidian.svg" },

	// Cloud Storage
	{ name: "Google Drive", icon: "/connectors/google-drive.svg" },

	// Development
	{ name: "GitHub", icon: "/connectors/github.svg" },

	// Productivity
	{ name: "Google Calendar", icon: "/connectors/google-calendar.svg" },
	{ name: "Luma", icon: "/connectors/luma.svg" },

	// Media
	{ name: "YouTube", icon: "/connectors/youtube.svg" },

	// Search
	{ name: "Linkup", icon: "/connectors/linkup.svg" },

	// Meetings
	{ name: "Circleback", icon: "/connectors/circleback.svg" },

	// AI
	{ name: "MCP", icon: "/connectors/modelcontextprotocol.svg" },
];

// 5 vertical columns — 23 icons spread across categories
const COLUMNS: number[][] = [
	[2, 5, 10, 0, 21, 11],
	[1, 7, 20, 17],
	[13, 6, 23, 4, 16],
	[12, 8, 15, 18],
	[3, 9, 14, 22, 19],
];

// Different scroll speeds per column for organic feel (seconds)
const SCROLL_DURATIONS = [26, 32, 22, 30, 28];

function IntegrationCard({ integration }: { integration: Integration }) {
	return (
		<div
			className="w-[60px] h-[60px] sm:w-[80px] sm:h-[80px] md:w-[120px] md:h-[120px] lg:w-[140px] lg:h-[140px] rounded-[16px] sm:rounded-[20px] md:rounded-[24px] flex items-center justify-center shrink-0 select-none"
			style={{
				background: "linear-gradient(145deg, var(--card-from), var(--card-to))",
				boxShadow: "inset 0 1px 0 0 var(--card-highlight), 0 4px 24px var(--card-shadow)",
			}}
		>
			<Image
				src={integration.icon}
				alt={integration.name}
				className="w-6 h-6 sm:w-7 sm:h-7 md:w-10 md:h-10 lg:w-12 lg:h-12 object-contain select-none pointer-events-none"
				loading="lazy"
				draggable={false}
				width={48}
				height={48}
			/>
		</div>
	);
}

function ScrollingColumn({
	cards,
	scrollUp,
	duration,
	colIndex,
	isEdge,
	isEdgeAdjacent,
}: {
	cards: number[];
	scrollUp: boolean;
	duration: number;
	colIndex: number;
	isEdge: boolean;
	isEdgeAdjacent: boolean;
}) {
	// Edge columns get a heavy vertical mask; edge-adjacent columns get a lighter one to smooth the transition
	const columnMask = isEdge
		? {
				maskImage:
					"linear-gradient(to bottom, transparent 0%, transparent 20%, black 40%, black 60%, transparent 80%, transparent 100%)",
				WebkitMaskImage:
					"linear-gradient(to bottom, transparent 0%, transparent 20%, black 40%, black 60%, transparent 80%, transparent 100%)",
			}
		: isEdgeAdjacent
			? {
					maskImage:
						"linear-gradient(to bottom, transparent 0%, transparent 10%, black 30%, black 70%, transparent 90%, transparent 100%)",
					WebkitMaskImage:
						"linear-gradient(to bottom, transparent 0%, transparent 10%, black 30%, black 70%, transparent 90%, transparent 100%)",
				}
			: {};

	const cardSet = cards.map((integrationIndex, i) => (
		<IntegrationCard
			key={`${INTEGRATIONS[integrationIndex].name}-c${colIndex}-${i}`}
			integration={INTEGRATIONS[integrationIndex]}
		/>
	));

	return (
		<div
			className="flex-shrink-0 overflow-hidden"
			style={{ ...columnMask, contain: "layout style paint" }}
		>
			{/* Outer div has NO gap — each inner copy uses pb matching the gap so both halves are identical in height → seamless -50% loop */}
			<div
				className="flex flex-col"
				style={{
					animation: `${scrollUp ? "integrations-scroll-up" : "integrations-scroll-down"} ${duration}s linear infinite`,
					willChange: "transform",
					transform: "translateZ(0)",
				}}
			>
				<div className="flex flex-col gap-2 sm:gap-3 md:gap-5 lg:gap-6 pb-2 sm:pb-3 md:pb-5 lg:pb-6">
					{cardSet}
				</div>
				<div className="flex flex-col gap-2 sm:gap-3 md:gap-5 lg:gap-6 pb-2 sm:pb-3 md:pb-5 lg:pb-6">
					{cardSet}
				</div>
			</div>
		</div>
	);
}

export default function ExternalIntegrations() {
	return (
		<section
			className={[
				"relative py-20 md:py-28 overflow-hidden",
				// No explicit background — inherits the page gradient for seamless blending
				// CSS custom properties — light mode (card styling)
				"[--card-from:rgba(255,255,255,0.9)]",
				"[--card-to:rgba(245,245,248,0.92)]",
				"[--card-highlight:rgba(255,255,255,0.5)]",
				"[--card-lowlight:transparent]",
				"[--card-shadow:transparent]",
				"[--card-border:transparent]",
				// CSS custom properties — dark mode (card styling)
				"dark:[--card-from:rgb(28,28,32)]",
				"dark:[--card-to:rgb(28,28,32)]",
				"dark:[--card-highlight:rgba(255,255,255,0.03)]",
				"dark:[--card-lowlight:rgba(0,0,0,0.1)]",
				"dark:[--card-shadow:rgba(0,0,0,0.15)]",
				"dark:[--card-border:rgba(255,255,255,0.03)]",
			].join(" ")}
		>
			{/* Heading */}
			<div className="text-center mb-12 md:mb-16 relative z-20 px-4">
				<h3 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold text-gray-900 dark:text-white leading-[1.1] tracking-tight">
					Integrate with your
					<br />
					team&apos;s most important tools
				</h3>
			</div>

			{/* Scrolling columns container — masked at edges so the page background shows through seamlessly */}
			<div
				className="relative"
				style={
					{
						maskImage:
							"linear-gradient(to bottom, transparent 0%, black 25%, black 70%, transparent 100%), " +
							"linear-gradient(to right, transparent 0%, black 12%, black 88%, transparent 100%)",
						WebkitMaskImage:
							"linear-gradient(to bottom, transparent 0%, black 25%, black 75%, transparent 100%), " +
							"linear-gradient(to right, transparent 0%, black 12%, black 88%, transparent 100%)",
						maskComposite: "intersect",
						WebkitMaskComposite: "source-in",
					} as React.CSSProperties
				}
			>
				{/* 5 scrolling columns */}
				<div className="flex justify-center gap-2 sm:gap-3 md:gap-5 lg:gap-6 h-[340px] sm:h-[420px] md:h-[560px] lg:h-[640px] overflow-hidden">
					{COLUMNS.map((column, colIndex) => (
						<ScrollingColumn
							key={`col-${SCROLL_DURATIONS[colIndex]}-${colIndex}`}
							cards={column}
							scrollUp={colIndex % 2 === 0}
							duration={SCROLL_DURATIONS[colIndex]}
							colIndex={colIndex}
							isEdge={colIndex === 0 || colIndex === COLUMNS.length - 1}
							isEdgeAdjacent={colIndex === 1 || colIndex === COLUMNS.length - 2}
						/>
					))}
				</div>
			</div>
		</section>
	);
}
