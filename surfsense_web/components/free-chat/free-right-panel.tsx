"use client";

import { Lock } from "lucide-react";
import Link from "next/link";
import type { FC } from "react";
import { Button } from "@/components/ui/button";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "@/components/ui/empty";

interface GatedTabProps {
	title: string;
	description: string;
}

const GatedTab: FC<GatedTabProps> = ({ title, description }) => (
	<Empty>
		<EmptyHeader>
			<EmptyMedia variant="icon">
				<Lock />
			</EmptyMedia>
			<EmptyTitle>{title}</EmptyTitle>
			<EmptyDescription>{description}</EmptyDescription>
		</EmptyHeader>
		<EmptyContent>
			<Button size="sm" asChild>
				<Link href="/register">Create Free Account</Link>
			</Button>
		</EmptyContent>
	</Empty>
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
