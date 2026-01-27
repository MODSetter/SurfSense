"use client";
import { useAtom } from "jotai";
import { Eye, EyeOff } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { loginMutationAtom } from "@/atoms/auth/auth-mutation.atoms";
import { Spinner } from "@/components/ui/spinner";
import { getAuthErrorDetails, isNetworkError, shouldRetry } from "@/lib/auth-errors";
import { AUTH_TYPE } from "@/lib/env-config";
import { ValidationError } from "@/lib/error";
import { trackLoginAttempt, trackLoginFailure, trackLoginSuccess } from "@/lib/posthog/events";

export function LocalLoginForm() {
	const t = useTranslations("auth");
	const tCommon = useTranslations("common");
	const [username, setUsername] = useState("");
	const [password, setPassword] = useState("");
	const [showPassword, setShowPassword] = useState(false);
	const [error, setError] = useState<{
		title: string | null;
		message: string | null;
	}>({
		title: null,
		message: null,
	});
	const [authType, setAuthType] = useState<string | null>(null);
	const router = useRouter();
	const [{ mutateAsync: login, isPending: isLoggingIn }] = useAtom(loginMutationAtom);

	useEffect(() => {
		// Get the auth type from centralized config
		setAuthType(AUTH_TYPE);
	}, []);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setError({ title: null, message: null }); // Clear any previous errors

		// Track login attempt
		trackLoginAttempt("local");

		try {
			const data = await login({
				username,
				password,
				grant_type: "password",
			});

			// Track successful login
			trackLoginSuccess("local");

			// Set flag so TokenHandler knows local login was already tracked
			if (typeof window !== "undefined") {
				sessionStorage.setItem("login_success_tracked", "true");
			}

			// Success toast
			toast.success(t("login_success"), {
				description: "Redirecting to dashboard",
				duration: 2000,
			});

			// Small delay to show success message
			setTimeout(() => {
				router.push(`/auth/callback?token=${data.access_token}`);
			}, 500);
		} catch (err) {
			if (err instanceof ValidationError) {
				trackLoginFailure("local", err.message);
				setError({ title: err.name, message: err.message });
				toast.error(err.name, {
					description: err.message,
					duration: 6000,
				});
				return;
			}

			// Use auth-errors utility to get proper error details
			let errorCode = "UNKNOWN_ERROR";

			if (err instanceof Error) {
				errorCode = err.message;
			} else if (isNetworkError(err)) {
				errorCode = "NETWORK_ERROR";
			}

			// Track login failure
			trackLoginFailure("local", errorCode);

			// Get detailed error information from auth-errors utility
			const errorDetails = getAuthErrorDetails(errorCode);

			// Set persistent error display
			setError({
				title: errorDetails.title,
				message: errorDetails.description,
			});

			// Show error toast with conditional retry action
			const toastOptions: any = {
				description: errorDetails.description,
				duration: 6000,
			};

			// Add retry action if the error is retryable
			if (shouldRetry(errorCode)) {
				toastOptions.action = {
					label: "Retry",
					onClick: () => handleSubmit(e),
				};
			}

			toast.error(errorDetails.title, toastOptions);
		}
	};

	return (
		<div className="w-full max-w-md px-6 md:px-0">
			<form onSubmit={handleSubmit} className="space-y-3 md:space-y-4">
				{/* Error Display */}
				<AnimatePresence>
					{error && error.title && (
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
						value={username}
						onChange={(e) => setUsername(e.target.value)}
						className={`mt-1 block w-full rounded-md border px-3 py-1.5 md:py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 dark:bg-gray-800 dark:text-white transition-all ${
							error.title
								? "border-red-300 focus:border-red-500 focus:ring-red-500 dark:border-red-700"
								: "border-gray-300 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-700"
						}`}
						disabled={isLoggingIn}
					/>
				</div>

				<div>
					<label
						htmlFor="password"
						className="block text-sm font-medium text-gray-700 dark:text-gray-300"
					>
						{t("password")}
					</label>
					<div className="relative">
						<input
							id="password"
							type={showPassword ? "text" : "password"}
							required
							value={password}
							onChange={(e) => setPassword(e.target.value)}
							className={`mt-1 block w-full rounded-md border pr-10 px-3 py-1.5 md:py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 dark:bg-gray-800 dark:text-white transition-all ${
								error.title
									? "border-red-300 focus:border-red-500 focus:ring-red-500 dark:border-red-700"
									: "border-gray-300 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-700"
							}`}
							disabled={isLoggingIn}
						/>
						<button
							type="button"
							onClick={() => setShowPassword((prev) => !prev)}
							className="absolute inset-y-0 right-0 flex items-center pr-3 mt-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
							aria-label={showPassword ? t("hide_password") : t("show_password")}
						>
							{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
						</button>
					</div>
				</div>

				<button
					type="submit"
					disabled={isLoggingIn}
					className="w-full rounded-md bg-blue-600 px-4 py-1.5 md:py-2 text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 transition-all text-sm md:text-base flex items-center justify-center gap-2"
				>
					{isLoggingIn ? (
						<>
							<Spinner size="sm" className="text-white" />
							<span>{t("signing_in")}</span>
						</>
					) : (
						t("sign_in")
					)}
				</button>
			</form>

			{authType === "LOCAL" && (
				<div className="mt-4 text-center text-sm">
					<p className="text-gray-600 dark:text-gray-400">
						{t("dont_have_account")}{" "}
						<Link
							href="/register"
							className="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400"
						>
							{t("sign_up")}
						</Link>
					</p>
				</div>
			)}
		</div>
	);
}
