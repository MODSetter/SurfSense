"use client";

import { EquationPlugin, InlineEquationPlugin } from "@platejs/math/react";

import { EquationElement, InlineEquationElement } from "@/components/ui/equation-node";

export const MathKit = [
	EquationPlugin.withComponent(EquationElement),
	InlineEquationPlugin.withComponent(InlineEquationElement),
];
