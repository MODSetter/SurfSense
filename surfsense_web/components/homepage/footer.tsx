"use client";
import {
	IconBrandMastodon,
	IconBook,
	IconPhoto,
	IconBrandGithub,
	IconBrandGitlab,
	IconBrandLinkedin,
	IconWorld,
	IconMail,
	IconBrandMatrix,
	IconDeviceTv,
} from "@tabler/icons-react";
import Link from "next/link";
import type React from "react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface SocialMediaLink {
	id: number;
	platform: string;
	url: string;
	label: string | null;
}

// Map platform names to icons
const getPlatformIcon = (platform: string) => {
	const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
		MASTODON: IconBrandMastodon,
		PIXELFED: IconPhoto,
		BOOKWYRM: IconBook,
		GITHUB: IconBrandGithub,
		GITLAB: IconBrandGitlab,
		LINKEDIN: IconBrandLinkedin,
		WEBSITE: IconWorld,
		EMAIL: IconMail,
		MATRIX: IconBrandMatrix,
		PEERTUBE: IconDeviceTv,
		LEMMY: IconWorld, // Using generic world icon for Lemmy
		OTHER: IconWorld,
	};
	return iconMap[platform] || IconWorld;
};

export function Footer() {
	const [socialLinks, setSocialLinks] = useState<SocialMediaLink[]>([]);
	const [isLoading, setIsLoading] = useState(true);

	useEffect(() => {
		// Fetch social media links from the public API (no auth required)
		const fetchSocialLinks = async () => {
			try {
				const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
				const response = await fetch(`${backendUrl}/api/v1/social-media-links/public`);

				if (response.ok) {
					const links = await response.json();
					setSocialLinks(links);
				} else {
					console.error("Failed to fetch social media links:", response.statusText);
				}
			} catch (error) {
				console.error("Error fetching social media links:", error);
			} finally {
				setIsLoading(false);
			}
		};

		fetchSocialLinks();
	}, []);

	return (
		<div className="border-t border-neutral-100 dark:border-white/[0.1] px-8 py-20 w-full relative overflow-hidden">
			<div className="max-w-7xl mx-auto text-sm text-neutral-500 justify-between items-start md:px-8">
				<div className="flex flex-col items-center justify-center w-full relative">
					<div className="mr-0 md:mr-4 md:flex mb-4">
						<div className="flex items-center">
							<span className="font-medium text-black dark:text-white ml-2">SurfSense</span>
						</div>
					</div>

					<GridLineHorizontal className="max-w-7xl mx-auto mt-8" />
				</div>
				<div className="flex sm:flex-row flex-col justify-between mt-8 items-center w-full">
					<p className="text-neutral-500 dark:text-neutral-400 mb-8 sm:mb-0">
						&copy; SurfSense 2025
					</p>
					{!isLoading && socialLinks.length > 0 && (
						<div className="flex gap-4">
							{socialLinks.map((link) => {
								const IconComponent = getPlatformIcon(link.platform);
								const ariaLabel = link.label || link.platform.toLowerCase();

								return (
									<Link
										key={link.id}
										href={link.url}
										target="_blank"
										rel="noopener noreferrer"
										aria-label={ariaLabel}
									>
										<IconComponent className="h-6 w-6 text-neutral-500 dark:text-neutral-300 hover:text-neutral-700 dark:hover:text-neutral-100 transition-colors" />
									</Link>
								);
							})}
						</div>
					)}
				</div>
			</div>
		</div>
	);
}

const GridLineHorizontal = ({ className, offset }: { className?: string; offset?: string }) => {
	return (
		<div
			style={
				{
					"--background": "#ffffff",
					"--color": "rgba(0, 0, 0, 0.2)",
					"--height": "1px",
					"--width": "5px",
					"--fade-stop": "90%",
					"--offset": offset || "200px", //-100px if you want to keep the line inside
					"--color-dark": "rgba(255, 255, 255, 0.2)",
					maskComposite: "exclude",
				} as React.CSSProperties
			}
			className={cn(
				"w-[calc(100%+var(--offset))] h-[var(--height)]",
				"bg-[linear-gradient(to_right,var(--color),var(--color)_50%,transparent_0,transparent)]",
				"[background-size:var(--width)_var(--height)]",
				"[mask:linear-gradient(to_left,var(--background)_var(--fade-stop),transparent),_linear-gradient(to_right,var(--background)_var(--fade-stop),transparent),_linear-gradient(black,black)]",
				"[mask-composite:exclude]",
				"z-30",
				"dark:bg-[linear-gradient(to_right,var(--color-dark),var(--color-dark)_50%,transparent_0,transparent)]",
				className
			)}
		></div>
	);
};
