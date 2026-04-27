import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
	return (
		<div className="flex min-h-screen">
			{/* Sidebar skeleton */}
			<aside className="hidden md:flex flex-col w-64 shrink-0 border-r border-border/50 px-4 py-8 gap-3">
				{Array.from({ length: 8 }).map((_, i) => (
					<Skeleton key={i} className={`h-4 ${i % 3 === 0 ? "w-3/4" : "w-full"}`} />
				))}
			</aside>

			{/* Main content skeleton */}
			<div className="flex-1 max-w-3xl mx-auto px-6 py-10 flex flex-col gap-4">
				{/* Page title */}
				<Skeleton className="h-9 w-1/2 mb-2" />
				<Skeleton className="h-5 w-3/4 mb-6" />

				{/* Body paragraphs */}
				{Array.from({ length: 10 }).map((_, i) => (
					<Skeleton key={i} className={`h-4 ${i % 4 === 3 ? "w-2/3" : "w-full"}`} />
				))}

				{/* Code block placeholder */}
				<Skeleton className="h-32 w-full rounded-lg mt-4" />

				{Array.from({ length: 5 }).map((_, i) => (
					<Skeleton key={i + 20} className={`h-4 ${i % 3 === 2 ? "w-4/5" : "w-full"}`} />
				))}
			</div>

			{/* TOC skeleton */}
			<aside className="hidden xl:flex flex-col w-52 shrink-0 px-4 py-8 gap-3">
				<Skeleton className="h-4 w-24 mb-2" />
				{Array.from({ length: 5 }).map((_, i) => (
					<Skeleton key={i} className="h-3 w-full" />
				))}
			</aside>
		</div>
	);
}
