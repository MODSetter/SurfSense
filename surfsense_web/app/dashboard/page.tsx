"use client";

import { useAtomValue } from "jotai";
import { AlertCircle, Plus, Search } from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { searchSpacesAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { CreateSearchSpaceDialog } from "@/components/layout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";

function ErrorScreen({ message }: { message: string }) {
	const t = useTranslations("dashboard");
	const router = useRouter();

	return (
		<div className="flex min-h-screen flex-col items-center justify-center gap-4">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
			>
				<Card className="w-full max-w-[400px] border-destructive/20 bg-background/60 backdrop-blur-sm">
					<CardHeader className="pb-2">
						<div className="flex items-center gap-2">
							<AlertCircle className="h-5 w-5 text-destructive" />
							<CardTitle className="text-xl font-medium">{t("error")}</CardTitle>
						</div>
						<CardDescription>{t("something_wrong")}</CardDescription>
					</CardHeader>
					<CardContent>
						<Alert variant="destructive" className="border-destructive/30 bg-destructive/10">
							<AlertCircle className="h-4 w-4" />
							<AlertTitle>{t("error_details")}</AlertTitle>
							<AlertDescription className="mt-2">{message}</AlertDescription>
						</Alert>
					</CardContent>
					<CardFooter className="flex justify-end gap-2 border-t pt-4">
						<Button variant="outline" onClick={() => router.refresh()}>
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
	const t = useTranslations("searchSpace");

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

	const t = useTranslations("dashboard");
	const { data: searchSpaces = [], isLoading, error } = useAtomValue(searchSpacesAtom);

	useEffect(() => {
		if (isLoading) return;

		if (searchSpaces.length > 0) {
			router.replace(`/dashboard/${searchSpaces[0].id}/new-chat`);
		}
	}, [isLoading, searchSpaces, router]);

	// Show loading while fetching or while we have spaces and are about to redirect
	const shouldShowLoading = isLoading || searchSpaces.length > 0;

	// Use global loading screen - spinner animation won't reset
	useGlobalLoadingEffect(shouldShowLoading);

	if (error) return <ErrorScreen message={error?.message || "Failed to load search spaces"} />;

	if (shouldShowLoading) {
		return null;
	}

	return (
		<>
			<EmptyState onCreateClick={() => setShowCreateDialog(true)} />
			<CreateSearchSpaceDialog open={showCreateDialog} onOpenChange={setShowCreateDialog} />
		</>
	);
}
