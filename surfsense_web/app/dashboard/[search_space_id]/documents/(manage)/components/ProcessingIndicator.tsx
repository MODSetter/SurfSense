"use client";

import { Loader2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface ProcessingIndicatorProps {
	activeTasksCount: number;
}

export function ProcessingIndicator({ activeTasksCount }: ProcessingIndicatorProps) {
	const t = useTranslations("documents");

	if (activeTasksCount === 0) return null;

	return (
		<AnimatePresence>
			<motion.div
				initial={{ opacity: 0, height: 0, marginBottom: 0 }}
				animate={{ opacity: 1, height: "auto", marginBottom: 24 }}
				exit={{ opacity: 0, height: 0, marginBottom: 0 }}
				transition={{ duration: 0.3 }}
			>
				<Alert className="border-border bg-primary/5">
					<div className="flex items-center gap-4">
						<div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
							<Loader2 className="h-5 w-5 animate-spin text-primary" />
						</div>
						<div className="flex-1">
							<AlertTitle className="text-primary font-semibold">
								{t("processing_documents")}
							</AlertTitle>
							<AlertDescription className="text-muted-foreground">
								{t("active_tasks_count", { count: activeTasksCount })}
							</AlertDescription>
						</div>
					</div>
				</Alert>
			</motion.div>
		</AnimatePresence>
	);
}
