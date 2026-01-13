"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useAtomValue } from "jotai";
import { Loader2, Plus, Search } from "lucide-react";
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
			<DialogContent className="sm:max-w-md">
				<DialogHeader>
					<div className="flex items-center gap-3">
						<div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
							<Search className="h-5 w-5 text-primary" />
						</div>
						<div>
							<DialogTitle>{t("create_title")}</DialogTitle>
							<DialogDescription>{t("create_description")}</DialogDescription>
						</div>
					</div>
				</DialogHeader>

				<Form {...form}>
					<form onSubmit={form.handleSubmit(handleSubmit)} className="flex flex-col gap-4">
						<FormField
							control={form.control}
							name="name"
							render={({ field }) => (
								<FormItem>
									<FormLabel>{t("name_label")}</FormLabel>
									<FormControl>
										<Input placeholder={t("name_placeholder")} {...field} autoFocus />
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
									<FormLabel>
										{t("description_label")}{" "}
										<span className="text-muted-foreground font-normal">
											({tCommon("optional")})
										</span>
									</FormLabel>
									<FormControl>
										<Input placeholder={t("description_placeholder")} {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<DialogFooter className="flex gap-2 pt-2">
							<Button
								type="button"
								variant="outline"
								onClick={() => handleOpenChange(false)}
								disabled={isSubmitting}
							>
								{tCommon("cancel")}
							</Button>
							<Button type="submit" disabled={isSubmitting}>
								{isSubmitting ? (
									<>
										<Loader2 className="mr-2 h-4 w-4 animate-spin" />
										{t("creating")}
									</>
								) : (
									<>
										<Plus className="mr-2 h-4 w-4" />
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
