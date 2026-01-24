"use client";

import { useTranslations } from "next-intl";
import { Spinner } from "@/components/ui/spinner";

export default function DashboardLoading() {
	const t = useTranslations("common");
	return (
		<div className="fixed inset-0 z-[9999] flex min-h-screen flex-col items-center justify-center bg-background">
			<div className="flex flex-col items-center space-y-4">
				<div className="h-12 w-12 flex items-center justify-center">
					<Spinner size="xl" className="text-primary" />
				</div>
				<span className="text-muted-foreground text-sm min-h-[1.25rem] text-center max-w-md px-4">
					{t("loading")}
				</span>
			</div>
		</div>
	);
}

