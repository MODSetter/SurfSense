"use client";

import { Crown, Search, Users } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import type { SearchSpace } from "../../types/layout.types";

interface AllSearchSpacesSheetProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	searchSpaces: SearchSpace[];
	activeSearchSpaceId: number | null;
	onSearchSpaceSelect: (id: number) => void;
	onCreateNew?: () => void;
}

export function AllSearchSpacesSheet({
	open,
	onOpenChange,
	searchSpaces,
	activeSearchSpaceId,
	onSearchSpaceSelect,
	onCreateNew,
}: AllSearchSpacesSheetProps) {
	const t = useTranslations("searchSpace");
	const tCommon = useTranslations("common");

	const handleSelect = (id: number) => {
		onSearchSpaceSelect(id);
		onOpenChange(false);
	};

	return (
		<Sheet open={open} onOpenChange={onOpenChange}>
			<SheetContent side="right" className="w-full sm:max-w-md">
				<SheetHeader>
					<div className="flex items-center gap-3">
						<div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
							<Search className="h-5 w-5 text-primary" />
						</div>
						<div className="flex flex-col gap-0.5">
							<SheetTitle>{t("all_search_spaces")}</SheetTitle>
							<SheetDescription>
								{t("search_spaces_count", { count: searchSpaces.length })}
							</SheetDescription>
						</div>
					</div>
				</SheetHeader>

				<div className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 pb-4">
					{searchSpaces.length === 0 ? (
						<div className="flex flex-1 flex-col items-center justify-center gap-4 py-12 text-center">
							<div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
								<Search className="h-8 w-8 text-muted-foreground" />
							</div>
							<div className="flex flex-col gap-1">
								<p className="font-medium">{t("no_search_spaces")}</p>
								<p className="text-sm text-muted-foreground">
									{t("create_first_search_space")}
								</p>
							</div>
							{onCreateNew && (
								<Button onClick={onCreateNew} className="mt-2">
									{t("create_button")}
								</Button>
							)}
						</div>
					) : (
						searchSpaces.map((space) => (
							<button
								key={space.id}
								type="button"
								onClick={() => handleSelect(space.id)}
								className={cn(
									"flex w-full flex-col gap-2 rounded-lg border p-4 text-left transition-colors",
									"hover:bg-accent hover:border-accent-foreground/20",
									activeSearchSpaceId === space.id &&
										"border-primary bg-primary/5 hover:bg-primary/10"
								)}
							>
								<div className="flex items-start justify-between gap-2">
									<div className="flex flex-col gap-1">
										<span className="font-medium leading-tight">
											{space.name}
										</span>
										{space.description && (
											<span className="text-sm text-muted-foreground line-clamp-2">
												{space.description}
											</span>
										)}
									</div>
									{space.isOwner && (
										<Badge variant="secondary" className="shrink-0">
											<Crown className="mr-1 h-3 w-3" />
											{tCommon("owner")}
										</Badge>
									)}
								</div>
								<div className="flex items-center gap-4 text-xs text-muted-foreground">
									<span className="flex items-center gap-1">
										<Users className="h-3.5 w-3.5" />
										{t("members_count", { count: space.memberCount })}
									</span>
								</div>
							</button>
						))
					)}
				</div>

				{searchSpaces.length > 0 && onCreateNew && (
					<div className="border-t p-4">
						<Button onClick={onCreateNew} variant="outline" className="w-full">
							{t("create_new_search_space")}
						</Button>
					</div>
				)}
			</SheetContent>
		</Sheet>
	);
}

