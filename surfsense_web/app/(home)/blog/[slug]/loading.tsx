import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { cn } from "@/lib/utils";

// Still placeholders: the blog has no motion, so not the pulsing `Skeleton`.
function Block({ className }: { className: string }) {
	return <div className={cn("rounded-md bg-primary/10", className)} />;
}

export default function BlogPostLoading() {
	return (
		<div className={sectionSpacing.foot}>
			<div className="mx-auto flex max-w-3xl flex-col items-center pt-16 md:pt-24">
				<Block className="h-4 w-20" />
				<Block className="mt-6 h-10 w-full" />
				<Block className="mt-3 h-10 w-4/5" />
				<Block className="mt-5 h-5 w-2/3" />
				<Block className="mt-6 h-7 w-48 rounded-full" />
			</div>

			<div className="mx-auto mt-10 max-w-5xl rounded-3xl bg-muted p-2 lg:mt-14">
				<Block className="aspect-2/1 rounded-2xl" />
			</div>

			<div className="mx-auto mt-12 flex max-w-3xl flex-col gap-6 lg:mt-16">
				{["a", "b", "c", "d"].map((key) => (
					<div key={key} className="flex flex-col gap-2">
						<Block className="h-4 w-full" />
						<Block className="h-4 w-full" />
						<Block className="h-4 w-4/5" />
					</div>
				))}
			</div>
		</div>
	);
}
