import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
	return (
		<div className="min-h-screen">
			{/* Header skeleton */}
			<div className="border-b border-border/50">
				<div className="max-w-5xl mx-auto px-6 py-16">
					<Skeleton className="h-10 w-48 mb-4" />
					<Skeleton className="h-5 w-80" />
				</div>
			</div>

			{/* Changelog entries skeleton */}
			<div className="max-w-3xl mx-auto px-6 py-10 flex flex-col gap-12">
				{Array.from({ length: 4 }).map((_, i) => (
					<div key={i} className="flex flex-col gap-4">
						{/* Date badge */}
						<Skeleton className="h-6 w-28 rounded-full" />
						{/* Entry title */}
						<Skeleton className="h-7 w-2/3" />
						{/* Body lines */}
						{Array.from({ length: 4 }).map((_, j) => (
							<Skeleton key={j} className={`h-4 ${j % 3 === 2 ? "w-4/5" : "w-full"}`} />
						))}
					</div>
				))}
			</div>
		</div>
	);
}
