"use client";

import { useAtomValue } from "jotai";
import { Plus, Search } from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { workspacesAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { CreateWorkspaceDialog } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";

function ErrorScreen({ message }: { message: string }) {
	const t = useTranslations("dashboard");
	const router = useRouter();

	return (
		<div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
				className="w-full max-w-xl"
			>
				<Card className="w-full border-0 bg-transparent shadow-none">
					<CardHeader className="pb-10">
						<CardTitle className="text-xl font-medium">{t("error")}</CardTitle>
						<CardDescription className="max-w-lg">{message}</CardDescription>
					</CardHeader>
					<CardFooter className="flex flex-col-reverse gap-2 pt-4 sm:flex-row sm:justify-end">
						<Button variant="secondary" onClick={() => router.refresh()}>
							{t("try_again")}
						</Button>
						<Button onClick={() => router.push("/")}>{t("go_home")}</Button>
					</CardFooter>
				</Card>
			</motion.div>
		</div>
	);
}

function EmptyState({ onCreateClick }: { onCreateClick: () => void }) {
	const t = useTranslations("workspace");

	return (
		<div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
				className="flex flex-col items-center gap-6 text-center"
			>
				<div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary/10">
					<Search className="h-10 w-10 text-primary" />
				</div>

				<div className="flex flex-col gap-2">
					<h1 className="text-2xl font-bold">{t("welcome_title")}</h1>
					<p className="max-w-md text-muted-foreground">{t("welcome_description")}</p>
				</div>

				<Button size="lg" onClick={onCreateClick} className="gap-2">
					<Plus className="h-5 w-5" />
					{t("create_first_button")}
				</Button>
			</motion.div>
		</div>
	);
}

export default function DashboardPage() {
	const router = useRouter();
	const [showCreateDialog, setShowCreateDialog] = useState(false);

	const { data: workspaces = [], isLoading, error } = useAtomValue(workspacesAtom);

	useEffect(() => {
		if (isLoading) return;

		if (workspaces.length > 0) {
			// Read the query string at the time of redirect — no subscription needed.
			// (Vercel Best Practice: rerender-defer-reads 5.2)
			const query = window.location.search;
			router.replace(`/dashboard/${workspaces[0].id}/new-chat${query}`);
		}
	}, [isLoading, workspaces, router]);

	// Show loading while fetching or while we have spaces and are about to redirect
	const shouldShowLoading = isLoading || workspaces.length > 0;

	// Use global loading screen - spinner animation won't reset
	useGlobalLoadingEffect(shouldShowLoading);

	if (error) return <ErrorScreen message={error?.message || "Failed to load workspaces"} />;

	if (shouldShowLoading) {
		return null;
	}

	return (
		<>
			<EmptyState onCreateClick={() => setShowCreateDialog(true)} />
			<CreateWorkspaceDialog open={showCreateDialog} onOpenChange={setShowCreateDialog} />
		</>
	);
}
