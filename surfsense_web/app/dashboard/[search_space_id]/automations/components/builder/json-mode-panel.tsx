"use client";
import { AlertCircle } from "lucide-react";
import { JsonView } from "@/components/json-view";

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
				<div className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
					{notice}
				</div>
			)}

			<div className="rounded-md border border-input bg-background px-3 py-2 max-h-144 overflow-auto">
				<JsonView
					src={value}
					editable
					onChange={(next) => onChange(next as Record<string, unknown>)}
					collapsed={false}
				/>
			</div>

			{issues.length > 0 && (
				<div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2">
					<div className="flex items-center gap-1.5 text-xs font-medium text-destructive mb-1.5">
						<AlertCircle className="h-3.5 w-3.5" aria-hidden />
						{issues.length === 1 ? "1 issue" : `${issues.length} issues`}
					</div>
					<ul className="space-y-0.5 text-xs text-destructive list-disc list-inside">
						{issues.map((issue) => (
							<li key={issue}>{issue}</li>
						))}
					</ul>
				</div>
			)}
		</div>
	);
}
