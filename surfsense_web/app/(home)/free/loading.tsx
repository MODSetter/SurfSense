import { Skeleton } from "@/components/ui/skeleton";

/** The hero's four fact pills and eight placeholder table rows. Named rather
 *  than counted, so each bar has a stable key. */
const PILLS = ["login", "tokens", "models", "source"];
const ROWS = ["a", "b", "c", "d", "e", "f", "g", "h"];

/**
 * Placeholder for `/free` while the model list is fetched. It mirrors the
 * page's own bands — hero, then a ruled table section — so the shape does not
 * change when the real content lands.
 */
export default function FreeChatLoading() {
	return (
		<>
			<section className="ss-home-hero ss-home-pad">
				<div className="mx-auto flex max-w-4xl flex-col items-center gap-4">
					<Skeleton className="h-12 w-4/5" />
					<Skeleton className="h-5 w-full max-w-xl" />
					<Skeleton className="h-5 w-3/5 max-w-xl" />
					<div className="mt-6 flex flex-wrap items-center justify-center gap-2">
						{PILLS.map((pill) => (
							<Skeleton key={pill} className="h-7 w-28 rounded-full" />
						))}
					</div>
				</div>
			</section>

			<section className="ss-home-rule">
				<div className="ss-home-head">
					<Skeleton className="h-8 w-80 max-w-full" />
					<Skeleton className="mt-3 h-4 w-96 max-w-full" />
				</div>

				<div>
					{ROWS.map((row) => (
						<div
							key={row}
							className="flex items-center gap-6 border-b border-[color:var(--border)] px-(--home-gutter) py-4"
						>
							<Skeleton className="h-4 w-40 shrink-0" />
							<Skeleton className="h-4 w-24 shrink-0" />
							<Skeleton className="h-4 w-14 shrink-0" />
						</div>
					))}
				</div>
			</section>
		</>
	);
}
