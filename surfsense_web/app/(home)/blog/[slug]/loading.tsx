import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
	return (
		<div className="min-h-screen max-w-3xl mx-auto px-6 py-16">
			{/* Breadcrumb */}
			<div className="flex gap-2 mb-8">
				<Skeleton className="h-4 w-10" />
				<Skeleton className="h-4 w-4" />
				<Skeleton className="h-4 w-32" />
			</div>

			{/* Title */}
			<Skeleton className="h-10 w-3/4 mb-4" />
			<Skeleton className="h-6 w-1/2 mb-8" />

			{/* Meta: date + read time */}
			<div className="flex gap-4 mb-10">
				<Skeleton className="h-4 w-24" />
				<Skeleton className="h-4 w-20" />
			</div>

			{/* Body */}
			<div className="flex flex-col gap-4">
				{Array.from({ length: 8 }).map((_, i) => (
					<Skeleton key={i} className={`h-4 ${i % 3 === 2 ? "w-2/3" : "w-full"}`} />
				))}
				<Skeleton className="h-48 w-full rounded-xl mt-4" />
				{Array.from({ length: 6 }).map((_, i) => (
					<Skeleton key={i + 10} className={`h-4 ${i % 4 === 3 ? "w-3/4" : "w-full"}`} />
				))}
			</div>
		</div>
	);
}
