import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { cn } from "@/lib/utils";

// Still placeholders shaped like `ChangelogTimeline`: no pulsing `Skeleton`.
function Block({ className }: { className: string }) {
	return <div className={cn("rounded-md bg-primary/10", className)} />;
}

export default function ChangelogLoading() {
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("flex flex-col items-center", sectionSpacing.head)}>
				<Block className="h-8 w-32 rounded-full" />
				<Block className="mt-4 h-12 w-64" />
				<Block className="mt-6 h-5 w-full max-w-xl" />
			</div>

			<div className="mt-10 divide-y divide-border border-y border-border lg:mt-14">
				{["a", "b", "c"].map((key) => (
					<div key={key} className="grid gap-6 py-10 md:grid-cols-[11rem_1fr] md:gap-10 md:py-14">
						<div className="flex flex-col gap-3">
							<Block className="h-6 w-24 rounded-full" />
							<Block className="h-4 w-20" />
						</div>
						<div className="flex max-w-3xl flex-col gap-4">
							<Block className="h-7 w-2/3" />
							<Block className="h-4 w-full" />
							<Block className="h-4 w-full" />
							<Block className="h-4 w-3/4" />
						</div>
					</div>
				))}
			</div>
		</section>
	);
}
