"use client";
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
	const fields = getInputFields(inputs.schema);

	if (fields.length === 0) {
		return <p className="text-sm text-muted-foreground">No extra inputs are required.</p>;
	}

	return (
		<div className="rounded-md border border-border/60 bg-background/30">
			{fields.map((field) => (
				<div
					key={field.name}
					className="flex items-start justify-between gap-4 border-border/60 px-3 py-2 text-sm not-last:border-b"
				>
					<div className="min-w-0">
						<div className="font-medium text-foreground">{field.name}</div>
						{field.description ? (
							<div className="mt-0.5 text-xs text-muted-foreground">{field.description}</div>
						) : null}
					</div>
					<div className="shrink-0 text-xs text-muted-foreground">
						{field.type}
						{field.required ? " · required" : ""}
					</div>
				</div>
			))}
		</div>
	);
}

function getInputFields(schema: Record<string, unknown>): {
	name: string;
	type: string;
	description?: string;
	required: boolean;
}[] {
	const properties = schema.properties;
	if (!properties || typeof properties !== "object" || Array.isArray(properties)) {
		return [];
	}

	const required = new Set(Array.isArray(schema.required) ? schema.required : []);
	return Object.entries(properties as Record<string, unknown>).map(([name, value]) => {
		const field = value && typeof value === "object" && !Array.isArray(value) ? value : {};
		return {
			name,
			type: formatType((field as Record<string, unknown>).type),
			description:
				typeof (field as Record<string, unknown>).description === "string"
					? ((field as Record<string, unknown>).description as string)
					: undefined,
			required: required.has(name),
		};
	});
}

function formatType(value: unknown): string {
	if (Array.isArray(value)) return value.join(" or ");
	if (typeof value === "string") return value;
	return "value";
}
