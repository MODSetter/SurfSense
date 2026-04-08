import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
	return (
		<div className="w-full px-6 py-4 space-y-6 min-h-[calc(100vh-64px)] animate-in fade-in duration-300">
			{/* Summary Dashboard Skeleton */}
			<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
				{[...Array(4)].map((_, i) => (
					<div key={i} className="rounded-lg border p-4">
						<div className="flex flex-row items-center justify-between space-y-0 pb-2">
							<Skeleton className="h-4 w-24" />
							<Skeleton className="h-4 w-4 rounded-full" />
						</div>
						<div className="space-y-2">
							<Skeleton className="h-8 w-16" />
							<Skeleton className="h-3 w-32" />
						</div>
					</div>
				))}
			</div>

			{/* Header Section Skeleton */}
			<div className="flex items-center justify-between">
				<div className="space-y-2">
					<Skeleton className="h-8 w-48" />
					<Skeleton className="h-4 w-64" />
				</div>
				<Skeleton className="h-9 w-24" />
			</div>

			{/* Filters Skeleton */}
			<div className="flex flex-wrap items-center justify-start gap-3 w-full">
				<div className="flex items-center gap-3 flex-wrap w-full sm:w-auto">
					<Skeleton className="h-9 w-full sm:w-60" />
					<Skeleton className="h-9 w-24" />
					<Skeleton className="h-9 w-24" />
					<Skeleton className="h-9 w-20" />
				</div>
			</div>

			{/* Table Skeleton */}
			<div className="rounded-md border overflow-hidden">
				{/* Table Header */}
				<div className="border-b bg-muted/50 px-4 py-3 flex items-center gap-4">
					<Skeleton className="h-4 w-4" />
					<Skeleton className="h-4 w-16" />
					<Skeleton className="h-4 w-20" />
					<Skeleton className="h-4 w-24" />
					<Skeleton className="h-4 flex-1" />
					<Skeleton className="h-4 w-24" />
					<Skeleton className="h-4 w-8" />
				</div>

				{/* Table Rows */}
				{[...Array(6)].map((_, i) => (
					<div key={i} className="border-b px-4 py-3 flex items-center gap-4 hover:bg-muted/50">
						<Skeleton className="h-4 w-4" />
						<Skeleton className="h-6 w-12 rounded-full" />
						<Skeleton className="h-6 w-16 rounded-full" />
						<div className="flex items-center gap-2">
							<Skeleton className="h-4 w-4" />
							<Skeleton className="h-4 w-20" />
						</div>
						<div className="flex-1 space-y-1">
							<Skeleton className="h-4 w-32" />
							<Skeleton className="h-3 w-48" />
						</div>
						<div className="space-y-1">
							<Skeleton className="h-3 w-24" />
							<Skeleton className="h-3 w-20" />
						</div>
						<Skeleton className="h-8 w-8" />
					</div>
				))}
			</div>

			{/* Pagination Skeleton */}
			<div className="flex items-center justify-between gap-8 mt-4">
				<div className="flex items-center gap-3">
					<Skeleton className="h-4 w-20 max-sm:sr-only" />
					<Skeleton className="h-9 w-16" />
				</div>

				<div className="flex grow justify-end">
					<Skeleton className="h-4 w-40" />
				</div>

				<div className="flex items-center gap-2">
					<Skeleton className="h-9 w-9" />
					<Skeleton className="h-9 w-9" />
					<Skeleton className="h-9 w-9" />
					<Skeleton className="h-9 w-9" />
				</div>
			</div>
		</div>
	);
}
