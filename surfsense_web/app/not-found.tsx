import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
	title: "Page Not Found | SurfSense",
	description:
		"The page you're looking for doesn't exist. Explore SurfSense - open source enterprise AI search and knowledge management.",
};

export default function NotFound() {
	return (
		<div className="flex min-h-screen flex-col items-center justify-center px-4 text-center">
			<h1 className="text-8xl font-bold tracking-tight text-neutral-900 dark:text-neutral-100">
				404
			</h1>
			<p className="mt-4 text-xl text-neutral-600 dark:text-neutral-400">
				The page you&apos;re looking for doesn&apos;t exist.
			</p>
			<p className="mt-2 text-base text-neutral-500 dark:text-neutral-500">
				It may have been moved, or the URL might be incorrect.
			</p>
			<div className="mt-10 flex flex-col items-center gap-4 sm:flex-row">
				<Link
					href="/"
					className="rounded-lg bg-black px-6 py-3 text-sm font-medium text-white transition hover:bg-neutral-800 dark:bg-white dark:text-black dark:hover:bg-neutral-200"
				>
					Go Home
				</Link>
				<Link
					href="/docs"
					className="rounded-lg border border-neutral-200 px-6 py-3 text-sm font-medium text-neutral-700 transition hover:bg-neutral-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
				>
					Browse Docs
				</Link>
				<Link
					href="/blog"
					className="rounded-lg border border-neutral-200 px-6 py-3 text-sm font-medium text-neutral-700 transition hover:bg-neutral-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
				>
					Read Blog
				</Link>
			</div>
			<nav className="mt-16 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-neutral-500 dark:text-neutral-400">
				<Link href="/pricing" className="hover:text-neutral-900 dark:hover:text-neutral-200">
					Pricing
				</Link>
				<Link href="/contact" className="hover:text-neutral-900 dark:hover:text-neutral-200">
					Contact
				</Link>
				<Link href="/changelog" className="hover:text-neutral-900 dark:hover:text-neutral-200">
					Changelog
				</Link>
			</nav>
		</div>
	);
}
