import { Skeleton } from "@/components/ui/skeleton";

export default function FreeModelLoading() {
	return (
		<>
			{/* Chat area skeleton - fills viewport */}
			<div className="h-full flex flex-col">
				{/* Chat header */}
				<div className="flex items-center gap-3 border-b px-4 py-3">
					<Skeleton className="h-8 w-8 rounded-full" />
					<Skeleton className="h-5 w-40" />
				</div>

				{/* Chat messages area */}
				<div className="flex-1 flex flex-col justify-end gap-4 px-4 py-6">
					<div className="flex justify-end">
						<Skeleton className="h-10 w-56 rounded-2xl" />
					</div>
					<div className="space-y-2 max-w-lg">
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-4/5" />
						<Skeleton className="h-4 w-3/4" />
					</div>
				</div>

				{/* Input bar */}
				<div className="border-t px-4 py-3">
					<Skeleton className="h-12 w-full rounded-xl" />
				</div>
			</div>

			{/* SEO section skeleton */}
			<div className="border-t bg-background">
				<div className="container mx-auto px-4 py-10 max-w-3xl">
					{/* Breadcrumb */}
					<div className="flex items-center gap-2 mb-6">
						<Skeleton className="h-4 w-10" />
						<Skeleton className="h-4 w-3" />
						<Skeleton className="h-4 w-24" />
						<Skeleton className="h-4 w-3" />
						<Skeleton className="h-4 w-32" />
					</div>

					<Skeleton className="h-7 w-3/4 mb-2" />
					<Skeleton className="h-4 w-full mb-1" />
					<Skeleton className="h-4 w-2/3 mb-8" />

					<div className="my-8 h-px bg-border" />

					{/* FAQ skeleton */}
					<Skeleton className="h-6 w-64 mb-4" />
					<div className="flex flex-col gap-3">
						{Array.from({ length: 4 }).map((_, i) => (
							<div key={i} className="rounded-lg border bg-card p-4 space-y-2">
								<Skeleton className="h-4 w-3/4" />
								<Skeleton className="h-3 w-full" />
								<Skeleton className="h-3 w-5/6" />
							</div>
						))}
					</div>
				</div>
			</div>
		</>
	);
}
