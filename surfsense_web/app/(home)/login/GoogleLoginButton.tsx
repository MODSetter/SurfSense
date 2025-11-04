"use client";
import { IconBrandGoogleFilled } from "@tabler/icons-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { Logo } from "@/components/Logo";
import { AmbientBackground } from "./AmbientBackground";

export function GoogleLoginButton() {
	const t = useTranslations("auth");

	const handleGoogleLogin = () => {
		// Redirect to Google OAuth authorization URL
		fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/auth/google/authorize`)
			.then((response) => {
				if (!response.ok) {
					throw new Error("Failed to get authorization URL");
				}
				return response.json();
			})
			.then((data) => {
				if (data.authorization_url) {
					window.location.href = data.authorization_url;
				} else {
					console.error("No authorization URL received");
				}
			})
			.catch((error) => {
				console.error("Error during Google login:", error);
			});
	};
	return (
		<div className="relative w-full overflow-hidden">
			<AmbientBackground />
			<div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center">
				<Logo className="rounded-md" />
				<h1 className="my-8 text-xl font-bold text-neutral-800 dark:text-neutral-100 md:text-4xl">
					{t("welcome_back")}
				</h1>
				{/* 
				<motion.div
					initial={{ opacity: 0, y: -5 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.3 }}
					className="mb-4 w-full overflow-hidden rounded-lg border border-yellow-200 bg-yellow-50 text-yellow-900 shadow-sm dark:border-yellow-900/30 dark:bg-yellow-900/20 dark:text-yellow-200"
				>
					<motion.div
						className="flex items-center gap-2 p-4"
						initial={{ x: -5 }}
						animate={{ x: 0 }}
						transition={{ delay: 0.1, duration: 0.2 }}
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
							className="flex-shrink-0"
						>
							<title>Google Logo</title>
							<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
							<line x1="12" y1="9" x2="12" y2="13" />
							<line x1="12" y1="17" x2="12.01" y2="17" />
						</svg>
						<div className="ml-1">
							<p className="text-sm font-medium">
								{t("cloud_dev_notice")}{" "}
								<a
									href="/docs"
									className="text-blue-600 underline dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
								>
									{t("docs")}
								</a>{" "}
								{t("cloud_dev_self_hosted")}
							</p>
						</div>
					</motion.div>
				</motion.div> */}

				<motion.button
					whileHover={{ scale: 1.02 }}
					whileTap={{ scale: 0.98 }}
					className="group/btn relative flex w-full items-center justify-center space-x-2 rounded-lg bg-white px-6 py-4 text-neutral-700 shadow-lg transition-all duration-200 hover:shadow-xl dark:bg-neutral-800 dark:text-neutral-200"
					onClick={handleGoogleLogin}
				>
					<div className="absolute inset-0 h-full w-full transform opacity-0 transition duration-200 group-hover/btn:opacity-100">
						<div className="absolute -left-px -top-px h-4 w-4 rounded-tl-lg border-l-2 border-t-2 border-blue-500 bg-transparent transition-all duration-200 group-hover/btn:-left-2 group-hover/btn:-top-2"></div>
						<div className="absolute -right-px -top-px h-4 w-4 rounded-tr-lg border-r-2 border-t-2 border-blue-500 bg-transparent transition-all duration-200 group-hover/btn:-right-2 group-hover/btn:-top-2"></div>
						<div className="absolute -bottom-px -left-px h-4 w-4 rounded-bl-lg border-b-2 border-l-2 border-blue-500 bg-transparent transition-all duration-200 group-hover/btn:-bottom-2 group-hover/btn:-left-2"></div>
						<div className="absolute -bottom-px -right-px h-4 w-4 rounded-br-lg border-b-2 border-r-2 border-blue-500 bg-transparent transition-all duration-200 group-hover/btn:-bottom-2 group-hover/btn:-right-2"></div>
					</div>
					<IconBrandGoogleFilled className="h-5 w-5 text-neutral-700 dark:text-neutral-200" />
					<span className="text-base font-medium">{t("continue_with_google")}</span>
				</motion.button>
			</div>
		</div>
	);
}
