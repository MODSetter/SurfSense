"use client";

import {
	IconBrandDiscord,
	IconBrandGithub,
	IconBrandLinkedin,
	IconBrandTwitter,
} from "@tabler/icons-react";
import Image from "next/image";
import Link from "next/link";
import React from "react";
import { Logo } from "@/components/Logo";
import { useSiteConfig } from "@/contexts/SiteConfigContext";
import { DEFAULT_COPYRIGHT_TEXT } from "@/lib/constants";

export function FooterNew() {
	const { config, isLoading } = useSiteConfig();
	const pages = [
		// {
		//   title: "All Products",
		//   href: "#",
		// },
		// {
		//   title: "Studio",
		//   href: "#",
		// },
		// {
		//   title: "Clients",
		//   href: "#",
		// },
		{
			title: "Pricing",
			href: "/pricing",
		},
		{
			title: "Docs",
			href: "/docs",
		},
		{
			title: "Contact Us",
			href: "/contact",
		},
	];

	// Build socials array dynamically from config
	const socials = React.useMemo(() => {
		const socialsList = [];
		if (config?.social_twitter) {
			socialsList.push({
				title: "Twitter",
				href: config.social_twitter,
				icon: IconBrandTwitter,
			});
		}
		if (config?.social_linkedin) {
			socialsList.push({
				title: "LinkedIn",
				href: config.social_linkedin,
				icon: IconBrandLinkedin,
			});
		}
		if (config?.social_github) {
			socialsList.push({
				title: "GitHub",
				href: config.social_github,
				icon: IconBrandGithub,
			});
		}
		if (config?.social_discord) {
			socialsList.push({
				title: "Discord",
				href: config.social_discord,
				icon: IconBrandDiscord,
			});
		}
		return socialsList;
	}, [config]);
	const legals = [
		{
			title: "Privacy Policy",
			href: "/privacy",
		},
		{
			title: "Terms of Service",
			href: "/terms",
		},
		// {
		//   title: "Cookie Policy",
		//   href: "#",
		// },
	];

	const signups = [
		{
			title: "Sign In",
			href: "/login",
		},
		// {
		//   title: "Login",
		//   href: "#",
		// },
		// {
		//   title: "Forgot Password",
		//   href: "#",
		// },
	];
	return (
		<div className="border-t border-neutral-100 dark:border-white/[0.1] px-8 py-20 bg-white dark:bg-neutral-950 w-full relative overflow-hidden">
			<div className="max-w-7xl mx-auto text-sm text-neutral-500 flex sm:flex-row flex-col justify-between items-start  md:px-8">
				<div>
					<div className="mr-0 md:mr-4  md:flex mb-4">
						<Logo className="h-6 w-6 rounded-md mr-2" />
						<span className="dark:text-white/90 text-gray-800 text-lg font-bold">SurfSense</span>
					</div>

					<div className="mt-2 ml-2">{config?.custom_copyright || DEFAULT_COPYRIGHT_TEXT}</div>
				</div>
				<div className="grid grid-cols-2 lg:grid-cols-4 gap-10 items-start mt-10 sm:mt-0 md:mt-0">
					{config?.show_pages_section && (
						<div className="flex justify-center space-y-4 flex-col w-full">
							<p className="transition-colors hover:text-text-neutral-800 text-neutral-600 dark:text-neutral-300 font-bold">
								Pages
							</p>
							<ul className="transition-colors hover:text-text-neutral-800 text-neutral-600 dark:text-neutral-300 list-none space-y-4">
								{pages.map((page, idx) => (
									<li key={"pages" + idx} className="list-none">
										<Link className="transition-colors hover:text-text-neutral-800 " href={page.href}>
											{page.title}
										</Link>
									</li>
								))}
							</ul>
						</div>
					)}

					{config?.show_socials_section && socials.length > 0 && (
						<div className="flex justify-center space-y-4 flex-col">
							<p className="transition-colors hover:text-text-neutral-800 text-neutral-600 dark:text-neutral-300 font-bold">
								Socials
							</p>
							<ul className="transition-colors hover:text-text-neutral-800 text-neutral-600 dark:text-neutral-300 list-none space-y-4">
								{socials.map((social, idx) => {
									const Icon = social.icon;
									return (
										<li key={"social" + idx} className="list-none">
											<Link
												className="transition-colors hover:text-text-neutral-800 flex items-center gap-2"
												href={social.href}
												target="_blank"
												rel="noopener noreferrer"
											>
												<Icon className="h-5 w-5" />
												{social.title}
											</Link>
										</li>
									);
								})}
							</ul>
						</div>
					)}

					{config?.show_legal_section && (
						<div className="flex justify-center space-y-4 flex-col">
							<p className="transition-colors hover:text-text-neutral-800 text-neutral-600 dark:text-neutral-300 font-bold">
								Legal
							</p>
							<ul className="transition-colors hover:text-text-neutral-800 text-neutral-600 dark:text-neutral-300 list-none space-y-4">
								{legals.map((legal, idx) => (
									<li key={"legal" + idx} className="list-none">
										<Link
											className="transition-colors hover:text-text-neutral-800 "
											href={legal.href}
										>
											{legal.title}
										</Link>
									</li>
								))}
							</ul>
						</div>
					)}
					{config?.show_register_section && (
						<div className="flex justify-center space-y-4 flex-col">
							<p className="transition-colors hover:text-text-neutral-800 text-neutral-600 dark:text-neutral-300 font-bold">
								Register
							</p>
							<ul className="transition-colors hover:text-text-neutral-800 text-neutral-600 dark:text-neutral-300 list-none space-y-4">
								{signups.map((auth, idx) => (
									<li key={"auth" + idx} className="list-none">
										<Link className="transition-colors hover:text-text-neutral-800 " href={auth.href}>
											{auth.title}
										</Link>
									</li>
								))}
							</ul>
						</div>
					)}
				</div>
			</div>
			<p className="text-center mt-20 text-5xl md:text-9xl lg:text-[12rem] xl:text-[13rem] font-bold bg-clip-text text-transparent bg-gradient-to-b from-neutral-50 dark:from-neutral-950 to-neutral-200 dark:to-neutral-800 inset-x-0">
				SurfSense
			</p>
		</div>
	);
}
