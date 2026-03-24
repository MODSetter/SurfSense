import * as Babel from "@babel/standalone";
import React from "react";
import {
	AbsoluteFill,
	Easing,
	interpolate,
	Sequence,
	spring,
	useCurrentFrame,
	useVideoConfig,
} from "remotion";
import { DURATION_IN_FRAMES } from "./constants";

export interface CompileResult {
	success: boolean;
	error: string | null;
}

function createStagger(totalFrames: number) {
	return function stagger(
		frame: number,
		fps: number,
		index: number,
		total: number
	): { opacity: number; transform: string } {
		const enterPhase = Math.floor(totalFrames * 0.2);
		const exitStart = Math.floor(totalFrames * 0.8);
		const gap = Math.max(6, Math.floor(enterPhase / Math.max(total, 1)));
		const delay = index * gap;

		const s = spring({
			frame: Math.max(0, frame - delay),
			fps,
			config: { damping: 15, stiffness: 120, mass: 0.8 },
		});

		const exit = interpolate(frame, [exitStart, totalFrames], [0, 1], {
			extrapolateLeft: "clamp",
			extrapolateRight: "clamp",
		});

		const ambient = s > 0.99 ? Math.sin(frame * 0.05) * 2 : 0;

		const opacity = s * (1 - exit);
		const translateY =
			interpolate(s, [0, 1], [40, 0]) + interpolate(exit, [0, 1], [0, -30]) + ambient;
		const scale = interpolate(s, [0, 1], [0.97, 1]);

		return {
			opacity,
			transform: `translateY(${translateY}px) scale(${scale})`,
		};
	};
}

const defaultStagger = createStagger(DURATION_IN_FRAMES);

const INJECTED_NAMES = [
	"React",
	"AbsoluteFill",
	"useCurrentFrame",
	"useVideoConfig",
	"spring",
	"interpolate",
	"Sequence",
	"Easing",
	"stagger",
] as const;

const linear = (t: number) => t;

const SafeEasing = new Proxy(Easing, {
	get(target, prop) {
		const val = target[prop as keyof typeof Easing];
		if (typeof val === "function") return val;
		return linear;
	},
});

function buildInjectedValues(staggerFn: ReturnType<typeof createStagger>) {
	return [
		React,
		AbsoluteFill,
		useCurrentFrame,
		useVideoConfig,
		spring,
		interpolate,
		Sequence,
		SafeEasing,
		staggerFn,
	];
}

export function prepareSource(code: string): string {
	const codeWithoutImports = code.replace(/^import\s+.*$/gm, "").trim();

	const match = codeWithoutImports.match(
		/export\s+(?:const|function)\s+(\w+)\s*(?::\s*React\.FC\s*)?=?\s*\(\s*\)\s*=>\s*\{([\s\S]*)\};?\s*$/
	);

	if (match) {
		return `const DynamicComponent = () => {\n${match[2].trim()}\n};`;
	}

	const cleanedCode = codeWithoutImports
		.replace(/export\s+default\s+/, "")
		.replace(/export\s+/, "");
	return cleanedCode.replace(/const\s+(\w+)/, "const DynamicComponent");
}

function transpile(code: string): string {
	const wrappedSource = prepareSource(code);
	const transpiled = Babel.transform(wrappedSource, {
		presets: ["react", "typescript"],
		filename: "dynamic.tsx",
	});
	if (!transpiled.code) throw new Error("Transpilation produced no output");
	return transpiled.code;
}

export function compileCheck(code: string): CompileResult {
	if (!code?.trim()) {
		return { success: false, error: "Empty code" };
	}

	try {
		const jsCode = transpile(code);
		new Function(...INJECTED_NAMES, `${jsCode}\nreturn DynamicComponent;`);
		return { success: true, error: null };
	} catch (err) {
		return {
			success: false,
			error: err instanceof Error ? err.message : "Unknown compilation error",
		};
	}
}

export function compileToComponent(code: string, durationInFrames?: number): React.ComponentType {
	const staggerFn = durationInFrames ? createStagger(durationInFrames) : defaultStagger;

	const jsCode = transpile(code);
	const factory = new Function(...INJECTED_NAMES, `${jsCode}\nreturn DynamicComponent;`);
	return factory(...buildInjectedValues(staggerFn)) as React.ComponentType;
}
