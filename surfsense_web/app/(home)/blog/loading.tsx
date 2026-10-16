import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { cn } from "@/lib/utils";

// Still placeholders: the blog has no motion, so not the pulsing `Skeleton`.
function Block({ className }: { className: string }) {
	return <div className={cn("rounded-md bg-primary/10", className)} />;
}

export default function BlogIndexLoading() {
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("flex flex-col items-center", sectionSpacing.head)}>
				<Block className="h-8 w-20 rounded-full" />
				<Block className="mt-4 h-12 w-full max-w-lg" />
				<Block className="mt-6 h-5 w-full max-w-md" />
				<Block className="mt-8 h-11 w-full max-w-md rounded-full" />
			</div>

			<div className="mt-10 flex flex-col gap-6 lg:mt-14">
				<div className="flex flex-col gap-2 rounded-3xl bg-muted p-2 md:flex-row">
					<Block className="aspect-16/10 rounded-2xl md:aspect-auto md:min-h-80 md:w-1/2" />
					<div className="flex flex-1 flex-col justify-center gap-4 p-6 md:p-10">
						<Block className="h-4 w-32" />
						<Block className="h-8 w-5/6" />
						<Block className="h-4 w-full" />
						<Block className="h-4 w-3/4" />
					</div>
				</div>

				<div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
					{["a", "b", "c"].map((key) => (
						<div key={key} className="rounded-2xl border border-border bg-card p-2">
							<Block className="aspect-16/10 rounded-xl" />
							<div className="flex flex-col gap-3 px-4 pt-5 pb-4">
								<Block className="h-3 w-20" />
								<Block className="h-5 w-3/4" />
								<Block className="h-4 w-full" />
							</div>
						</div>
					))}
				</div>
			</div>
		</section>
	);
}
