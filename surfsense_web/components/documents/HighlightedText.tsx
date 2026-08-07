import type { MatchRange } from "@/lib/documents/document-search";

export function HighlightedText({ text, ranges }: { text: string; ranges: MatchRange[] }) {
	let cursor = 0;

	return (
		<>
			{ranges.map(([start, end]) => {
				const before = text.slice(cursor, start);
				const match = text.slice(start, end);
				cursor = end;

				return (
					<span key={`${start}-${end}`}>
						{before}
						<mark className="rounded-sm bg-primary/15 text-inherit">{match}</mark>
					</span>
				);
			})}
			{text.slice(cursor)}
		</>
	);
}
