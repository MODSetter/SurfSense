import { CheckIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

const OPTIONS = [
	{ width: "w-3/4", correct: false },
	{ width: "w-2/3", correct: true },
	{ width: "w-1/2", correct: false },
];

/** A question with three answers, the right one marked. */
export function QuizPreview() {
	return (
		<div className="flex w-full max-w-48 flex-col gap-2 rounded-xl bg-card p-4 shadow-sm ring-1 ring-black/5">
			<span className="mb-1 h-2 w-5/6 rounded-full bg-foreground/70" />
			{OPTIONS.map((option) => (
				<div
					key={option.width}
					className={cn(
						"flex items-center gap-2 rounded-md px-2 py-1.5",
						option.correct && "bg-(--notice)/10"
					)}
				>
					<span
						className={cn(
							"grid size-3.5 shrink-0 place-items-center rounded-full ring-1",
							option.correct
								? "bg-(--notice) ring-(--notice) text-white"
								: "ring-muted-foreground/40"
						)}
					>
						{option.correct && <CheckIcon className="size-2.5" />}
					</span>
					<span className={cn("h-1.5 rounded-full bg-muted-foreground/30", option.width)} />
				</div>
			))}
		</div>
	);
}
