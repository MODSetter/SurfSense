import { Info } from "lucide-react";
import type { FieldOption } from "@/app/dashboard/[workspace_id]/playground/components/schema-form";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { FormField } from "@/lib/playground/json-schema";

export const AMAZON_DOMAIN_OPTIONS: FieldOption[] = [
	{ label: "US", value: "www.amazon.com" },
	{ label: "UK", value: "www.amazon.co.uk" },
	{ label: "Germany", value: "www.amazon.de" },
	{ label: "Italy", value: "www.amazon.it" },
	{ label: "Spain", value: "www.amazon.es" },
	{ label: "France, best effort", value: "www.amazon.fr" },
];

const AMAZON_SUPPORTED_COUNTRIES = "US, UK, Germany, Italy, Spain, France";

export function getAmazonFieldOptions(field: FormField): FieldOption[] | undefined {
	return field.name === "domain" ? AMAZON_DOMAIN_OPTIONS : undefined;
}

export function hasAmazonFranceValue(values: Record<string, unknown>): boolean {
	return JSON.stringify(values).toLowerCase().includes("amazon.fr");
}

export function AmazonMarketplaceHint({ showFranceWarning }: { showFranceWarning: boolean }) {
	return (
		<Alert>
			<Info />
			<AlertDescription className="flex flex-wrap items-baseline gap-x-1">
				<span className="font-medium text-foreground">Supported countries: </span>
				<span>{AMAZON_SUPPORTED_COUNTRIES}</span>
				{showFranceWarning
					? " France is more WAF-sensitive. If this run returns no results, retry later or use another marketplace."
					: null}
			</AlertDescription>
		</Alert>
	);
}
