"use client";

import { Check, Copy } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BACKEND_URL } from "@/lib/env-config";
import { buildExamplePayload, buildSnippets } from "@/lib/playground/code-snippets";
import type { FormField } from "@/lib/playground/json-schema";

function CopyButton({ text }: { text: string }) {
	const [copied, setCopied] = useState(false);
	const copy = () => {
		navigator.clipboard.writeText(text).then(() => {
			setCopied(true);
			setTimeout(() => setCopied(false), 1500);
		});
	};
	return (
		<Button
			type="button"
			variant="ghost"
			size="sm"
			onClick={copy}
			className="absolute right-2 top-2 h-7 gap-1.5 px-2 text-xs"
		>
			{copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
			{copied ? "Copied" : "Copy"}
		</Button>
	);
}

function CodeBlock({ code }: { code: string }) {
	return (
		<div className="relative">
			<CopyButton text={code} />
			<pre className="max-h-[420px] overflow-auto rounded-md border border-border/60 bg-muted/20 p-3 pr-20 text-xs">
				<code>{code}</code>
			</pre>
		</div>
	);
}

function SchemaBlock({ title, schema }: { title: string; schema: Record<string, unknown> }) {
	const json = useMemo(() => JSON.stringify(schema, null, 2), [schema]);
	return (
		<details className="group rounded-md border border-border/60">
			<summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground">
				{title}
			</summary>
			<div className="relative border-t border-border/60">
				<CopyButton text={json} />
				<pre className="max-h-[360px] overflow-auto p-3 pr-20 text-xs">
					<code>{json}</code>
				</pre>
			</div>
		</details>
	);
}

export function ApiReference({
	workspaceId,
	platform,
	verb,
	fields,
	inputSchema,
	outputSchema,
}: {
	workspaceId: number;
	platform: string;
	verb: string;
	fields: FormField[];
	inputSchema: Record<string, unknown>;
	/** Absent only when talking to a backend that predates output schemas. */
	outputSchema?: Record<string, unknown>;
}) {
	const path = `/api/v1/workspaces/${workspaceId}/scrapers/${platform}/${verb}`;

	// In proxy mode BACKEND_URL is intentionally empty (same-origin), so external
	// callers use this app's origin. Client component, so window is available.
	const baseUrl = BACKEND_URL || (typeof window !== "undefined" ? window.location.origin : "");

	const snippets = useMemo(() => {
		const payload = buildExamplePayload(fields);
		return buildSnippets(baseUrl, path, payload);
	}, [fields, baseUrl, path]);

	return (
		<section className="space-y-4">
			<div>
				<h2 className="text-base font-semibold">API reference</h2>
				<p className="mt-1 text-sm text-muted-foreground">
					Call this API from your own project. Create a key under{" "}
					<span className="font-medium text-foreground">API Keys</span> (and enable API access for
					this workspace), then send it as a{" "}
					<code className="rounded bg-muted/40 px-1 py-0.5 text-xs">Authorization: Bearer</code>{" "}
					header.
				</p>
			</div>

			<Tabs defaultValue="curl">
				<TabsList className="h-auto flex-wrap">
					{snippets.map((snippet) => (
						<TabsTrigger key={snippet.id} value={snippet.id}>
							{snippet.label}
						</TabsTrigger>
					))}
				</TabsList>
				{snippets.map((snippet) => (
					<TabsContent key={snippet.id} value={snippet.id}>
						<CodeBlock code={snippet.code} />
					</TabsContent>
				))}
			</Tabs>

			<div className="space-y-2">
				<SchemaBlock title="Input schema (JSON)" schema={inputSchema} />
				{outputSchema && <SchemaBlock title="Output schema (JSON)" schema={outputSchema} />}
			</div>
		</section>
	);
}
