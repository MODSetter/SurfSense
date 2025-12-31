"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Info } from "lucide-react";
import type { FC } from "react";
import { useRef } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
	Form,
	FormControl,
	FormDescription,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { EnumConnectorName } from "@/contracts/enums/connector";
import type { ConnectFormProps } from "../index";

const linearConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	api_key: z
		.string()
		.min(10, {
			message: "Linear API Key is required and must be valid.",
		})
		.regex(/^lin_api_/, {
			message: "Linear API Key should start with 'lin_api_'",
		}),
});

type LinearConnectorFormValues = z.infer<typeof linearConnectorFormSchema>;

export const LinearConnectForm: FC<ConnectFormProps> = ({
	onSubmit,
	isSubmitting,
}) => {
	const isSubmittingRef = useRef(false);
	const form = useForm<LinearConnectorFormValues>({
		resolver: zodResolver(linearConnectorFormSchema),
		defaultValues: {
			name: "Linear Connector",
			api_key: "",
		},
	});

	const handleSubmit = async (values: LinearConnectorFormValues) => {
		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		isSubmittingRef.current = true;
		try {
			await onSubmit({
				name: values.name,
				connector_type: EnumConnectorName.LINEAR_CONNECTOR,
				config: {
					LINEAR_API_KEY: values.api_key,
				},
				is_indexable: true,
				last_indexed_at: null,
				periodic_indexing_enabled: false,
				indexing_frequency_minutes: null,
				next_scheduled_at: null,
			});
		} finally {
			isSubmittingRef.current = false;
		}
	};

	return (
		<div className="space-y-6 pb-6">
			<Alert className="bg-slate-400/5 dark:bg-white/5 border-slate-400/20 p-2 sm:p-3 flex items-center [&>svg]:relative [&>svg]:left-0 [&>svg]:top-0 [&>svg+div]:translate-y-0">
				<Info className="h-3 w-3 sm:h-4 sm:w-4 shrink-0 ml-1" />
				<div className="-ml-1">
					<AlertTitle className="text-xs sm:text-sm">API Key Required</AlertTitle>
					<AlertDescription className="text-[10px] sm:text-xs !pl-0">
						You'll need a Linear API Key to use this connector. You can create one from{" "}
						<a
							href="https://linear.app/settings/api"
							target="_blank"
							rel="noopener noreferrer"
							className="font-medium underline underline-offset-4"
						>
							Linear API Settings
						</a>
					</AlertDescription>
				</div>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<Form {...form}>
					<form id="linear-connect-form" onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4 sm:space-y-6">
						<FormField
							control={form.control}
							name="name"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Connector Name</FormLabel>
									<FormControl>
										<Input 
											placeholder="My Linear Connector" 
											className="border-slate-400/20 focus-visible:border-slate-400/40" 
											disabled={isSubmitting}
											{...field} 
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										A friendly name to identify this connector.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="api_key"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">Linear API Key</FormLabel>
									<FormControl>
										<Input 
											type="password" 
											placeholder="lin_api_..." 
											className="border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field} 
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Your Linear API Key will be encrypted and stored securely. It typically starts with "lin_api_".
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>
					</form>
				</Form>
			</div>
		</div>
	);
};

