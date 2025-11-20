"use client";
import { useAtom } from "jotai";
import { Eye, EyeOff, ShieldCheck } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { loginMutationAtom } from "@/atoms/auth/auth-mutation.atoms";
import { verify2FAMutationAtom } from "@/atoms/auth/two-fa-mutation.atoms";
import { useSiteConfig } from "@/contexts/SiteConfigContext";
import { getAuthErrorDetails, isNetworkError, shouldRetry } from "@/lib/auth-errors";
import { ValidationError } from "@/lib/error";

export function LocalLoginForm() {
	const t = useTranslations("auth");
	const tCommon = useTranslations("common");
	const { config } = useSiteConfig();
	const [username, setUsername] = useState("");
	const [password, setPassword] = useState("");
	const [showPassword, setShowPassword] = useState(false);
	const [requires2FA, setRequires2FA] = useState(false);
	const [temporaryToken, setTemporaryToken] = useState("");
	const [totpCode, setTotpCode] = useState("");
	const [error, setError] = useState<{
		title: string | null;
		message: string | null;
	}>({
		title: null,
		message: null,
	});
	const router = useRouter();
	const [{ mutateAsync: login, isPending: isLoggingIn }] = useAtom(loginMutationAtom);
	const [{ mutateAsync: verify2FA, isPending: isVerifying2FA }] = useAtom(verify2FAMutationAtom);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setError({ title: null, message: null }); // Clear any previous errors

		// Show loading toast
		const loadingToast = toast.loading(tCommon("loading"));

		try {
			const data = await login({
				username,
				password,
				grant_type: "password",
			});

			// Check if 2FA is required
			if (data.requires_2fa && data.temporary_token) {
				// Dismiss loading toast
				toast.dismiss(loadingToast);

				// Set 2FA state
				setRequires2FA(true);
				setTemporaryToken(data.temporary_token);

				// Show info toast
				toast.info("Two-Factor Authentication Required", {
					description: "Please enter the 6-digit code from your authenticator app.",
					duration: 5000,
				});

				return;
			}

			// No 2FA required - proceed with normal login
			if (!data.access_token) {
				throw new Error("No access token received");
			}

			// Success toast
			toast.success(t("login_success"), {
				id: loadingToast,
				description: "Redirecting to dashboard...",
				duration: 2000,
			});

			// Small delay to show success message
			setTimeout(() => {
				router.push(`/auth/callback?token=${data.access_token}`);
			}, 500);
		} catch (err) {
			if (err instanceof ValidationError) {
				setError({ title: err.name, message: err.message });
				toast.error(err.name, {
					id: loadingToast,
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

			// Get detailed error information from auth-errors utility
			const errorDetails = getAuthErrorDetails(errorCode);

			// Set persistent error display
			setError({
				title: errorDetails.title,
				message: errorDetails.description,
			});

			// Show error toast with conditional retry action
			const toastOptions: any = {
				id: loadingToast,
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

	const handle2FAVerification = async (e: React.FormEvent) => {
		e.preventDefault();
		setError({ title: null, message: null }); // Clear any previous errors

		// Show loading toast
		const loadingToast = toast.loading("Verifying 2FA code...");

		try {
			const data = await verify2FA({
				temporary_token: temporaryToken,
				code: totpCode,
			});

			// Success toast
			toast.success("Verification Successful", {
				id: loadingToast,
				description: "Redirecting to dashboard...",
				duration: 2000,
			});

			// Small delay to show success message
			setTimeout(() => {
				router.push(`/auth/callback?token=${data.access_token}`);
			}, 500);
		} catch (err) {
			if (err instanceof ValidationError) {
				setError({ title: err.name, message: err.message });
				toast.error(err.name, {
					id: loadingToast,
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

			// Get detailed error information from auth-errors utility
			const errorDetails = getAuthErrorDetails(errorCode);

			// Set persistent error display
			setError({
				title: errorDetails.title,
				message: errorDetails.description,
			});

			// Show error toast
			toast.error(errorDetails.title, {
				id: loadingToast,
				description: errorDetails.description,
				duration: 6000,
			});
		}
	};

	return (
		<div className="w-full max-w-md">
			<form onSubmit={handleSubmit} className="space-y-4">
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
						className={`mt-1 block w-full rounded-md border px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 dark:bg-gray-800 dark:text-white transition-colors ${
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
							className={`mt-1 block w-full rounded-md border pr-10 px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 dark:bg-gray-800 dark:text-white transition-colors ${
								error.title
									? "border-red-300 focus:border-red-500 focus:ring-red-500 dark:border-red-700"
									: "border-gray-300 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-700"
							}`}
							disabled={isLoggingIn || requires2FA}
						/>
						<button
							type="button"
							onClick={() => setShowPassword((prev) => !prev)}
							className="absolute inset-y-0 right-0 flex items-center pr-3 mt-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
							aria-label={showPassword ? t("hide_password") : t("show_password")}
							disabled={requires2FA}
						>
							{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
						</button>
					</div>
				</div>

				{/* 2FA Code Input - Shows when 2FA is required */}
				<AnimatePresence>
					{requires2FA && (
						<motion.div
							initial={{ opacity: 0, height: 0, scale: 0.95 }}
							animate={{ opacity: 1, height: "auto", scale: 1 }}
							exit={{ opacity: 0, height: 0, scale: 0.95 }}
							transition={{ duration: 0.3 }}
							className="overflow-hidden"
						>
							<div>
								<label
									htmlFor="totp-code"
									className="block text-sm font-medium text-gray-700 dark:text-gray-300"
								>
									<div className="flex items-center gap-2">
										<ShieldCheck className="h-4 w-4 text-blue-600 dark:text-blue-400" />
										<span>Two-Factor Authentication Code</span>
									</div>
								</label>
								<input
									id="totp-code"
									type="text"
									inputMode="numeric"
									pattern="[0-9]{6}"
									maxLength={6}
									required={requires2FA}
									value={totpCode}
									onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
									placeholder="000000"
									className={`mt-1 block w-full rounded-md border px-3 py-2 text-center text-lg tracking-widest shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 dark:bg-gray-800 dark:text-white transition-colors ${
										error.title
											? "border-red-300 focus:border-red-500 focus:ring-red-500 dark:border-red-700"
											: "border-gray-300 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-700"
									}`}
									disabled={isVerifying2FA}
									autoFocus
									autoComplete="one-time-code"
								/>
								<p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
									Enter the 6-digit code from your authenticator app (Google Authenticator, Authy, etc.)
								</p>
							</div>
						</motion.div>
					)}
				</AnimatePresence>

				{/* Show different button based on 2FA state */}
				{!requires2FA ? (
					<button
						type="submit"
						disabled={isLoggingIn}
						className="w-full rounded-md bg-blue-600 px-4 py-2 text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
					>
						{isLoggingIn ? tCommon("loading") : t("sign_in")}
					</button>
				) : (
					<div className="space-y-2">
						<button
							type="button"
							onClick={handle2FAVerification}
							disabled={isVerifying2FA || totpCode.length !== 6}
							className="w-full rounded-md bg-blue-600 px-4 py-2 text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
						>
							{isVerifying2FA ? "Verifying..." : "Verify Code"}
						</button>
						<button
							type="button"
							onClick={() => {
								setRequires2FA(false);
								setTemporaryToken("");
								setTotpCode("");
								setError({ title: null, message: null });
							}}
							disabled={isVerifying2FA}
							className="w-full rounded-md bg-gray-200 dark:bg-gray-700 px-4 py-2 text-gray-700 dark:text-gray-300 shadow-sm hover:bg-gray-300 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
						>
							Back to Login
						</button>
					</div>
				)}
			</form>

			{!config.disable_registration && (
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
