import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
	return (
		<div className="flex flex-1 flex-col items-center justify-center gap-4 p-4">
			<Skeleton className="h-4 w-64" />
			<Skeleton className="h-32 w-full max-w-2xl rounded-xl" />
		</div>
	);
}
