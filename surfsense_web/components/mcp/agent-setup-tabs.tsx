"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
	API_KEY_PLACEHOLDER,
	DEFAULT_SERVER_DIR,
	MCP_CLIENTS,
	type McpSnippetOptions,
} from "@/lib/mcp/clients";

function CopyButton({ text }: { text: string }) {
	const [copied, setCopied] = useState(false);

	const handleCopy = async () => {
		try {
			await navigator.clipboard.writeText(text);
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
		} catch {
			// Clipboard unavailable (permissions/insecure context); nothing to recover.
		}
	};

	return (
		<Button
			variant="ghost"
			size="sm"
			className="absolute top-2 right-2 h-7 gap-1.5 px-2 text-xs"
			onClick={handleCopy}
			aria-label="Copy configuration"
		>
			{copied ? <Check className="size-3.5 text-brand" /> : <Copy className="size-3.5" />}
			{copied ? "Copied" : "Copy"}
		</Button>
	);
}

/**
 * Per-agent MCP setup instructions as tabs: pick a client, follow its steps,
 * copy its exact config. Used on the /mcp-server marketing page and in the
 * API playground; `options` fills in real values where the caller has them.
 */
export function AgentSetupTabs({ options }: { options?: Partial<McpSnippetOptions> }) {
	const resolved: McpSnippetOptions = {
		baseUrl: options?.baseUrl || "https://api.surfsense.com",
		apiKey: options?.apiKey || API_KEY_PLACEHOLDER,
		serverDir: options?.serverDir || DEFAULT_SERVER_DIR,
	};

	return (
		<Tabs defaultValue={MCP_CLIENTS[0].id} className="w-full">
			<TabsList className="flex h-auto flex-wrap justify-start gap-1">
				{MCP_CLIENTS.map((client) => (
					<TabsTrigger key={client.id} value={client.id}>
						{client.label}
					</TabsTrigger>
				))}
			</TabsList>
			{MCP_CLIENTS.map((client) => {
				const config = client.buildConfig(resolved);
				return (
					<TabsContent key={client.id} value={client.id} className="space-y-3">
						<ol className="list-decimal space-y-1 pl-5 text-sm leading-relaxed text-muted-foreground">
							{client.steps.map((step) => (
								<li key={step}>{step}</li>
							))}
						</ol>
						<div>
							<p className="mb-1.5 font-mono text-xs text-muted-foreground">{client.configFile}</p>
							<div className="relative">
								<CopyButton text={config} />
								<pre className="overflow-x-auto rounded-lg border bg-muted/50 p-4 font-mono text-xs leading-relaxed">
									<code>{config}</code>
								</pre>
							</div>
						</div>
					</TabsContent>
				);
			})}
		</Tabs>
	);
}
