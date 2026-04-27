import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
	return (
		<div className="min-h-screen">
			{/* Header skeleton */}
			<div className="border-b border-border/50">
				<div className="max-w-5xl mx-auto px-6 py-16">
					<Skeleton className="h-10 w-48 mb-4" />
					<Skeleton className="h-5 w-96" />
				</div>
			</div>

			{/* Article list skeleton */}
			<div className="max-w-5xl mx-auto px-6 py-10 grid gap-8 md:grid-cols-2">
				{Array.from({ length: 6 }).map((_, i) => (
					<div key={i} className="flex flex-col gap-3">
						<Skeleton className="h-48 w-full rounded-xl" />
						<Skeleton className="h-4 w-24" />
						<Skeleton className="h-6 w-3/4" />
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-5/6" />
					</div>
				))}
			</div>
		</div>
	);
}
