import { Skeleton } from "@/components/ui/skeleton";

export default function BlogIndexLoading() {
	return (
		<>
			<section className="ss-home-hero ss-home-pad pb-8">
				<Skeleton className="h-10 w-24" />
			</section>

			<section className="ss-home-pad pb-14">
				{/* Heading + search bar skeleton */}
				<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
					<Skeleton className="h-6 w-24" />
					<Skeleton className="h-11 w-full sm:max-w-md" />
				</div>

				{/* Grid of article cards */}
				<div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
					{Array.from({ length: 6 }).map((_, i) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: a fixed-length loading skeleton, never reordered or filtered
						<div key={i} className="space-y-3 border border-border">
							<Skeleton className="aspect-video w-full rounded-none" />
							<div className="space-y-3 px-6 pb-6">
								<Skeleton className="h-5 w-3/4" />
								<Skeleton className="h-4 w-full" />
								<Skeleton className="h-4 w-5/6" />
								<div className="flex items-center gap-2 pt-1">
									<Skeleton className="h-6 w-6 rounded-full" />
									<Skeleton className="h-4 w-24" />
								</div>
							</div>
						</div>
					))}
				</div>
			</section>
		</>
	);
}
