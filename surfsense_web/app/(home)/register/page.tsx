"use client";

import { useAtom } from "jotai";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { registerMutationAtom } from "@/atoms/auth/auth-mutation.atoms";
import { Logo } from "@/components/Logo";
import { Spinner } from "@/components/ui/spinner";
import { getAuthErrorDetails, isNetworkError, shouldRetry } from "@/lib/auth-errors";
import { AUTH_TYPE } from "@/lib/env-config";
import { AppError, ValidationError } from "@/lib/error";
import {
	trackRegistrationAttempt,
	trackRegistrationFailure,
	trackRegistrationSuccess,
} from "@/lib/posthog/events";
import { AmbientBackground } from "../login/AmbientBackground";

export default function RegisterPage() {
	const t = useTranslations("auth");
	const tCommon = useTranslations("common");
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [confirmPassword, setConfirmPassword] = useState("");
	const [error, setError] = useState<{
		title: string | null;
		message: string | null;
	}>({
		title: null,
		message: null,
	});
	const router = useRouter();
	const [{ mutateAsync: register, isPending: isRegistering }] = useAtom(registerMutationAtom);

	// Check authentication type and redirect if not LOCAL
	useEffect(() => {
		if (AUTH_TYPE !== "LOCAL") {
			router.push("/login");
		}
	}, [router]);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();

		// Form validation
		if (password !== confirmPassword) {
			setError({ title: t("password_mismatch"), message: t("passwords_no_match_desc") });
			toast.error(t("password_mismatch"), {
				description: t("passwords_no_match_desc"),
				duration: 4000,
			});
			return;
		}

		setError({ title: null, message: null }); // Clear any previous errors

		// Track registration attempt
		trackRegistrationAttempt();

		try {
			await register({
				email,
				password,
				is_active: true,
				is_superuser: false,
				is_verified: false,
			});

			// Track successful registration
			trackRegistrationSuccess();

			// Success toast
			toast.success(t("register_success"), {
				description: t("redirecting_login"),
				duration: 2000,
			});

			// Small delay to show success message
			setTimeout(() => {
				router.push("/login?registered=true");
			}, 500);
		} catch (err) {
			if (err instanceof AppError) {
				switch (err.status) {
					case 403: {
						const friendlyMessage =
							"Registrations are currently closed. If you need access, contact your administrator.";
						trackRegistrationFailure("Registration disabled");
						setError({ title: "Registration is disabled", message: friendlyMessage });
						toast.error("Registration is disabled", {
							description: friendlyMessage,
							duration: 6000,
						});
						return;
					}
					default:
						break;
				}

				if (err instanceof ValidationError) {
					trackRegistrationFailure(err.message);
					setError({ title: err.name, message: err.message });
					toast.error(err.name, {
						description: err.message,
						duration: 6000,
					});
					return;
				}
			}

			// Use auth-errors utility to get proper error details
			let errorCode = "UNKNOWN_ERROR";

			if (err instanceof Error) {
				errorCode = err.message;
			} else if (isNetworkError(err)) {
				errorCode = "NETWORK_ERROR";
			}

			// Track registration failure
			trackRegistrationFailure(errorCode);

			// Get detailed error information from auth-errors utility
			const errorDetails = getAuthErrorDetails(errorCode);

			// Set persistent error display
			setError({ title: errorDetails.title, message: errorDetails.description });

			// Show error toast with conditional retry action
			const toastOptions: any = {
				description: errorDetails.description,
				duration: 6000,
			};

			// Add retry action if the error is retryable
			if (shouldRetry(errorCode)) {
				toastOptions.action = {
					label: tCommon("retry"),
					onClick: () => handleSubmit(e),
				};
			}

			toast.error(errorDetails.title, toastOptions);
		}
	};

	return (
		<div className="relative w-full overflow-hidden">
			<AmbientBackground />
			<div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center px-6 md:px-0">
				<Logo className="h-16 w-16 md:h-32 md:w-32 rounded-md transition-all" />
				<h1 className="mt-4 mb-6 text-xl font-bold text-neutral-800 dark:text-neutral-100 md:mt-8 md:mb-8 md:text-3xl lg:text-4xl transition-all">
					{t("create_account")}
				</h1>

				<div className="w-full max-w-md">
					<form onSubmit={handleSubmit} className="space-y-3 md:space-y-4">
						{/* Enhanced Error Display */}
						<AnimatePresence>
							{error?.title && (
								<motion.div
									initial={{ opacity: 0, y: -10, scale: 0.95 }}
									animate={{ opacity: 1, y: 0, scale: 1 }}
									exit={{ opacity: 0, y: -10, scale: 0.95 }}
									transition={{ duration: 0.3 }}
									className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-900 shadow-sm dark:border-red-900/30 dark:bg-red-900/20 dark:text-red-200"
								>
									<div className="flex items-start gap-3">
										<svg
											xmlns="http://www.w3.org/2000/svg"
											width="18"
											height="18"
											viewBox="0 0 24 24"
											fill="none"
											stroke="currentColor"
											strokeWidth="2"
											strokeLinecap="round"
											strokeLinejoin="round"
											className="flex-shrink-0 mt-0.5 text-red-500 dark:text-red-400"
										>
											<title>Error Icon</title>
											<circle cx="12" cy="12" r="10" />
											<line x1="15" y1="9" x2="9" y2="15" />
											<line x1="9" y1="9" x2="15" y2="15" />
										</svg>
										<div className="flex-1 min-w-0">
											<p className="text-sm font-semibold mb-1">{error.title}</p>
											<p className="text-sm text-red-700 dark:text-red-300">{error.message}</p>
										</div>
										<button
											onClick={() => {
												setError({ title: null, message: null });
											}}
											className="flex-shrink-0 text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-200 transition-colors"
											aria-label="Dismiss error"
											type="button"
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												width="16"
												height="16"
												viewBox="0 0 24 24"
												fill="none"
												stroke="currentColor"
												strokeWidth="2"
												strokeLinecap="round"
												strokeLinejoin="round"
											>
												<title>Close</title>
												<line x1="18" y1="6" x2="6" y2="18" />
												<line x1="6" y1="6" x2="18" y2="18" />
											</svg>
										</button>
									</div>
								</motion.div>
							)}
						</AnimatePresence>

						<div>
							<label
								htmlFor="email"
								className="block text-sm font-medium text-gray-700 dark:text-gray-300"
							>
								{t("email")}
							</label>
							<input
								id="email"
								type="email"
								required
								value={email}
								onChange={(e) => setEmail(e.target.value)}
								className={`mt-1 block w-full rounded-md border px-3 py-1.5 md:py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 dark:bg-gray-800 dark:text-white transition-all ${
									error.title
										? "border-red-300 focus:border-red-500 focus:ring-red-500 dark:border-red-700"
										: "border-gray-300 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-700"
								}`}
								disabled={isRegistering}
							/>
						</div>

						<div>
							<label
								htmlFor="password"
								className="block text-sm font-medium text-gray-700 dark:text-gray-300"
							>
								{t("password")}
							</label>
							<input
								id="password"
								type="password"
								required
								value={password}
								onChange={(e) => setPassword(e.target.value)}
								className={`mt-1 block w-full rounded-md border px-3 py-1.5 md:py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 dark:bg-gray-800 dark:text-white transition-all ${
									error.title
										? "border-red-300 focus:border-red-500 focus:ring-red-500 dark:border-red-700"
										: "border-gray-300 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-700"
								}`}
								disabled={isRegistering}
							/>
						</div>

						<div>
							<label
								htmlFor="confirmPassword"
								className="block text-sm font-medium text-gray-700 dark:text-gray-300"
							>
								{t("confirm_password")}
							</label>
							<input
								id="confirmPassword"
								type="password"
								required
								value={confirmPassword}
								onChange={(e) => setConfirmPassword(e.target.value)}
								className={`mt-1 block w-full rounded-md border px-3 py-1.5 md:py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 dark:bg-gray-800 dark:text-white transition-all ${
									error.title
										? "border-red-300 focus:border-red-500 focus:ring-red-500 dark:border-red-700"
										: "border-gray-300 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-700"
								}`}
								disabled={isRegistering}
							/>
						</div>

						<button
							type="submit"
							disabled={isRegistering}
							className="w-full rounded-md bg-blue-600 px-4 py-1.5 md:py-2 text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 transition-all text-sm md:text-base flex items-center justify-center gap-2"
						>
							{isRegistering ? (
								<>
									<Spinner size="sm" className="text-white" />
									<span>{t("creating_account_btn")}</span>
								</>
							) : (
								t("register")
							)}
						</button>
					</form>

					<div className="mt-4 text-center text-sm">
						<p className="text-gray-600 dark:text-gray-400">
							{t("already_have_account")}{" "}
							<Link
								href="/login"
								className="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400"
							>
								{t("sign_in")}
							</Link>
						</p>
					</div>
				</div>
			</div>
		</div>
	);
}
