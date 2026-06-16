import { FlatCompat } from "@eslint/eslintrc";
import { dirname } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
	baseDirectory: __dirname,
});

const eslintConfig = [
	...compat.extends("next/core-web-vitals", "next/typescript"),
	{
		rules: {
			"no-restricted-imports": [
				"error",
				{
					paths: [
						{
							name: "@/lib/env-config",
							importNames: ["BACKEND_URL"],
							message:
								"Use buildBackendUrl(path, params) for browser-facing backend URLs. BACKEND_URL is empty in proxy mode; importing it bypasses the single URL seam.",
						},
					],
					patterns: [
						{
							group: ["**/env-config", "**/env-config.ts"],
							importNames: ["BACKEND_URL"],
							message:
								"Use buildBackendUrl(path, params). Import BACKEND_URL only inside lib/env-config.ts.",
						},
					],
				},
			],
		},
	},
];

export default eslintConfig;
