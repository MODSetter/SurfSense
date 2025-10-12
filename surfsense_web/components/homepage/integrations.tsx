"use client";
import React, { useEffect, useState } from "react";

interface Integration {
	name: string;
	icon: string;
}

const INTEGRATIONS: Integration[] = [
	// Search
	{ name: "Tavily", icon: "https://www.tavily.com/images/logo.svg" },
	{
		name: "LinkUp",
		icon: "https://framerusercontent.com/images/7zeIm6t3f1HaSltkw8upEvsD80.png?scale-down-to=512",
	},
	{ name: "Elasticsearch", icon: "https://cdn.simpleicons.org/elastic/00A9E5" },

	// Communication
	{ name: "Slack", icon: "https://cdn.simpleicons.org/slack/4A154B" },
	{ name: "Discord", icon: "https://cdn.simpleicons.org/discord/5865F2" },
	{ name: "Gmail", icon: "https://cdn.simpleicons.org/gmail/EA4335" },

	// Project Management
	{ name: "Linear", icon: "https://cdn.simpleicons.org/linear/5E6AD2" },
	{ name: "Jira", icon: "https://cdn.simpleicons.org/jira/0052CC" },
	{ name: "ClickUp", icon: "https://cdn.simpleicons.org/clickup/7B68EE" },
	{ name: "Airtable", icon: "https://cdn.simpleicons.org/airtable/18BFFF" },

	// Documentation & Knowledge
	{ name: "Confluence", icon: "https://cdn.simpleicons.org/confluence/172B4D" },
	{ name: "Notion", icon: "https://cdn.simpleicons.org/notion/000000/ffffff" },

	// Cloud Storage
	{ name: "Google Drive", icon: "https://cdn.simpleicons.org/googledrive/4285F4" },
	{ name: "Dropbox", icon: "https://cdn.simpleicons.org/dropbox/0061FF" },
	{
		name: "Amazon S3",
		icon: "https://upload.wikimedia.org/wikipedia/commons/b/bc/Amazon-S3-Logo.svg",
	},

	// Development
	{ name: "GitHub", icon: "https://cdn.simpleicons.org/github/181717/ffffff" },

	// Productivity
	{ name: "Google Calendar", icon: "https://cdn.simpleicons.org/googlecalendar/4285F4" },
	{ name: "Luma", icon: "https://images.lumacdn.com/social-images/default-social-202407.png" },

	// Media
	{ name: "YouTube", icon: "https://cdn.simpleicons.org/youtube/FF0000" },
];

function SemiCircleOrbit({ radius, centerX, centerY, count, iconSize, startIndex }: any) {
	return (
		<>
			{/* Semi-circle glow background */}
			<div className="absolute inset-0 flex justify-center items-start overflow-visible">
				<div
					className="
            w-[800px] h-[800px] rounded-full 
            bg-[radial-gradient(circle_at_center,rgba(0,0,0,0.15),transparent_70%)]
            dark:bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.15),transparent_70%)]
            blur-3xl 
            pointer-events-none
          "
					style={{
						zIndex: 0,
						transform: "translateY(-20%)",
					}}
				/>
			</div>

			{/* Orbit icons */}
			{Array.from({ length: count }).map((_, index) => {
				const actualIndex = startIndex + index;
				// Skip if we've run out of integrations
				if (actualIndex >= INTEGRATIONS.length) return null;

				const angle = (index / (count - 1)) * 180;
				const x = radius * Math.cos((angle * Math.PI) / 180);
				const y = radius * Math.sin((angle * Math.PI) / 180);
				const integration = INTEGRATIONS[actualIndex];

				// Tooltip positioning — above or below based on angle
				const tooltipAbove = angle > 90;

				return (
					<div
						key={index}
						className="absolute flex flex-col items-center group"
						style={{
							left: `${centerX + x - iconSize / 2}px`,
							top: `${centerY - y - iconSize / 2}px`,
							zIndex: 5,
						}}
					>
						<img
							src={integration.icon}
							alt={integration.name}
							width={iconSize}
							height={iconSize}
							className="object-contain cursor-pointer transition-transform hover:scale-110"
							style={{ minWidth: iconSize, minHeight: iconSize }} // fix accidental shrink
						/>

						{/* Tooltip */}
						<div
							className={`absolute ${
								tooltipAbove ? "bottom-[calc(100%+8px)]" : "top-[calc(100%+8px)]"
							} hidden group-hover:block w-auto min-w-max rounded-lg bg-black px-3 py-1.5 text-xs text-white shadow-lg text-center whitespace-nowrap`}
						>
							{integration.name}
							<div
								className={`absolute left-1/2 -translate-x-1/2 w-3 h-3 rotate-45 bg-black ${
									tooltipAbove ? "top-full" : "bottom-full"
								}`}
							></div>
						</div>
					</div>
				);
			})}
		</>
	);
}

export default function ExternalIntegrations() {
	const [size, setSize] = useState({ width: 0, height: 0 });

	useEffect(() => {
		const updateSize = () => setSize({ width: window.innerWidth, height: window.innerHeight });
		updateSize();
		window.addEventListener("resize", updateSize);
		return () => window.removeEventListener("resize", updateSize);
	}, []);

	const baseWidth = Math.min(size.width * 0.8, 700);
	const centerX = baseWidth / 2;
	const centerY = baseWidth * 0.5;

	const iconSize =
		size.width < 480
			? Math.max(24, baseWidth * 0.05)
			: size.width < 768
				? Math.max(28, baseWidth * 0.06)
				: Math.max(32, baseWidth * 0.07);

	return (
		<section className="py-12 relative min-h-screen w-full overflow-visible">
			<div className="relative flex flex-col items-center text-center z-10">
				<h1 className="my-6 text-4xl font-bold lg:text-7xl">Integrations</h1>
				<p className="mb-12 max-w-2xl text-gray-600 dark:text-gray-400 lg:text-xl">
					Integrate with your team's most important tools
				</p>

				<div
					className="relative overflow-visible"
					style={{ width: baseWidth, height: baseWidth * 0.7, paddingBottom: "100px" }}
				>
					<SemiCircleOrbit
						radius={baseWidth * 0.22}
						centerX={centerX}
						centerY={centerY}
						count={5}
						iconSize={iconSize}
						startIndex={0}
					/>
					<SemiCircleOrbit
						radius={baseWidth * 0.36}
						centerX={centerX}
						centerY={centerY}
						count={6}
						iconSize={iconSize}
						startIndex={5}
					/>
					<SemiCircleOrbit
						radius={baseWidth * 0.5}
						centerX={centerX}
						centerY={centerY}
						count={8}
						iconSize={iconSize}
						startIndex={11}
					/>
				</div>
			</div>
		</section>
	);
}
