import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
	return (
		<div className="flex h-full flex-col bg-main-panel px-4">
			<div className="mx-auto w-full max-w-[44rem] flex flex-1 flex-col gap-6 py-8">
				{/* User message */}
				<div className="flex justify-end">
					<Skeleton className="h-12 w-56 rounded-2xl" />
				</div>

				{/* Assistant message */}
				<div className="flex flex-col gap-2">
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-[85%]" />
					<Skeleton className="h-18 w-[40%]" />
				</div>

				{/* User message */}
				<div className="flex gap-2 justify-end">
					<Skeleton className="h-12 w-72 rounded-2xl" />
				</div>

				{/* Assistant message */}
				<div className="flex flex-col gap-2">
					<Skeleton className="h-10 w-[30%]" />
					<Skeleton className="h-4 w-[90%]" />
					<Skeleton className="h-6 w-[60%]" />
				</div>

				{/* User message */}
				<div className="flex gap-2 justify-end">
					<Skeleton className="h-12 w-96 rounded-2xl" />
				</div>
			</div>

			{/* Input bar */}
			<div className="sticky bottom-0 pb-6 bg-main-panel">
				<div className="mx-auto w-full max-w-[44rem]">
					<Skeleton className="h-24 w-full rounded-2xl" />
				</div>
			</div>
		</div>
	);
}
