"use client";
import { JsonView } from "@/components/json-view";
import type { Inputs } from "@/contracts/types/automation.types";

interface InputsSchemaPreviewProps {
	inputs: Inputs;
}

/**
 * Read-only preview of an automation's accepted-inputs schema. Most
 * automations don't define inputs (defaults are baked into the trigger's
 * static_inputs), so the parent skips rendering this card when ``inputs``
 * is null.
 */
export function InputsSchemaPreview({ inputs }: InputsSchemaPreviewProps) {
	return (
		<div className="rounded-md bg-muted/40 px-3 py-2 max-h-72 overflow-auto">
			<JsonView src={inputs.schema} collapsed={2} />
		</div>
	);
}
