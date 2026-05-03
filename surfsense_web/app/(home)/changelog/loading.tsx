import { Skeleton } from "@/components/ui/skeleton";

export default function ChangelogLoading() {
	return (
		<div className="min-h-screen relative pt-20">
			{/* Header */}
			<div className="border-b border-border/50">
				<div className="max-w-5xl mx-auto relative">
					<div className="p-6 flex items-center justify-between">
						<div>
							{/* Breadcrumb */}
							<div className="flex items-center gap-2 mb-4">
								<Skeleton className="h-4 w-10" />
								<Skeleton className="h-4 w-3" />
								<Skeleton className="h-4 w-20" />
							</div>
							<Skeleton className="h-10 w-48 mb-2" />
							<Skeleton className="h-4 w-80" />
						</div>
					</div>
				</div>
			</div>

			{/* Timeline */}
			<div className="max-w-5xl mx-auto px-6 lg:px-10 pt-10 pb-20">
				<div className="relative">
					{Array.from({ length: 3 }).map((_, i) => (
						<div key={i} className="relative flex flex-col md:flex-row gap-y-6 mb-10">
							{/* Left: date + version */}
							<div className="md:w-48 flex-shrink-0">
								<Skeleton className="h-4 w-24 mb-3" />
								<Skeleton className="h-12 w-12 rounded-xl" />
							</div>

							{/* Right: content */}
							<div className="flex-1 md:pl-8 relative pb-10">
								<div className="space-y-4">
									{/* Title */}
									<Skeleton className="h-7 w-2/3" />
									{/* Tags */}
									<div className="flex gap-2">
										<Skeleton className="h-6 w-16 rounded-full" />
										<Skeleton className="h-6 w-20 rounded-full" />
									</div>
									{/* Body paragraphs */}
									<div className="space-y-2">
										<Skeleton className="h-4 w-full" />
										<Skeleton className="h-4 w-full" />
										<Skeleton className="h-4 w-3/4" />
									</div>
									<div className="space-y-2">
										<Skeleton className="h-4 w-full" />
										<Skeleton className="h-4 w-5/6" />
									</div>
								</div>
							</div>
						</div>
					))}
				</div>
			</div>
		</div>
	);
}
