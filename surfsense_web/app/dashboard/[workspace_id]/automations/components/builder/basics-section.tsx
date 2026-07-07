"use client";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "./form-field";

interface BasicsSectionProps {
	name: string;
	description: string | null;
	errors: Record<string, string>;
	onChange: (patch: { name?: string; description?: string | null }) => void;
}

export function BasicsSection({ name, description, errors, onChange }: BasicsSectionProps) {
	return (
		<div className="space-y-4">
			<Field label="Name" htmlFor="automation-name" required error={errors.name}>
				<Input
					id="automation-name"
					value={name}
					maxLength={200}
					placeholder="Weekly competitor digest"
					onChange={(e) => onChange({ name: e.target.value })}
				/>
			</Field>

			<Field
				label="Description"
				htmlFor="automation-description"
				hint="Optional. A short note about what this automation is for."
				error={errors.description}
			>
				<Textarea
					id="automation-description"
					value={description ?? ""}
					rows={2}
					placeholder="Summarize what changed and email me the highlights."
					onChange={(e) => onChange({ description: e.target.value })}
				/>
			</Field>
		</div>
	);
}
