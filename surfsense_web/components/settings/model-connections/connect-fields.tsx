import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface ApiBaseUrlFieldProps {
	value: string;
	onChange: (value: string) => void;
	optional?: boolean;
	/** Placeholder, typically the provider's prefilled default base URL. */
	placeholder?: string;
}

/** Shared API Base URL input. The prefilled default is passed in via `value`. */
export function ApiBaseUrlField({ value, onChange, optional, placeholder }: ApiBaseUrlFieldProps) {
	return (
		<div className="flex flex-col gap-2">
			<Label>API Base URL{optional ? " (optional)" : ""}</Label>
			<Input
				value={value}
				onChange={(event) => onChange(event.target.value)}
				placeholder={placeholder || "https://api.example.com/v1"}
			/>
			<p className="text-xs text-muted-foreground">
				Local URLs are tested from the backend container, so use host.docker.internal instead of
				localhost.
			</p>
		</div>
	);
}

interface ApiKeyFieldProps {
	value: string;
	onChange: (value: string) => void;
	label?: string;
	placeholder?: string;
}

/** Shared masked API Key input. */
export function ApiKeyField({
	value,
	onChange,
	label = "API Key",
	placeholder = "API key",
}: ApiKeyFieldProps) {
	return (
		<div className="flex flex-col gap-2">
			<Label>{label}</Label>
			<Input
				value={value}
				onChange={(event) => onChange(event.target.value)}
				placeholder={placeholder}
				type="password"
			/>
		</div>
	);
}

interface ConnectFormFooterProps {
	onCancel: () => void;
	onSubmit: () => void;
	canSubmit: boolean;
	isPending: boolean;
}

/** Shared Cancel / Connect footer for every provider connect form. */
export function ConnectFormFooter({
	onCancel,
	onSubmit,
	canSubmit,
	isPending,
}: ConnectFormFooterProps) {
	return (
		<DialogFooter className="mt-6">
			<Button variant="secondary" onClick={onCancel}>
				Cancel
			</Button>
			<Button onClick={onSubmit} disabled={isPending || !canSubmit}>
				Connect
			</Button>
		</DialogFooter>
	);
}
