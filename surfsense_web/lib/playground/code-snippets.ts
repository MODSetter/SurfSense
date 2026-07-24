/**
 * Code-example generators for the playground API reference. One snippet per
 * popular language, all derived from the same endpoint URL + example payload
 * so they can't drift from each other.
 */

import type { FormField } from "./json-schema";

export interface CodeSnippet {
	id: string;
	label: string;
	code: string;
}

/**
 * Example request payload derived from the verb's parsed input fields:
 * required fields always appear (default or a named placeholder), optional
 * fields appear only when they carry a server default worth showing.
 */
export function buildExamplePayload(fields: FormField[]): Record<string, unknown> {
	const example: Record<string, unknown> = {};
	for (const field of fields) {
		if (field.default !== undefined && field.default !== null) {
			example[field.name] = field.default;
			continue;
		}
		if (!field.required) continue;
		switch (field.kind) {
			case "string_array":
				example[field.name] = [`<${field.name}>`];
				break;
			case "integer":
			case "number":
				example[field.name] = field.minimum ?? 1;
				break;
			case "boolean":
				example[field.name] = false;
				break;
			case "enum":
				example[field.name] = field.enumValues?.[0] ?? `<${field.name}>`;
				break;
			default:
				example[field.name] = `<${field.name}>`;
		}
	}
	return example;
}

function indent(text: string, spaces: number): string {
	const pad = " ".repeat(spaces);
	return text
		.split("\n")
		.map((line, i) => (i === 0 ? line : pad + line))
		.join("\n");
}

export function buildSnippets(
	baseUrl: string,
	path: string,
	payload: Record<string, unknown>
): CodeSnippet[] {
	const url = `${baseUrl}${path}`;
	const body = JSON.stringify(payload, null, 2);

	const curl = `curl -X POST "${url}" \\
  -H "Authorization: Bearer $SURFSENSE_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '${body.replace(/'/g, "'\\''")}'`;

	const python = `import os
import requests

response = requests.post(
    "${url}",
    headers={"Authorization": f"Bearer {os.environ['SURFSENSE_API_KEY']}"},
    json=${indent(body, 4)},
)
response.raise_for_status()
data = response.json()
print(data["items"])`;

	const javascript = `const response = await fetch("${url}", {
  method: "POST",
  headers: {
    Authorization: \`Bearer \${process.env.SURFSENSE_API_KEY}\`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify(${indent(body, 2)}),
});
if (!response.ok) throw new Error(\`HTTP \${response.status}\`);
const data = await response.json();
console.log(data.items);`;

	const typescript = `interface RunResult {
  items: Record<string, unknown>[];
}

const response = await fetch("${url}", {
  method: "POST",
  headers: {
    Authorization: \`Bearer \${process.env.SURFSENSE_API_KEY}\`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify(${indent(body, 2)}),
});
if (!response.ok) throw new Error(\`HTTP \${response.status}\`);
const data = (await response.json()) as RunResult;
console.log(data.items);`;

	const go = `package main

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"os"
)

func main() {
	payload := []byte(\`${body}\`)

	req, err := http.NewRequest("POST", "${url}", bytes.NewBuffer(payload))
	if err != nil {
		panic(err)
	}
	req.Header.Set("Authorization", "Bearer "+os.Getenv("SURFSENSE_API_KEY"))
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		panic(err)
	}
	defer resp.Body.Close()

	data, _ := io.ReadAll(resp.Body)
	fmt.Println(resp.Status, string(data))
}`;

	const java = `import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public class SurfSenseExample {
    public static void main(String[] args) throws Exception {
        String payload = """
${indent(body, 8)}
            """;

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create("${url}"))
            .header("Authorization", "Bearer " + System.getenv("SURFSENSE_API_KEY"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(payload))
            .build();

        HttpResponse<String> response = HttpClient.newHttpClient()
            .send(request, HttpResponse.BodyHandlers.ofString());
        System.out.println(response.statusCode() + " " + response.body());
    }
}`;

	const csharp = `using System.Net.Http.Headers;
using System.Text;

var payload = """
${indent(body, 4)}
    """;

using var client = new HttpClient();
client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue(
    "Bearer", Environment.GetEnvironmentVariable("SURFSENSE_API_KEY"));

var response = await client.PostAsync(
    "${url}",
    new StringContent(payload, Encoding.UTF8, "application/json"));
response.EnsureSuccessStatusCode();
Console.WriteLine(await response.Content.ReadAsStringAsync());`;

	const php = `<?php
$payload = json_encode(${indent(phpArray(payload), 0)});

$ch = curl_init("${url}");
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POSTFIELDS => $payload,
    CURLOPT_HTTPHEADER => [
        "Authorization: Bearer " . getenv("SURFSENSE_API_KEY"),
        "Content-Type: application/json",
    ],
]);

$response = curl_exec($ch);
curl_close($ch);

$data = json_decode($response, true);
print_r($data["items"]);`;

	const ruby = `require "net/http"
require "json"

uri = URI("${url}")
request = Net::HTTP::Post.new(uri)
request["Authorization"] = "Bearer #{ENV["SURFSENSE_API_KEY"]}"
request["Content-Type"] = "application/json"
request.body = <<~JSON
${indent(body, 2).replace(/^/, "  ")}
JSON

response = Net::HTTP.start(uri.hostname, uri.port, use_ssl: uri.scheme == "https") do |http|
  http.request(request)
end
data = JSON.parse(response.body)
puts data["items"]`;

	return [
		{ id: "curl", label: "cURL", code: curl },
		{ id: "python", label: "Python", code: python },
		{ id: "javascript", label: "JavaScript", code: javascript },
		{ id: "typescript", label: "TypeScript", code: typescript },
		{ id: "go", label: "Go", code: go },
		{ id: "java", label: "Java", code: java },
		{ id: "csharp", label: "C#", code: csharp },
		{ id: "php", label: "PHP", code: php },
		{ id: "ruby", label: "Ruby", code: ruby },
	];
}

/** Render a JSON-ish value as PHP array syntax for the PHP snippet. */
function phpArray(value: unknown, depth = 0): string {
	const pad = "    ".repeat(depth + 1);
	const closePad = "    ".repeat(depth);
	if (Array.isArray(value)) {
		if (value.length === 0) return "[]";
		const items = value.map((v) => `${pad}${phpArray(v, depth + 1)}`).join(",\n");
		return `[\n${items},\n${closePad}]`;
	}
	if (typeof value === "object" && value !== null) {
		const entries = Object.entries(value as Record<string, unknown>);
		if (entries.length === 0) return "[]";
		const items = entries
			.map(([k, v]) => `${pad}${JSON.stringify(k)} => ${phpArray(v, depth + 1)}`)
			.join(",\n");
		return `[\n${items},\n${closePad}]`;
	}
	if (typeof value === "string") return JSON.stringify(value);
	if (value === null) return "null";
	return String(value);
}
