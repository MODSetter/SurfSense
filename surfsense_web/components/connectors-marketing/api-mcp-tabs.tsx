"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ApiSample } from "@/lib/connectors-marketing/types";

/** Pretty-print the request body as canonical JSON (a valid JS/JSON object literal). */
function prettyJson(requestBody: Record<string, unknown>): string {
	return JSON.stringify(requestBody, null, 2);
}

/** Indent every line except the first by `pad` (for splicing a JSON block inline). */
function indentRest(text: string, pad: string): string {
	return text
		.split("\n")
		.map((line, i) => (i === 0 ? line : pad + line))
		.join("\n");
}

/** Render one request-body value as a Python literal (True/False, not true/false). */
function toPythonValue(value: unknown): string {
	if (typeof value === "boolean") return value ? "True" : "False";
	if (Array.isArray(value)) return `[${value.map((v) => JSON.stringify(v)).join(", ")}]`;
	return JSON.stringify(value);
}

/**
 * `"key" <arrow> <json-value>,` lines for languages whose literal syntax matches
 * JSON scalar/array values (Ruby hashes, PHP arrays).
 */
function kvLines(requestBody: Record<string, unknown>, arrow: string, pad: string): string {
	return Object.entries(requestBody)
		.map(([k, v]) => `${pad}"${k}" ${arrow} ${JSON.stringify(v)},`)
		.join("\n");
}

function buildCurl({ platform, verb, requestBody }: ApiSample): string {
	const body = indentRest(prettyJson(requestBody), "  ");
	return [
		`curl -X POST "$SURFSENSE_API_URL/workspaces/$WORKSPACE_ID/scrapers/${platform}/${verb}" \\`,
		`  -H "Authorization: Bearer $SURFSENSE_API_KEY" \\`,
		`  -H "Content-Type: application/json" \\`,
		`  -d '${body}'`,
	].join("\n");
}

function buildPython({ platform, verb, requestBody }: ApiSample): string {
	const entries = Object.entries(requestBody)
		.map(([k, v]) => `        ${JSON.stringify(k)}: ${toPythonValue(v)},`)
		.join("\n");
	return [
		"import os",
		"import requests",
		"",
		"base = os.environ['SURFSENSE_API_URL']",
		"key = os.environ['SURFSENSE_API_KEY']",
		"",
		"resp = requests.post(",
		`    f"{base}/workspaces/{WORKSPACE_ID}/scrapers/${platform}/${verb}",`,
		'    headers={"Authorization": f"Bearer {key}"},',
		"    json={",
		entries,
		"    },",
		")",
		"resp.raise_for_status()",
		'items = resp.json()["items"]',
	].join("\n");
}

function buildJavaScript({ platform, verb, requestBody }: ApiSample): string {
	return [
		`const payload = ${prettyJson(requestBody)};`,
		"",
		"const res = await fetch(",
		"  `${process.env.SURFSENSE_API_URL}/workspaces/${WORKSPACE_ID}/scrapers/" +
			platform +
			"/" +
			verb +
			"`,",
		"  {",
		'    method: "POST",',
		"    headers: {",
		"      Authorization: `Bearer ${process.env.SURFSENSE_API_KEY}`,",
		'      "Content-Type": "application/json",',
		"    },",
		"    body: JSON.stringify(payload),",
		"  },",
		");",
		"const { items } = await res.json();",
	].join("\n");
}

function buildGo({ platform, verb, requestBody }: ApiSample): string {
	return [
		"package main",
		"",
		"import (",
		'\t"bytes"',
		'\t"net/http"',
		'\t"os"',
		")",
		"",
		"func main() {",
		"\tpayload := []byte(`" + prettyJson(requestBody) + "`)",
		'\turl := os.Getenv("SURFSENSE_API_URL") + "/workspaces/" +',
		'\t\tos.Getenv("WORKSPACE_ID") + "/scrapers/' + platform + "/" + verb + '"',
		'\treq, _ := http.NewRequest("POST", url, bytes.NewReader(payload))',
		'\treq.Header.Set("Authorization", "Bearer "+os.Getenv("SURFSENSE_API_KEY"))',
		'\treq.Header.Set("Content-Type", "application/json")',
		"\tresp, _ := http.DefaultClient.Do(req)",
		"\tdefer resp.Body.Close()",
		"}",
	].join("\n");
}

function buildPhp({ platform, verb, requestBody }: ApiSample): string {
	return [
		"<?php",
		"$ch = curl_init();",
		"curl_setopt_array($ch, [",
		'    CURLOPT_URL => getenv("SURFSENSE_API_URL")',
		'        . "/workspaces/" . getenv("WORKSPACE_ID")',
		'        . "/scrapers/' + platform + "/" + verb + '",',
		"    CURLOPT_POST => true,",
		"    CURLOPT_RETURNTRANSFER => true,",
		"    CURLOPT_HTTPHEADER => [",
		'        "Authorization: Bearer " . getenv("SURFSENSE_API_KEY"),',
		'        "Content-Type: application/json",',
		"    ],",
		"    CURLOPT_POSTFIELDS => json_encode([",
		kvLines(requestBody, "=>", "        "),
		"    ]),",
		"]);",
		'$items = json_decode(curl_exec($ch), true)["items"];',
	].join("\n");
}

