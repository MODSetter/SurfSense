"use client";

import { Lock } from "lucide-react";
import Link from "next/link";
import type { FC } from "react";
import { Button } from "@/components/ui/button";

interface GatedTabProps {
	title: string;
	description: string;
}

const GatedTab: FC<GatedTabProps> = ({ title, description }) => (
	<div className="flex flex-col items-center justify-center gap-3 p-8 text-center">
		<div className="rounded-full bg-muted p-3">
			<Lock className="size-5 text-muted-foreground" />
		</div>
		<h3 className="text-sm font-medium">{title}</h3>
		<p className="text-xs text-muted-foreground max-w-[200px]">{description}</p>
		<Button size="sm" asChild>
			<Link href="/register">Create Free Account</Link>
		</Button>
	</div>
);

export const ReportsGatedPlaceholder: FC = () => (
	<GatedTab
		title="Generate Reports"
		description="Create a free account to generate structured reports from your conversations."
	/>
);

export const EditorGatedPlaceholder: FC = () => (
	<GatedTab
		title="Document Editor"
		description="Create a free account to use the AI-powered document editor."
	/>
);

export const HitlGatedPlaceholder: FC = () => (
	<GatedTab
		title="Human-in-the-Loop Editing"
		description="Create a free account to collaborate with AI on document edits."
	/>
);
