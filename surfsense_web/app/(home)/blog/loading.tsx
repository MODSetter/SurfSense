import { Skeleton } from "@/components/ui/skeleton";

export default function BlogIndexLoading() {
	return (
		<div className="relative overflow-hidden bg-neutral-50 px-4 pt-20 md:px-8 dark:bg-neutral-950">
			<div className="mx-auto max-w-6xl pt-12 pb-24 md:pt-20">
				{/* Header */}
				<div className="mb-10 md:mb-14">
					<Skeleton className="h-10 w-24 rounded-md" />
				</div>

				{/* Featured post skeleton */}
				<div className="mb-14 overflow-hidden rounded-3xl border border-neutral-200/80 dark:border-neutral-800">
					<Skeleton className="aspect-[2.4/1] min-h-[220px] w-full rounded-none" />
					<div className="p-6 md:p-8 space-y-3">
						<Skeleton className="h-5 w-24 rounded-full" />
						<Skeleton className="h-8 w-3/4" />
						<Skeleton className="h-4 w-full max-w-lg" />
						<div className="flex items-center gap-3 pt-2">
							<Skeleton className="h-8 w-8 rounded-full" />
							<Skeleton className="h-4 w-28" />
							<Skeleton className="h-4 w-20" />
						</div>
					</div>
				</div>

				{/* Search bar skeleton */}
				<div className="mb-10">
					<Skeleton className="h-11 w-full max-w-md rounded-full" />
				</div>

				{/* Grid of article cards */}
				<div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
					{Array.from({ length: 6 }).map((_, i) => (
						<div key={i} className="space-y-3">
							<Skeleton className="aspect-video w-full rounded-2xl" />
							<Skeleton className="h-5 w-3/4" />
							<Skeleton className="h-4 w-full" />
							<Skeleton className="h-4 w-5/6" />
							<div className="flex items-center gap-2 pt-1">
								<Skeleton className="h-6 w-6 rounded-full" />
								<Skeleton className="h-4 w-24" />
							</div>
						</div>
					))}
				</div>
			</div>
		</div>
	);
}
