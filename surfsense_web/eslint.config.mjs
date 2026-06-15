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
			"no-restricted-syntax": [
				"error",
				{
					selector:
						"NewExpression[callee.name='URL'] TemplateLiteral Identifier[name='BACKEND_URL']",
					message:
						"Use buildBackendUrl(path, params) for backend URLs. BACKEND_URL may be empty in proxy mode, and new URL('/relative') throws without a base.",
				},
				{
					selector:
						"NewExpression[callee.name='URL'] TemplateLiteral Identifier[name='backendUrl']",
					message:
						"Use buildBackendUrl(path, params) for backend URLs instead of aliasing BACKEND_URL into new URL().",
				},
				{
					selector: "VariableDeclarator[id.name='backendUrl'][init.name='BACKEND_URL']",
					message:
						"Do not alias BACKEND_URL for URL construction. Use buildBackendUrl(path, params) instead.",
				},
			],
		},
	},
];

export default eslintConfig;
