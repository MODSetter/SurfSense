import { Skeleton } from "@/components/ui/skeleton";

export default function BlogPostLoading() {
	return (
		<div className="ss-home-pad pt-16 pb-20">
			<div className="mx-auto max-w-3xl">
				{/* Cover image */}
				<Skeleton className="mb-8 aspect-2/1 w-full rounded-none" />

				{/* Tags */}
				<div className="mb-4 flex flex-wrap gap-2">
					<Skeleton className="h-6 w-16 rounded-full" />
					<Skeleton className="h-6 w-20 rounded-full" />
				</div>

				{/* Title */}
				<div className="mb-6 space-y-3">
					<Skeleton className="h-10 w-full" />
					<Skeleton className="h-10 w-4/5" />
				</div>

				{/* Author + date */}
				<div className="mb-10 flex items-center gap-3">
					<Skeleton className="h-8 w-8 rounded-full" />
					<Skeleton className="h-4 w-32" />
					<Skeleton className="h-4 w-24" />
				</div>

				{/* Article body paragraphs */}
				{Array.from({ length: 5 }).map((_, i) => (
					// biome-ignore lint/suspicious/noArrayIndexKey: a fixed-length loading skeleton, never reordered or filtered
					<div key={i} className="mb-6 space-y-2">
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-4/5" />
					</div>
				))}

				{/* Sub-heading */}
				<Skeleton className="mt-8 mb-4 h-7 w-56" />

				{Array.from({ length: 3 }).map((_, i) => (
					// biome-ignore lint/suspicious/noArrayIndexKey: a fixed-length loading skeleton, never reordered or filtered
					<div key={i} className="mb-6 space-y-2">
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-11/12" />
						<Skeleton className="h-4 w-3/4" />
					</div>
				))}
			</div>
		</div>
	);
}
