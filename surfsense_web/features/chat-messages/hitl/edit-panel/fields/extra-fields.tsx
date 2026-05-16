"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ExtraField } from "../edit-panel.atom";
import { DateTimePickerField } from "./calendar-field";
import { EmailsTagField } from "./email-tags-field";

/**
 * Renders ``ExtraField[]`` as a labelled vertical stack. Picks the
 * input control from ``field.type``; unknown types fall back to a
 * plain ``<Input type={field.type} />`` (covers "text" and "email").
 *
 * Pure presentational component — owns no state, just maps values to
 * controls and propagates changes through ``onFieldChange(key, value)``.
 */
export function ExtraFieldsSection({
	fields,
	values,
	onFieldChange,
}: {
	fields: ExtraField[];
	values: Record<string, string>;
	onFieldChange: (key: string, value: string) => void;
}) {
	if (fields.length === 0) return null;

	return (
		<div className="flex flex-col gap-3 px-4 py-3 border-b">
			{fields.map((field) => {
				const fieldId = `extra-field-${field.key}`;
				const currentValue = values[field.key] ?? "";

				return (
					<div key={field.key} className="flex flex-col gap-1.5">
						<Label htmlFor={fieldId} className="text-xs font-medium text-muted-foreground">
							{field.label}
						</Label>
						{field.type === "emails" ? (
							<EmailsTagField
								id={fieldId}
								value={currentValue}
								onChange={(v) => onFieldChange(field.key, v)}
								placeholder={`Add ${field.label.toLowerCase()}`}
							/>
						) : field.type === "datetime-local" ? (
							<DateTimePickerField
								id={fieldId}
								value={currentValue}
								onChange={(v) => onFieldChange(field.key, v)}
							/>
						) : field.type === "textarea" ? (
							<Textarea
								id={fieldId}
								value={currentValue}
								onChange={(e) => onFieldChange(field.key, e.target.value)}
								className="text-sm min-h-[60px]"
							/>
						) : (
							<Input
								id={fieldId}
								type={field.type}
								value={currentValue}
								onChange={(e) => onFieldChange(field.key, e.target.value)}
								className="text-sm"
							/>
						)}
					</div>
				);
			})}
		</div>
	);
}
