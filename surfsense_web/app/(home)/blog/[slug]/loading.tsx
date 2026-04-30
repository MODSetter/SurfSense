import { Skeleton } from "@/components/ui/skeleton";

export default function BlogPostLoading() {
	return (
		<div className="min-h-screen relative pt-20">
			<div className="max-w-3xl mx-auto px-6 lg:px-10 pt-10 pb-20">
				{/* Breadcrumb */}
				<div className="flex items-center gap-2 mb-8">
					<Skeleton className="h-4 w-10" />
					<Skeleton className="h-4 w-3" />
					<Skeleton className="h-4 w-10" />
					<Skeleton className="h-4 w-3" />
					<Skeleton className="h-4 w-40" />
				</div>

				{/* Tags */}
				<div className="flex flex-wrap gap-2 mb-4">
					<Skeleton className="h-6 w-16 rounded-full" />
					<Skeleton className="h-6 w-20 rounded-full" />
				</div>

				{/* Title */}
				<div className="space-y-3 mb-6">
					<Skeleton className="h-10 w-full" />
					<Skeleton className="h-10 w-4/5" />
				</div>

				{/* Description */}
				<Skeleton className="h-5 w-full mb-2" />
				<Skeleton className="h-5 w-3/4 mb-8" />

				{/* Author + date */}
				<div className="flex items-center gap-3 mb-10">
					<Skeleton className="h-10 w-10 rounded-full" />
					<div className="space-y-1.5">
						<Skeleton className="h-4 w-32" />
						<Skeleton className="h-3 w-24" />
					</div>
				</div>

				{/* Cover image */}
				<Skeleton className="w-full aspect-video rounded-xl mb-10" />

				{/* Article body paragraphs */}
				{Array.from({ length: 5 }).map((_, i) => (
					<div key={i} className="space-y-2 mb-6">
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-4/5" />
					</div>
				))}

				{/* Sub-heading */}
				<Skeleton className="h-7 w-56 mt-8 mb-4" />

				{Array.from({ length: 3 }).map((_, i) => (
					<div key={i} className="space-y-2 mb-6">
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-11/12" />
						<Skeleton className="h-4 w-3/4" />
					</div>
				))}
			</div>
		</div>
	);
}
