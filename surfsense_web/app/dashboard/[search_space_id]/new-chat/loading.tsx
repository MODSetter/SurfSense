import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
	return (
		<div
			className="aui-root aui-thread-root @container flex h-full min-h-0 flex-col bg-main-panel"
			style={{
				["--thread-max-width" as string]: "44rem",
			}}
		>
			<div
				className="aui-thread-viewport relative flex flex-1 min-h-0 flex-col overflow-y-auto px-4 scroll-smooth"
				style={{ scrollbarGutter: "stable" }}
			>
				<div
					aria-hidden
					className="aui-chat-viewport-top-fade pointer-events-none sticky top-0 z-10 -mx-4 h-2 shrink-0 bg-gradient-to-b from-main-panel from-20% to-transparent"
				/>
				<div className="mx-auto w-full max-w-(--thread-max-width) flex flex-1 flex-col gap-6 py-8">
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
				<div
					className="aui-chat-composer-footer sticky bottom-0 z-20 -mx-4 mt-auto flex flex-col items-stretch bg-gradient-to-t from-main-panel from-60% to-transparent px-4 pt-6"
					style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
				>
					<div className="aui-chat-composer-area relative mx-auto flex w-full max-w-(--thread-max-width) flex-col gap-3 overflow-visible">
						<Skeleton className="h-28 w-full rounded-3xl" />
					</div>
				</div>
			</div>
		</div>
	);
}