function buildRuby({ platform, verb, requestBody }: ApiSample): string {
	return [
		'require "net/http"',
		'require "json"',
		'require "uri"',
		"",
		"uri = URI(\"#{ENV['SURFSENSE_API_URL']}/workspaces/#{ENV['WORKSPACE_ID']}/scrapers/" +
			platform +
			"/" +
			verb +
			'")',
		"req = Net::HTTP::Post.new(uri)",
		'req["Authorization"] = "Bearer #{ENV[\'SURFSENSE_API_KEY\']}"',
		'req["Content-Type"] = "application/json"',
		"req.body = {",
		kvLines(requestBody, "=>", "  "),
		"}.to_json",
		"",
		"res = Net::HTTP.start(uri.host, uri.port, use_ssl: true) { |http| http.request(req) }",
		'items = JSON.parse(res.body)["items"]',
	].join("\n");
}

function buildJava({ platform, verb, requestBody }: ApiSample): string {
	return [
		"import java.net.URI;",
		"import java.net.http.HttpClient;",
		"import java.net.http.HttpRequest;",
		"import java.net.http.HttpResponse;",
		"",
		"var client = HttpClient.newHttpClient();",
		'String payload = """',
		prettyJson(requestBody),
		'""";',
		"var request = HttpRequest.newBuilder()",
		'    .uri(URI.create(System.getenv("SURFSENSE_API_URL")',
		'        + "/workspaces/" + System.getenv("WORKSPACE_ID")',
		'        + "/scrapers/' + platform + "/" + verb + '"))',
		'    .header("Authorization", "Bearer " + System.getenv("SURFSENSE_API_KEY"))',
		'    .header("Content-Type", "application/json")',
		"    .POST(HttpRequest.BodyPublishers.ofString(payload))",
		"    .build();",
		"var response = client.send(request, HttpResponse.BodyHandlers.ofString());",
	].join("\n");
}

function buildCsharp({ platform, verb, requestBody }: ApiSample): string {
	return [
		"using System;",
		"using System.Net.Http;",
		"using System.Text;",
		"",
		"var http = new HttpClient();",
		'var url = Environment.GetEnvironmentVariable("SURFSENSE_API_URL")',
		'    + "/workspaces/" + Environment.GetEnvironmentVariable("WORKSPACE_ID")',
		'    + "/scrapers/' + platform + "/" + verb + '";',
		'var payload = """',
		prettyJson(requestBody),
		'""";',
		"var request = new HttpRequestMessage(HttpMethod.Post, url)",
		"{",
		'    Content = new StringContent(payload, Encoding.UTF8, "application/json"),',
		"};",
		'request.Headers.Add("Authorization", "Bearer " + Environment.GetEnvironmentVariable("SURFSENSE_API_KEY"));',
		"var response = await http.SendAsync(request);",
	].join("\n");
}

function buildMcp({ mcpTool }: ApiSample): string {
	const config = {
		mcpServers: {
			surfsense: {
				url: "https://mcp.surfsense.com/mcp",
				headers: { Authorization: "Bearer ${SURFSENSE_API_KEY}" },
			},
		},
	};
	return `${JSON.stringify(config, null, 2)}\n\n# Your agent can now call the ${mcpTool} tool.`;
}

/** Ordered language set for the code-sample tabs. cURL is the default. */
const SAMPLES: { value: string; label: string; build: (api: ApiSample) => string }[] = [
	{ value: "curl", label: "cURL", build: buildCurl },
	{ value: "python", label: "Python", build: buildPython },
	{ value: "javascript", label: "JavaScript", build: buildJavaScript },
	{ value: "go", label: "Go", build: buildGo },
	{ value: "php", label: "PHP", build: buildPhp },
	{ value: "ruby", label: "Ruby", build: buildRuby },
	{ value: "java", label: "Java", build: buildJava },
	{ value: "csharp", label: "C#", build: buildCsharp },
	{ value: "mcp", label: "MCP", build: buildMcp },
];

function CodeBlock({ code }: { code: string }) {
	return (
		<pre className="overflow-x-auto rounded-lg border bg-muted/50 p-4 text-xs leading-relaxed">
			<code className="font-mono text-foreground/90">{code}</code>
		</pre>
	);
}

export function ApiMcpTabs({ api }: { api: ApiSample }) {
	return (
		<Tabs defaultValue="curl" className="w-full">
			<TabsList className="flex h-auto flex-wrap justify-start gap-1">
				{SAMPLES.map((sample) => (
					<TabsTrigger key={sample.value} value={sample.value}>
						{sample.label}
					</TabsTrigger>
				))}
			</TabsList>
			{SAMPLES.map((sample) => (
				<TabsContent key={sample.value} value={sample.value}>
					<CodeBlock code={sample.build(api)} />
				</TabsContent>
			))}
		</Tabs>
	);
}
