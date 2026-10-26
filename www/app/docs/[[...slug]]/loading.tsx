import { Skeleton } from "@/components/ui/skeleton";

export default function DocsLoading() {
	return (
		<div className="flex flex-1 flex-col gap-4 p-6 max-w-4xl mx-auto w-full">
			{/* Title */}
			<Skeleton className="h-9 w-64" />

			{/* Description */}
			<Skeleton className="h-5 w-full max-w-md" />

			<div className="mt-4 space-y-8">
				{/* Paragraph block 1 */}
				<div className="space-y-2">
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-3/4" />
				</div>

				{/* Sub-heading */}
				<Skeleton className="h-7 w-48" />

				{/* Paragraph block 2 */}
				<div className="space-y-2">
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-5/6" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-2/3" />
				</div>

				{/* Code block placeholder */}
				<Skeleton className="h-28 w-full rounded-lg" />

				{/* Sub-heading */}
				<Skeleton className="h-7 w-56" />

				{/* List items */}
				<div className="space-y-3">
					{Array.from({ length: 4 }).map((_, i) => (
						<div key={i} className="flex items-start gap-3">
							<Skeleton className="mt-1 h-3 w-3 shrink-0 rounded-full" />
							<Skeleton className="h-4 w-full max-w-lg" />
						</div>
					))}
				</div>

				{/* Paragraph block 3 */}
				<div className="space-y-2">
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-4/5" />
				</div>
			</div>
		</div>
	);
}
