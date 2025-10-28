"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Logo } from "@/components/Logo";
import { getAuthErrorDetails, isNetworkError, shouldRetry } from "@/lib/auth-errors";
import { AmbientBackground } from "../login/AmbientBackground";

export default function RegisterPage() {
	const t = useTranslations("auth");
	const tCommon = useTranslations("common");
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [confirmPassword, setConfirmPassword] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [errorTitle, setErrorTitle] = useState<string | null>(null);
	const [isLoading, setIsLoading] = useState(false);
	const router = useRouter();

	// Check authentication type and redirect if not LOCAL
	useEffect(() => {
		const authType = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE || "GOOGLE";
		if (authType !== "LOCAL") {
			router.push("/login");
		}
	}, [router]);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();

		// Form validation
		if (password !== confirmPassword) {
			setError(t("passwords_no_match"));
			setErrorTitle(t("password_mismatch"));
			toast.error(t("password_mismatch"), {
				description: t("passwords_no_match_desc"),
				duration: 4000,
			});
			return;
		}

		setIsLoading(true);
		setError(null); // Clear any previous errors
		setErrorTitle(null);

		// Show loading toast
		const loadingToast = toast.loading(t("creating_account"));

		try {
			const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/auth/register`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({
					email,
					password,
					is_active: true,
					is_superuser: false,
					is_verified: false,
				}),
			});

			const data = await response.json();

			if (!response.ok && response.status === 403) {
				const friendlyMessage =
					"Registrations are currently closed. If you need access, contact your administrator.";
				setErrorTitle("Registration is disabled");
				setError(friendlyMessage);
				toast.error("Registration is disabled", {
					id: loadingToast,
					description: friendlyMessage,
					duration: 6000,
				});
				setIsLoading(false);
				return;
			}

			if (!response.ok) {
				throw new Error(data.detail || `HTTP ${response.status}`);
			}

			// Success toast
			toast.success(t("register_success"), {
				id: loadingToast,
				description: t("redirecting_login"),
				duration: 2000,
			});

			// Small delay to show success message
			setTimeout(() => {
				router.push("/login?registered=true");
			}, 500);
		} catch (err) {
			// Use auth-errors utility to get proper error details
			let errorCode = "UNKNOWN_ERROR";

			if (err instanceof Error) {
				errorCode = err.message;
			} else if (isNetworkError(err)) {
				errorCode = "NETWORK_ERROR";
			}

			// Get detailed error information from auth-errors utility
			const errorDetails = getAuthErrorDetails(errorCode);

			// Set persistent error display
			setErrorTitle(errorDetails.title);
			setError(errorDetails.description);

			// Show error toast with conditional retry action
			const toastOptions: any = {
				id: loadingToast,
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
		} finally {
			setIsLoading(false);
		}
	};

	return (
		<div className="relative w-full overflow-hidden">
			<AmbientBackground />
			<div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center">
				<Logo className="rounded-md" />
				<h1 className="my-8 text-xl font-bold text-neutral-800 dark:text-neutral-100 md:text-4xl">
					{t("create_account")}
				</h1>

				<div className="w-full max-w-md">
					<form onSubmit={handleSubmit} className="space-y-4">
						{/* Enhanced Error Display */}
						<AnimatePresence>
							{error && errorTitle && (
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
											<p className="text-sm font-semibold mb-1">{errorTitle}</p>
											<p className="text-sm text-red-700 dark:text-red-300">{error}</p>
										</div>
										<button
											onClick={() => {
												setError(null);
												setErrorTitle(null);
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
								className={`mt-1 block w-full rounded-md border px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 dark:bg-gray-800 dark:text-white transition-colors ${
									error
										? "border-red-300 focus:border-red-500 focus:ring-red-500 dark:border-red-700"
										: "border-gray-300 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-700"
								}`}
								disabled={isLoading}
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
								className={`mt-1 block w-full rounded-md border px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 dark:bg-gray-800 dark:text-white transition-colors ${
									error
										? "border-red-300 focus:border-red-500 focus:ring-red-500 dark:border-red-700"
										: "border-gray-300 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-700"
								}`}
								disabled={isLoading}
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
								className={`mt-1 block w-full rounded-md border px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 dark:bg-gray-800 dark:text-white transition-colors ${
									error
										? "border-red-300 focus:border-red-500 focus:ring-red-500 dark:border-red-700"
										: "border-gray-300 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-700"
								}`}
								disabled={isLoading}
							/>
						</div>

						<button
							type="submit"
							disabled={isLoading}
							className="w-full rounded-md bg-blue-600 px-4 py-2 text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
						>
							{isLoading ? t("creating_account_btn") : t("register")}
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
