"use client";

import { IconCheck, IconCopy, IconKey } from "@tabler/icons-react";
import { ArrowLeft } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useApiKey } from "@/hooks/use-api-key";

const fadeIn = {
	hidden: { opacity: 0 },
	visible: { opacity: 1, transition: { duration: 0.4 } },
};

const staggerContainer = {
	hidden: { opacity: 0 },
	visible: {
		opacity: 1,
		transition: {
			staggerChildren: 0.1,
		},
	},
};

const ApiKeyClient = () => {
	const { apiKey, isLoading, copied, copyToClipboard } = useApiKey();
	const router = useRouter();
	return (
		<div className="flex justify-center w-full min-h-screen py-10 px-4">
			<motion.div
				className="w-full max-w-3xl"
				initial="hidden"
				animate="visible"
				variants={staggerContainer}
			>
				<motion.div className="mb-8 text-center" variants={fadeIn}>
					<h1 className="text-3xl font-bold tracking-tight">API Key</h1>
					<p className="text-muted-foreground mt-2">
						Your API key for authenticating with the SurfSense API.
					</p>
				</motion.div>

				<motion.div variants={fadeIn}>
					<Alert className="mb-8">
						<IconKey className="h-4 w-4" />
						<AlertTitle>Important</AlertTitle>
						<AlertDescription>
							Your API key grants full access to your account. Never share it publicly or with
							unauthorized users.
						</AlertDescription>
					</Alert>
				</motion.div>

				<motion.div variants={fadeIn}>
					<Card>
						<CardHeader className="text-center">
							<CardTitle>Your API Key</CardTitle>
							<CardDescription>Use this key to authenticate your API requests.</CardDescription>
						</CardHeader>
						<CardContent>
							<AnimatePresence mode="wait">
								{isLoading ? (
									<motion.div
										key="loading"
										initial={{ opacity: 0 }}
										animate={{ opacity: 1 }}
										exit={{ opacity: 0 }}
										className="h-10 w-full bg-muted animate-pulse rounded-md"
									/>
								) : apiKey ? (
									<motion.div
										key="api-key"
										initial={{ opacity: 0, y: 10 }}
										animate={{ opacity: 1, y: 0 }}
										exit={{ opacity: 0, y: -10 }}
										transition={{ type: "spring", stiffness: 500, damping: 30 }}
										className="flex items-center space-x-2"
									>
										<div className="bg-muted p-3 rounded-md flex-1 font-mono text-sm overflow-x-auto whitespace-nowrap">
											<motion.div
												initial={{ opacity: 0 }}
												animate={{ opacity: 1 }}
												transition={{ duration: 0.5 }}
											>
												{apiKey}
											</motion.div>
										</div>
										<TooltipProvider>
											<Tooltip>
												<TooltipTrigger asChild>
													<Button
														variant="outline"
														size="icon"
														onClick={copyToClipboard}
														className="flex-shrink-0"
													>
														<motion.div
															whileTap={{ scale: 0.9 }}
															animate={copied ? { scale: [1, 1.2, 1] } : {}}
															transition={{ duration: 0.2 }}
														>
															{copied ? (
																<IconCheck className="h-4 w-4" />
															) : (
																<IconCopy className="h-4 w-4" />
															)}
														</motion.div>
													</Button>
												</TooltipTrigger>
												<TooltipContent>
													<p>{copied ? "Copied!" : "Copy to clipboard"}</p>
												</TooltipContent>
											</Tooltip>
										</TooltipProvider>
									</motion.div>
								) : (
									<motion.div
										key="no-key"
										initial={{ opacity: 0 }}
										animate={{ opacity: 1 }}
										exit={{ opacity: 0 }}
										className="text-muted-foreground text-center"
									>
										No API key found.
									</motion.div>
								)}
							</AnimatePresence>
						</CardContent>
					</Card>
				</motion.div>

				<motion.div
					className="mt-8"
					variants={fadeIn}
					initial={{ opacity: 0, y: 20 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ delay: 0.3 }}
				>
					<h2 className="text-xl font-semibold mb-4 text-center">How to use your API key</h2>
					<Card>
						<CardContent className="pt-6">
							<motion.div
								className="space-y-4"
								initial="hidden"
								animate="visible"
								variants={staggerContainer}
							>
								<motion.div variants={fadeIn}>
									<h3 className="font-medium mb-2 text-center">Authentication</h3>
									<p className="text-sm text-muted-foreground text-center">
										Include your API key in the Authorization header of your requests:
									</p>
									<motion.pre
										className="bg-muted p-3 rounded-md mt-2 overflow-x-auto"
										whileHover={{ scale: 1.01 }}
										transition={{ type: "spring", stiffness: 400, damping: 10 }}
									>
										<code className="text-xs">
											Authorization: Bearer {apiKey || "YOUR_API_KEY"}
										</code>
									</motion.pre>
								</motion.div>
							</motion.div>
						</CardContent>
					</Card>
				</motion.div>
			</motion.div>
			<div>
				<button
					onClick={() => router.push("/dashboard")}
					className="flex items-center justify-center h-10 w-10 rounded-lg bg-primary/10 hover:bg-primary/30 transition-colors"
					aria-label="Back to Dashboard"
					type="button"
				>
					<ArrowLeft className="h-5 w-5 text-primary" />
				</button>
			</div>
		</div>
	);
};

export default ApiKeyClient;
