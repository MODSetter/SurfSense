import { ExternalLink } from "lucide-react";
import { memo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { getConnectorIcon } from "./ConnectorComponents";
import type { Source } from "./types";

type CitationProps = {
	citationId: number;
	citationText: string;
	position: number;
	source: Source | null;
};

/**
 * Citation component to handle individual citations
 */
export const Citation = memo(({ citationId, citationText, position, source }: CitationProps) => {
	const [open, setOpen] = useState(false);
	const citationKey = `citation-${citationId}-${position}`;

	if (!source) return <>{citationText}</>;

	return (
		<span key={citationKey} className="relative inline-flex items-center">
			<DropdownMenu open={open} onOpenChange={setOpen}>
				<DropdownMenuTrigger asChild>
					<sup>
						<span className="inline-flex items-center justify-center text-primary cursor-pointer bg-primary/10 hover:bg-primary/15 w-4 h-4 rounded-full text-[10px] font-medium ml-0.5 transition-colors border border-primary/20 shadow-sm">
							{citationId}
						</span>
					</sup>
				</DropdownMenuTrigger>
				{open && (
					<DropdownMenuContent align="start" className="w-80 p-0" forceMount>
						<Card className="border-0 shadow-none">
							<div className="p-3 flex items-start gap-3">
								<div className="flex-shrink-0 w-7 h-7 flex items-center justify-center bg-muted rounded-full">
									{getConnectorIcon(source.connectorType || "")}
								</div>
								<div className="flex-1">
									<div className="flex items-center gap-2 mb-1">
										<h3 className="font-medium text-sm text-card-foreground">{source.title}</h3>
									</div>
									<p className="text-sm text-muted-foreground mt-0.5">{source.description}</p>
									<div className="mt-2 flex items-center text-xs text-muted-foreground">
										<span className="truncate max-w-[200px]">{source.url}</span>
									</div>
								</div>
								<Button
									variant="ghost"
									size="icon"
									className="h-7 w-7 rounded-full"
									onClick={() => window.open(source.url, "_blank", "noopener,noreferrer")}
									title="Open in new tab"
								>
									<ExternalLink className="h-3.5 w-3.5" />
								</Button>
							</div>
						</Card>
					</DropdownMenuContent>
				)}
			</DropdownMenu>
		</span>
	);
});

Citation.displayName = "Citation";

/**
 * Function to render text with citations
 */
export const renderTextWithCitations = (
	text: string,
	getCitationSource: (id: number) => Source | null
) => {
	// Regular expression to find citation patterns like [1], [2], etc.
	const citationRegex = /\[(\d+)\]/g;
	const parts = [];
	let lastIndex = 0;
	let match: RegExpExecArray | null = citationRegex.exec(text);
	let position = 0;

	while (match !== null) {
		// Add text before the citation
		if (match.index > lastIndex) {
			parts.push(text.substring(lastIndex, match.index));
		}

		// Add the citation component
		const citationId = parseInt(match[1], 10);
		parts.push(
			<Citation
				key={`citation-${citationId}-${position}`}
				citationId={citationId}
				citationText={match[0]}
				position={position}
				source={getCitationSource(citationId)}
			/>
		);

		lastIndex = match.index + match[0].length;
		position++;
		match = citationRegex.exec(text);
	}

	// Add any remaining text after the last citation
	if (lastIndex < text.length) {
		parts.push(text.substring(lastIndex));
	}

	return parts;
};
