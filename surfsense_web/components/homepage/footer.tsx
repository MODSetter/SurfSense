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
import { useSiteConfig } from "@/contexts/SiteConfigContext";

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
		LEMMY: IconWorld,
		OTHER: IconWorld,
	};
	return iconMap[platform] || IconWorld;
};

export function Footer() {
	const { config } = useSiteConfig();
	const [socialLinks, setSocialLinks] = useState<SocialMediaLink[]>([]);
	const [isLoading, setIsLoading] = useState(true);

	useEffect(() => {
		const fetchSocialLinks = async () => {
			try {
				const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
				const response = await fetch(`${backendUrl}/api/v1/social-media-links/public`);

				if (response.ok) {
					const links = await response.json();
					setSocialLinks(links);
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

				<div className="flex sm:flex-row flex-col justify-between mt-8 items-start sm:items-center w-full gap-8">
					<p className="text-neutral-500 dark:text-neutral-400">
						&copy; {config.custom_copyright || "SurfSense 2025"}
					</p>

					<div className="flex flex-col sm:flex-row gap-8 flex-1 justify-center">
						{config.show_pages_section && (
							<div className="flex flex-col gap-2">
								<h3 className="font-semibold text-neutral-700 dark:text-neutral-300 mb-2">Pages</h3>
								{!config.disable_pricing_route && (
									<Link
										href="/pricing"
										className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
									>
										Pricing
									</Link>
								)}
								{!config.disable_docs_route && (
									<Link
										href="/docs"
										className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
									>
										Documentation
									</Link>
								)}
								{!config.disable_contact_route && (
									<Link
										href="/contact"
										className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
									>
										Contact
									</Link>
								)}
							</div>
						)}

						{config.show_legal_section && (
							<div className="flex flex-col gap-2">
								<h3 className="font-semibold text-neutral-700 dark:text-neutral-300 mb-2">Legal</h3>
								{!config.disable_terms_route && (
									<Link
										href="/terms"
										className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
									>
										Terms of Service
									</Link>
								)}
								{!config.disable_privacy_route && (
									<Link
										href="/privacy"
										className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
									>
										Privacy Policy
									</Link>
								)}
							</div>
						)}

						{config.show_register_section && (
							<div className="flex flex-col gap-2">
								<h3 className="font-semibold text-neutral-700 dark:text-neutral-300 mb-2">Get Started</h3>
								<Link
									href="/register"
									className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
								>
									Create Account
								</Link>
								<Link
									href="/login"
									className="text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
								>
									Sign In
								</Link>
							</div>
						)}
					</div>

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
					"--offset": offset || "200px",
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
