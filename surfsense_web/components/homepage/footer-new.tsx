import {
	IconBrandDiscord,
	IconBrandGithub,
	IconBrandLinkedin,
	IconBrandReddit,
	IconBrandTwitter,
} from "@tabler/icons-react";
import Link from "next/link";
import { Logo } from "@/components/Logo";

export function FooterNew() {
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
			title: "Connectors",
			href: "/connectors",
		},
		{
			title: "Pricing",
			href: "/pricing",
		},
		{
			title: "Blog",
			href: "/blog",
		},
		{
			title: "Docs",
			href: "/docs",
		},
		{
			title: "Contact Us",
			href: "/contact",
		},
		{
			title: "What's New",
			href: "/announcements",
		},
	];

	const socials = [
		{
			title: "Twitter",
			href: "https://x.com/mod_setter",
			icon: IconBrandTwitter,
		},
		{
			title: "LinkedIn",
			href: "https://www.linkedin.com/company/surfsense/",
			icon: IconBrandLinkedin,
		},
		{
			title: "GitHub",
			href: "https://github.com/MODSetter",
			icon: IconBrandGithub,
		},
		{
			title: "Discord",
			href: "https://discord.gg/ejRNvftDp9",
			icon: IconBrandDiscord,
		},
		{
			title: "Reddit",
			href: "https://www.reddit.com/r/SurfSense/",
			icon: IconBrandReddit,
		},
	];
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
		<div className="border-t border-border px-8 py-20 bg-background w-full relative overflow-hidden">
			<div className="max-w-[var(--home-max,88rem)] mx-auto text-sm text-muted-foreground flex sm:flex-row flex-col justify-between items-start">
				<div>
					<div className="mr-0 md:mr-4  md:flex mb-4">
						<Logo className="h-6 w-6 rounded-md mr-2" />
						<span className="text-foreground text-lg font-bold tracking-tight">SurfSense</span>
					</div>

					<div className="mt-2 ml-2">
						&copy; SurfSense {new Date().getFullYear()}. All rights reserved.
					</div>
				</div>
				<div className="grid grid-cols-2 lg:grid-cols-4 gap-10 items-start mt-10 sm:mt-0 md:mt-0">
					<div className="flex justify-center gap-4 flex-col w-full">
						<p className="text-foreground font-semibold">Pages</p>
						<ul className="flex flex-col gap-4 list-none text-muted-foreground">
							{pages.map((page, idx) => (
								<li key={"pages" + idx} className="list-none">
									<Link
										className="transition-colors duration-150 ease-out hover:text-foreground"
										href={page.href}
									>
										{page.title}
									</Link>
								</li>
							))}
						</ul>
					</div>

					<div className="flex justify-center gap-4 flex-col">
						<p className="text-foreground font-semibold">Socials</p>
						<ul className="flex flex-col gap-4 list-none text-muted-foreground">
							{socials.map((social, idx) => {
								const Icon = social.icon;
								return (
									<li key={"social" + idx} className="list-none">
										<Link
											className="transition-colors duration-150 ease-out hover:text-foreground flex items-center gap-2"
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

					<div className="flex justify-center gap-4 flex-col">
						<p className="text-foreground font-semibold">Legal</p>
						<ul className="flex flex-col gap-4 list-none text-muted-foreground">
							{legals.map((legal, idx) => (
								<li key={"legal" + idx} className="list-none">
									<Link
										className="transition-colors duration-150 ease-out hover:text-foreground"
										href={legal.href}
									>
										{legal.title}
									</Link>
								</li>
							))}
						</ul>
					</div>
					<div className="flex justify-center gap-4 flex-col">
						<p className="text-foreground font-semibold">Register</p>
						<ul className="flex flex-col gap-4 list-none text-muted-foreground">
							{signups.map((auth, idx) => (
								<li key={"auth" + idx} className="list-none">
									<Link
										className="transition-colors duration-150 ease-out hover:text-foreground"
										href={auth.href}
									>
										{auth.title}
									</Link>
								</li>
							))}
						</ul>
					</div>
				</div>
			</div>
			<p className="text-center mt-20 text-5xl md:text-9xl lg:text-[12rem] xl:text-[13rem] font-bold tracking-tighter bg-clip-text text-transparent bg-gradient-to-b from-border to-transparent inset-x-0 select-none">
				SurfSense
			</p>
		</div>
	);
}
