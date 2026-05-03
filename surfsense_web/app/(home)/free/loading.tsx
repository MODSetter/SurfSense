import { Skeleton } from "@/components/ui/skeleton";

export default function FreeChatLoading() {
	return (
		<div className="min-h-screen pt-20">
			<article className="container mx-auto px-4 pb-20">
				{/* Breadcrumb */}
				<div className="flex items-center gap-2 mb-8">
					<Skeleton className="h-4 w-10" />
					<Skeleton className="h-4 w-3" />
					<Skeleton className="h-4 w-24" />
				</div>

				{/* Hero section */}
				<section className="mt-8 text-center max-w-3xl mx-auto space-y-4">
					<Skeleton className="h-12 w-3/4 mx-auto" />
					<Skeleton className="h-12 w-2/3 mx-auto" />
					<Skeleton className="h-5 w-full max-w-lg mx-auto" />
					<Skeleton className="h-5 w-4/5 max-w-lg mx-auto" />
					<div className="flex flex-wrap items-center justify-center gap-3 mt-6">
						{Array.from({ length: 4 }).map((_, i) => (
							<Skeleton key={i} className="h-8 w-28 rounded-full" />
						))}
					</div>
				</section>

				<div className="my-12 max-w-4xl mx-auto h-px bg-border" />

				{/* Model table */}
				<section className="max-w-4xl mx-auto">
					<Skeleton className="h-7 w-64 mb-2" />
					<Skeleton className="h-4 w-80 mb-6" />

					<div className="overflow-hidden rounded-lg border">
						{/* Table header */}
						<div className="flex gap-4 px-4 py-3 bg-muted/50 border-b">
							<Skeleton className="h-4 w-[45%]" />
							<Skeleton className="h-4 w-24" />
							<Skeleton className="h-4 w-16" />
							<Skeleton className="h-4 w-20" />
						</div>

						{/* Table rows */}
						{Array.from({ length: 8 }).map((_, i) => (
							<div key={i} className="flex items-center gap-4 px-4 py-3 border-b last:border-0">
								<div className="flex-1 space-y-1.5">
									<Skeleton className="h-4 w-40" />
									<Skeleton className="h-3 w-24" />
								</div>
								<Skeleton className="h-4 w-24" />
								<Skeleton className="h-6 w-14 rounded-full" />
								<Skeleton className="h-8 w-20 rounded-md" />
							</div>
						))}
					</div>
				</section>
			</article>
		</div>
	);
}
