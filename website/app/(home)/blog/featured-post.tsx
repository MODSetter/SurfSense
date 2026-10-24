import { format } from "date-fns";
import Image from "next/image";
import Link from "next/link";
import { siteText } from "@/components/site/site-text";
import { ArrowRightIcon, DotIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import type { BlogEntry } from "./page";

/** The lead post, laid out like the homepage's "What you get" rows. */
export function FeaturedPost({ blog }: { blog: BlogEntry }) {
	return (
		<Link
			href={blog.url}
			className="group flex flex-col overflow-hidden rounded-3xl bg-muted p-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring md:flex-row"
		>
			<div className="relative aspect-16/10 shrink-0 overflow-hidden rounded-2xl md:aspect-auto md:min-h-80 md:w-1/2">
				<Image
					src={blog.image}
					alt=""
					fill
					priority
					sizes="(max-width: 767px) 100vw, 50vw"
					className="object-cover"
				/>
			</div>
			<div className="flex flex-1 flex-col justify-center gap-4 p-6 md:p-10">
				<p className="flex flex-wrap items-center gap-x-3 gap-y-2 text-xs font-medium text-muted-foreground">
					<span className="rounded-full bg-card px-2.5 py-1 text-foreground">Featured</span>
					{/* One unit, so a narrow screen wraps it whole instead of mid-name. */}
					<span className="flex items-center gap-1.5 whitespace-nowrap">
						{blog.author}
						<DotIcon aria-hidden="true" className="size-3.5" />
						<time dateTime={blog.date}>{format(new Date(blog.date), "MMM d, yyyy")}</time>
					</span>
				</p>
				<h2 className="text-2xl leading-snug font-medium tracking-tight text-balance text-foreground md:text-3xl">
					{blog.title}
				</h2>
				<p className={cn(siteText.body, "line-clamp-3")}>{blog.description}</p>
				<p className="inline-flex items-center gap-1.5 text-sm font-medium text-primary group-hover:text-foreground">
					Read the post <ArrowRightIcon aria-hidden="true" className="size-4" />
				</p>
			</div>
		</Link>
	);
}
