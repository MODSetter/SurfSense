import { Skeleton } from "@/components/ui/skeleton";

export function ThreadMessagesSkeletonBody() {
	return (
		<div className="mx-auto flex w-full max-w-(--thread-max-width) flex-1 flex-col gap-6 py-8">
			<div className="flex justify-end">
				<Skeleton className="h-12 w-[65%] max-w-56 rounded-2xl" />
			</div>

			<div className="flex flex-col gap-2">
				<Skeleton className="h-4 w-full" />
				<Skeleton className="h-4 w-[85%]" />
				<Skeleton className="h-18 w-[40%]" />
			</div>

			<div className="flex justify-end gap-2">
				<Skeleton className="h-12 w-[78%] max-w-72 rounded-2xl" />
			</div>

			<div className="flex flex-col gap-2">
				<Skeleton className="h-10 w-[30%]" />
				<Skeleton className="h-4 w-[90%]" />
				<Skeleton className="h-6 w-[60%]" />
			</div>

			<div className="flex justify-end gap-2">
				<Skeleton className="h-12 w-[85%] max-w-96 rounded-2xl" />
			</div>
		</div>
	);
}
