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
	type McpTransport,
	REMOTE_URL,
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
			className="absolute top-2 right-2 size-7 p-0"
			onClick={handleCopy}
			aria-label={copied ? "Configuration copied" : "Copy configuration"}
		>
			{copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
		</Button>
	);
}

const TRANSPORTS: { id: McpTransport; label: string; hint: string }[] = [
	{ id: "remote", label: "Hosted", hint: "mcp.surfsense.com, nothing to install" },
	{ id: "stdio", label: "Self-host", hint: "run the server against your own backend" },
];

/**
 * Per-agent MCP setup instructions as tabs: pick a client, then Hosted or
 * Self-host, and copy its exact config. Used on the /mcp-server marketing page
 * and in the API playground; `options` fills in real values where the caller
 * has them.
 */
export function AgentSetupTabs({ options }: { options?: Partial<McpSnippetOptions> }) {
	const [transport, setTransport] = useState<McpTransport>("remote");

	const resolved: McpSnippetOptions = {
		remoteUrl: options?.remoteUrl || REMOTE_URL,
		apiKey: options?.apiKey || API_KEY_PLACEHOLDER,
		baseUrl: options?.baseUrl || "https://api.surfsense.com",
		serverDir: options?.serverDir || DEFAULT_SERVER_DIR,
	};

	const active = TRANSPORTS.find((t) => t.id === transport) ?? TRANSPORTS[0];

	return (
		<div className="min-w-0 space-y-4">
			<div className="flex flex-wrap items-center gap-3">
				<div className="inline-flex rounded-lg border bg-muted/40 p-0.5">
					{TRANSPORTS.map((t) => (
						<Button
							key={t.id}
							variant={t.id === transport ? "secondary" : "ghost"}
							size="sm"
							className="h-7 px-3 text-xs"
							onClick={() => setTransport(t.id)}
							aria-pressed={t.id === transport}
						>
							{t.label}
						</Button>
					))}
				</div>
				<span className="text-xs text-muted-foreground">{active.hint}</span>
			</div>

			<Tabs defaultValue={MCP_CLIENTS[0].id} className="min-w-0 w-full">
				<div className="w-full max-w-full overflow-x-auto overscroll-x-contain">
					<TabsList className="flex h-auto w-max min-w-full flex-nowrap justify-start gap-1">
						{MCP_CLIENTS.map((client) => (
							<TabsTrigger key={client.id} value={client.id}>
								{client.label}
							</TabsTrigger>
						))}
					</TabsList>
				</div>
				{MCP_CLIENTS.map((client) => {
					const snippet = client[transport];
					const config = snippet.build(resolved);
					return (
						<TabsContent key={client.id} value={client.id} className="min-w-0 space-y-3">
							<ol className="list-decimal space-y-1 pl-5 text-sm leading-relaxed text-muted-foreground">
								{snippet.steps.map((step) => (
									<li key={step}>{step}</li>
								))}
							</ol>
							<div>
								<p className="mb-1.5 font-mono text-xs text-muted-foreground">
									{snippet.configFile}
								</p>
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
		</div>
	);
}
