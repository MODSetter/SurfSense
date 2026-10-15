import { format } from "date-fns";
import Image from "next/image";
import Link from "next/link";
import { siteText } from "@/components/site/site-text";
import { DotIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import type { BlogEntry } from "./page";

function truncate(text: string, length: number) {
	return text.length > length ? `${text.slice(0, length)}…` : text;
}

/** One post in the grid, in the homepage cards' shape. No motion on hover. */
export function PostCard({ blog }: { blog: BlogEntry }) {
	return (
		<Link
			href={blog.url}
			className="flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-card p-2 shadow-xs hover:border-muted-foreground/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
		>
			<div className="relative aspect-16/10 overflow-hidden rounded-xl bg-muted">
				<Image
					src={blog.image}
					alt=""
					fill
					sizes="(max-width: 639px) 100vw, (max-width: 1023px) 50vw, 33vw"
					className="object-cover"
				/>
			</div>
			<div className="flex flex-1 flex-col px-4 pt-5 pb-4">
				<h3 className={siteText.h3}>{blog.title}</h3>
				<p className={cn(siteText.body, "mt-2 flex-1 text-sm")}>
					{truncate(blog.description, 120)}
				</p>
				<p className="mt-5 flex items-center gap-2">
					<Image
						src={blog.authorAvatar}
						alt=""
						width={24}
						height={24}
						className="size-6 rounded-full object-cover"
					/>
					<span className="text-xs font-medium whitespace-nowrap text-foreground">
						{blog.author}
					</span>
					<DotIcon aria-hidden="true" className="size-3.5 text-muted-foreground" />
					<time className="text-xs whitespace-nowrap text-muted-foreground" dateTime={blog.date}>
						{format(new Date(blog.date), "MMM d, yyyy")}
					</time>
				</p>
			</div>
		</Link>
	);
}
