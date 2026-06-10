"use client";
import { AlertCircle, TriangleAlert } from "lucide-react";
import { JsonView } from "@/components/json-view";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface JsonModePanelProps {
	value: Record<string, unknown>;
	issues: string[];
	notice?: string;
	onChange: (next: Record<string, unknown>) => void;
}

/**
 * Raw-JSON escape hatch. Edits the same payload the form produces; the
 * orchestrator validates it against the contract schema on submit. Shown when
 * the user opts into "Edit as JSON" or when an existing definition uses
 * features the form can't represent.
 */
export function JsonModePanel({ value, issues, notice, onChange }: JsonModePanelProps) {
	return (
		<div className="space-y-4">
			{notice && (
				<Alert variant="warning">
					<TriangleAlert aria-hidden />
					<AlertDescription>{notice}</AlertDescription>
				</Alert>
			)}

			<JsonView
				src={value}
				editable
				onChange={(next) => onChange(next as Record<string, unknown>)}
				collapsed={false}
				className="max-h-144 overflow-auto rounded-md border border-accent bg-accent/20"
			/>

			{issues.length > 0 && (
				<Alert variant="destructive">
					<AlertCircle aria-hidden />
					<AlertTitle>{issues.length === 1 ? "1 issue" : `${issues.length} issues`}</AlertTitle>
					<AlertDescription>
						<ul className="list-inside list-disc">
							{issues.map((issue) => (
								<li key={issue}>{issue}</li>
							))}
						</ul>
					</AlertDescription>
				</Alert>
			)}
		</div>
	);
}
