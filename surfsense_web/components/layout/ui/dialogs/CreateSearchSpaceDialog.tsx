"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useAtomValue } from "jotai";
import { Plus, Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { createSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { trackSearchSpaceCreated } from "@/lib/posthog/events";

const formSchema = z.object({
	name: z.string().min(1, "Name is required"),
	description: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

interface CreateSearchSpaceDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

export function CreateSearchSpaceDialog({ open, onOpenChange }: CreateSearchSpaceDialogProps) {
	const t = useTranslations("searchSpace");
	const tCommon = useTranslations("common");
	const [isSubmitting, setIsSubmitting] = useState(false);

	const { mutateAsync: createSearchSpace } = useAtomValue(createSearchSpaceMutationAtom);

	const form = useForm<FormValues>({
		resolver: zodResolver(formSchema),
		defaultValues: {
			name: "",
			description: "",
		},
	});

	const handleSubmit = async (values: FormValues) => {
		setIsSubmitting(true);
		try {
			const result = await createSearchSpace({
				name: values.name,
				description: values.description || "",
			});

			trackSearchSpaceCreated(result.id, values.name);

			// Hard redirect to ensure fresh state
			window.location.href = `/dashboard/${result.id}/onboard`;
		} catch (error) {
			console.error("Failed to create search space:", error);
			setIsSubmitting(false);
		}
	};

	const handleOpenChange = (newOpen: boolean) => {
		if (!newOpen) {
			form.reset();
		}
		onOpenChange(newOpen);
	};

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent className="max-w-[90vw] sm:max-w-sm p-4 sm:p-5 data-[state=open]:animate-none data-[state=closed]:animate-none">
				<DialogHeader className="space-y-2 pb-2">
					<div className="flex items-center gap-2 sm:gap-3">
						<div className="flex h-8 w-8 sm:h-10 sm:w-10 items-center justify-center rounded-lg bg-primary/10 flex-shrink-0">
							<Search className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
						</div>
						<div className="flex-1 min-w-0">
							<DialogTitle className="text-base sm:text-lg">{t("create_title")}</DialogTitle>
							<DialogDescription className="text-xs sm:text-sm mt-0.5">
								{t("create_description")}
							</DialogDescription>
						</div>
					</div>
				</DialogHeader>

				<Form {...form}>
					<form onSubmit={form.handleSubmit(handleSubmit)} className="flex flex-col gap-3 sm:gap-4">
						<FormField
							control={form.control}
							name="name"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-sm">{t("name_label")}</FormLabel>
									<FormControl>
										<Input
											placeholder={t("name_placeholder")}
											{...field}
											autoFocus
											className="text-sm h-9 sm:h-10"
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="description"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-sm">
										{t("description_label")}{" "}
										<span className="text-muted-foreground font-normal">
											({tCommon("optional")})
										</span>
									</FormLabel>
									<FormControl>
										<Input
											placeholder={t("description_placeholder")}
											{...field}
											className="text-sm h-9 sm:h-10"
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<DialogFooter className="flex-col sm:flex-row gap-2 pt-2 sm:pt-3">
							<Button
								type="button"
								variant="outline"
								onClick={() => handleOpenChange(false)}
								disabled={isSubmitting}
								className="w-full sm:w-auto h-9 sm:h-10 text-sm"
							>
								{tCommon("cancel")}
							</Button>
							<Button
								type="submit"
								disabled={isSubmitting}
								className="w-full sm:w-auto h-9 sm:h-10 text-sm"
							>
								{isSubmitting ? (
									<>
										<Spinner size="sm" className="mr-1.5" />
										{t("creating")}
									</>
								) : (
									<>
										<Plus className="-mr-1 h-4 w-4" />
										{t("create_button")}
									</>
								)}
							</Button>
						</DialogFooter>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
}
