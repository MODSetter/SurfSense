/**
 * Minimal JSON-Schema reader for the playground form. It only understands the
 * shapes pydantic v2 ``model_json_schema()`` actually emits for the scraper
 * verbs: primitives, ``string[]``, enums (via ``$defs`` + ``$ref``/``allOf``),
 * and optionals (``anyOf: [T, null]``). Anything unrecognized falls back to a
 * free-text string field so the form never silently drops an input.
 */

type JsonObject = Record<string, unknown>;

export type FieldKind =
	| "string"
	| "string_array"
	| "integer"
	| "number"
	| "boolean"
	| "enum";

export interface FormField {
	name: string;
	title: string;
	description?: string;
	kind: FieldKind;
	required: boolean;
	default?: unknown;
	enumValues?: string[];
	minimum?: number;
	maximum?: number;
}

function isObject(value: unknown): value is JsonObject {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function resolveRef(ref: string, defs: JsonObject): JsonObject | undefined {
	// Only local ``#/$defs/Name`` refs are emitted by pydantic.
	const name = ref.split("/").pop();
	if (!name) return undefined;
	const target = defs[name];
	return isObject(target) ? target : undefined;
}

/**
 * Collapse ``$ref`` / ``allOf`` / ``anyOf`` wrappers down to the concrete
 * subschema that carries ``type``/``enum``. Returns the original node if it is
 * already concrete.
 */
function resolveNode(node: JsonObject, defs: JsonObject, depth = 0): JsonObject {
	if (depth > 5) return node;

	if (typeof node.$ref === "string") {
		const target = resolveRef(node.$ref, defs);
		return target ? resolveNode(target, defs, depth + 1) : node;
	}

	if (Array.isArray(node.allOf) && node.allOf.length > 0 && isObject(node.allOf[0])) {
		return resolveNode(node.allOf[0], defs, depth + 1);
	}

	if (Array.isArray(node.anyOf)) {
		const branch = node.anyOf.find(
			(entry): entry is JsonObject => isObject(entry) && entry.type !== "null"
		);
		if (branch) return resolveNode(branch, defs, depth + 1);
	}

	return node;
}

function toEnumValues(node: JsonObject): string[] | undefined {
	if (!Array.isArray(node.enum)) return undefined;
	return node.enum.map((value) => String(value));
}

function detectKind(node: JsonObject): FieldKind {
	if (Array.isArray(node.enum)) return "enum";
	if (node.type === "array") {
		const items = isObject(node.items) ? node.items : undefined;
		// string[] is the only array shape used; other item types still render as
		// a line-per-value textarea, which is a reasonable fallback.
		void items;
		return "string_array";
	}
	if (node.type === "integer") return "integer";
	if (node.type === "number") return "number";
	if (node.type === "boolean") return "boolean";
	return "string";
}

function readNumber(value: unknown): number | undefined {
	return typeof value === "number" ? value : undefined;
}

/** Parse a full input schema into an ordered list of form fields. */
export function parseSchemaFields(schema: JsonObject | undefined): FormField[] {
	if (!isObject(schema) || !isObject(schema.properties)) return [];
	const defs = isObject(schema.$defs) ? schema.$defs : {};
	const required = new Set(
		Array.isArray(schema.required) ? schema.required.map((r) => String(r)) : []
	);

	return Object.entries(schema.properties).map(([name, rawProp]) => {
		const prop = isObject(rawProp) ? rawProp : {};
		const resolved = resolveNode(prop, defs);
		const kind = detectKind(resolved);

		return {
			name,
			title: typeof prop.title === "string" ? prop.title : name,
			description:
				typeof prop.description === "string"
					? prop.description
					: typeof resolved.description === "string"
						? resolved.description
						: undefined,
			kind,
			required: required.has(name),
			default: "default" in prop ? prop.default : undefined,
			enumValues: toEnumValues(resolved),
			minimum: readNumber(resolved.minimum) ?? readNumber(prop.minimum),
			maximum: readNumber(resolved.maximum) ?? readNumber(prop.maximum),
		};
	});
}

/** Build the initial form value map from field defaults. */
export function initialFormValues(fields: FormField[]): Record<string, unknown> {
	const values: Record<string, unknown> = {};
	for (const field of fields) {
		if (field.default !== undefined && field.default !== null) {
			values[field.name] =
				field.kind === "string_array" && Array.isArray(field.default)
					? field.default.join("\n")
					: field.default;
		} else if (field.kind === "boolean") {
			values[field.name] = false;
		} else {
			values[field.name] = "";
		}
	}
	return values;
}

/**
 * Convert the form's string-ish state into a typed request payload. Empty
 * optional fields are omitted so backend defaults apply.
 */
export function buildPayload(
	fields: FormField[],
	values: Record<string, unknown>
): Record<string, unknown> {
	const payload: Record<string, unknown> = {};

	for (const field of fields) {
		const raw = values[field.name];

		if (field.kind === "boolean") {
			payload[field.name] = Boolean(raw);
			continue;
		}

		if (field.kind === "string_array") {
			const lines = String(raw ?? "")
				.split("\n")
				.map((line) => line.trim())
				.filter(Boolean);
			if (lines.length > 0) payload[field.name] = lines;
			continue;
		}

		if (field.kind === "integer" || field.kind === "number") {
			if (raw === "" || raw === undefined || raw === null) continue;
			const num = Number(raw);
			if (!Number.isNaN(num)) payload[field.name] = num;
			continue;
		}

		// string + enum
		if (raw === "" || raw === undefined || raw === null) continue;
		payload[field.name] = raw;
	}

	return payload;
}
