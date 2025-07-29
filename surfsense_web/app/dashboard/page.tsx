"use client";

import { motion, type Variants } from "framer-motion";
import { AlertCircle, Loader2, Plus, Search, Trash2 } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Logo } from "@/components/Logo";
import { ThemeTogglerComponent } from "@/components/theme/theme-toggle";
import { UserDropdown } from "@/components/UserDropdown";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Spotlight } from "@/components/ui/spotlight";
import { Tilt } from "@/components/ui/tilt";
import { useSearchSpaces } from "@/hooks/use-search-spaces";
import { apiClient } from "@/lib/api";

interface User {
	id: string;
	email: string;
	is_active: boolean;
	is_superuser: boolean;
	is_verified: boolean;
}

/**
 * Formats a date string into a readable format
 * @param dateString - The date string to format
 * @returns Formatted date string (e.g., "Jan 1, 2023")
 */
const formatDate = (dateString: string): string => {
	return new Date(dateString).toLocaleDateString("en-US", {
		year: "numeric",
		month: "short",
		day: "numeric",
	});
};

/**
 * Loading screen component with animation
 */
const LoadingScreen = () => {
	return (
		<div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
			<motion.div
				initial={{ opacity: 0, scale: 0.8 }}
				animate={{ opacity: 1, scale: 1 }}
				transition={{ duration: 0.5 }}
			>
				<Card className="w-[350px] bg-background/60 backdrop-blur-sm">
					<CardHeader className="pb-2">
						<CardTitle className="text-xl font-medium">Loading</CardTitle>
						<CardDescription>Fetching your search spaces...</CardDescription>
					</CardHeader>
					<CardContent className="flex justify-center py-6">
						<motion.div
							animate={{ rotate: 360 }}
							transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
						>
							<Loader2 className="h-12 w-12 text-primary" />
						</motion.div>
					</CardContent>
					<CardFooter className="border-t pt-4 text-sm text-muted-foreground">
						This may take a moment
					</CardFooter>
				</Card>
			</motion.div>
		</div>
	);
};

/**
 * Error screen component with animation
 */
const ErrorScreen = ({ message }: { message: string }) => {
	const router = useRouter();

	return (
		<div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
			>
				<Card className="w-[400px] bg-background/60 backdrop-blur-sm border-destructive/20">
					<CardHeader className="pb-2">
						<div className="flex items-center gap-2">
							<AlertCircle className="h-5 w-5 text-destructive" />
							<CardTitle className="text-xl font-medium">Error</CardTitle>
						</div>
						<CardDescription>Something went wrong</CardDescription>
					</CardHeader>
					<CardContent>
						<Alert variant="destructive" className="bg-destructive/10 border-destructive/30">
							<AlertCircle className="h-4 w-4" />
							<AlertTitle>Error Details</AlertTitle>
							<AlertDescription className="mt-2">{message}</AlertDescription>
						</Alert>
					</CardContent>
					<CardFooter className="flex justify-end gap-2 border-t pt-4">
						<Button variant="outline" onClick={() => router.refresh()}>
							Try Again
						</Button>
						<Button onClick={() => router.push("/")}>Go Home</Button>
					</CardFooter>
				</Card>
			</motion.div>
		</div>
	);
};

const DashboardPage = () => {
	// Animation variants
	const containerVariants: Variants = {
		hidden: { opacity: 0 },
		visible: {
			opacity: 1,
			transition: {
				staggerChildren: 0.1,
			},
		},
	};

	const itemVariants: Variants = {
		hidden: { y: 20, opacity: 0 },
		visible: {
			y: 0,
			opacity: 1,
			transition: {
				type: "spring",
				stiffness: 300,
				damping: 24,
			},
		},
	};

	const { searchSpaces, loading, error, refreshSearchSpaces } = useSearchSpaces();

	// User state management
	const [user, setUser] = useState<User | null>(null);
	const [isLoadingUser, setIsLoadingUser] = useState(true);
	const [userError, setUserError] = useState<string | null>(null);

	// Fetch user details
	useEffect(() => {
		const fetchUser = async () => {
			try {
				if (typeof window === "undefined") return;

				try {
					const userData = await apiClient.get<User>("users/me");
					setUser(userData);
					setUserError(null);
				} catch (error) {
					console.error("Error fetching user:", error);
					setUserError(error instanceof Error ? error.message : "Unknown error occurred");
				} finally {
					setIsLoadingUser(false);
				}
			} catch (error) {
				console.error("Error in fetchUser:", error);
				setIsLoadingUser(false);
			}
		};

		fetchUser();
	}, []);

	// Create user object for UserDropdown
	const customUser = {
		name: user?.email ? user.email.split("@")[0] : "User",
		email:
			user?.email ||
			(isLoadingUser ? "Loading..." : userError ? "Error loading user" : "Unknown User"),
		avatar: "/icon-128.png", // Default avatar
	};

	if (loading) return <LoadingScreen />;
	if (error) return <ErrorScreen message={error} />;

	const handleDeleteSearchSpace = async (id: number) => {
		// Send DELETE request to the API
		try {
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${id}`,
				{
					method: "DELETE",
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
				}
			);

			if (!response.ok) {
				toast.error("Failed to delete search space");
				throw new Error("Failed to delete search space");
			}

			// Refresh the search spaces list after successful deletion
			refreshSearchSpaces();
		} catch (error) {
			console.error("Error deleting search space:", error);
			toast.error("An error occurred while deleting the search space");
			return;
		}
		toast.success("Search space deleted successfully");
	};

	return (
		<motion.div
			className="container mx-auto py-10"
			initial="hidden"
			animate="visible"
			variants={containerVariants}
		>
			<motion.div className="flex flex-col space-y-6" variants={itemVariants}>
				<div className="flex flex-row space-x-4 justify-between">
					<div className="flex flex-row space-x-4">
						<Logo className="w-10 h-10 rounded-md" />
						<div className="flex flex-col space-y-2">
							<h1 className="text-4xl font-bold">SurfSense Dashboard</h1>
							<p className="text-muted-foreground">Welcome to your SurfSense dashboard.</p>
						</div>
					</div>
					<div className="flex items-center space-x-3">
						<UserDropdown user={customUser} />
						<ThemeTogglerComponent />
					</div>
				</div>

				<div className="flex flex-col space-y-6 mt-6">
					<div className="flex justify-between items-center">
						<h2 className="text-2xl font-semibold">Your Search Spaces</h2>
						<motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
							<Link href="/dashboard/searchspaces">
								<Button className="h-10">
									<Plus className="mr-2 h-4 w-4" />
									Create Search Space
								</Button>
							</Link>
						</motion.div>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
						{searchSpaces &&
							searchSpaces.length > 0 &&
							searchSpaces.map((space) => (
								<Link href={`/dashboard/${space.id}/documents`} key={space.id}>
									<motion.div key={space.id} variants={itemVariants} className="aspect-[4/3]">
										<Tilt
											rotationFactor={6}
											isRevese
											springOptions={{
												stiffness: 26.7,
												damping: 4.1,
												mass: 0.2,
											}}
											className="group relative rounded-lg h-full"
										>
											<Spotlight
												className="z-10 from-blue-500/20 via-blue-300/10 to-blue-200/5 blur-2xl"
												size={248}
												springOptions={{
													stiffness: 26.7,
													damping: 4.1,
													mass: 0.2,
												}}
											/>
											<div className="flex flex-col h-full overflow-hidden rounded-xl border bg-muted/30 backdrop-blur-sm transition-all hover:border-primary/50">
												<div className="relative h-32 w-full overflow-hidden">
													<Image
														src="https://images.unsplash.com/photo-1519389950473-47ba0277781c?ixlib=rb-4.0.3&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=1740&q=80"
														alt={space.name}
														className="h-full w-full object-cover grayscale duration-700 group-hover:grayscale-0"
														width={248}
														height={248}
													/>
													<div className="absolute inset-0 bg-gradient-to-t from-background/80 to-transparent" />
													<div className="absolute top-2 right-2">
														<div>
															<AlertDialog>
																<AlertDialogTrigger asChild>
																	<Button
																		variant="ghost"
																		size="icon"
																		className="h-8 w-8 rounded-full bg-background/50 backdrop-blur-sm hover:bg-destructive/90 cursor-pointer"
																	>
																		<Trash2 className="h-4 w-4" />
																	</Button>
																</AlertDialogTrigger>
																<AlertDialogContent>
																	<AlertDialogHeader>
																		<AlertDialogTitle>Delete Search Space</AlertDialogTitle>
																		<AlertDialogDescription>
																			Are you sure you want to delete &quot;{space.name}&quot;? This
																			action cannot be undone. All documents, chats, and podcasts in
																			this search space will be permanently deleted.
																		</AlertDialogDescription>
																	</AlertDialogHeader>
																	<AlertDialogFooter>
																		<AlertDialogCancel>Cancel</AlertDialogCancel>
																		<AlertDialogAction
																			onClick={() => handleDeleteSearchSpace(space.id)}
																			className="bg-destructive hover:bg-destructive/90"
																		>
																			Delete
																		</AlertDialogAction>
																	</AlertDialogFooter>
																</AlertDialogContent>
															</AlertDialog>
														</div>
													</div>
												</div>

												<div className="flex flex-1 flex-col justify-between p-4">
													<div>
														<h3 className="font-medium text-lg">{space.name}</h3>
														<p className="mt-1 text-sm text-muted-foreground">
															{space.description}
														</p>
													</div>
													<div className="mt-4 flex justify-between text-xs text-muted-foreground">
														{/* <span>{space.title}</span> */}
														<span>Created {formatDate(space.created_at)}</span>
													</div>
												</div>
											</div>
										</Tilt>
									</motion.div>
								</Link>
							))}

						{searchSpaces.length === 0 && (
							<motion.div
								variants={itemVariants}
								className="col-span-full flex flex-col items-center justify-center p-12 text-center"
							>
								<div className="rounded-full bg-muted/50 p-4 mb-4">
									<Search className="h-8 w-8 text-muted-foreground" />
								</div>
								<h3 className="text-lg font-medium mb-2">No search spaces found</h3>
								<p className="text-muted-foreground mb-6">
									Create your first search space to get started
								</p>
								<Link href="/dashboard/searchspaces">
									<Button>
										<Plus className="mr-2 h-4 w-4" />
										Create Search Space
									</Button>
								</Link>
							</motion.div>
						)}

						{searchSpaces.length > 0 && (
							<motion.div variants={itemVariants} className="aspect-[4/3]">
								<Tilt
									rotationFactor={6}
									isRevese
									springOptions={{
										stiffness: 26.7,
										damping: 4.1,
										mass: 0.2,
									}}
									className="group relative rounded-lg h-full"
								>
									<Link href="/dashboard/searchspaces" className="flex h-full">
										<div className="flex flex-col items-center justify-center h-full w-full rounded-xl border border-dashed bg-muted/10 hover:border-primary/50 transition-colors">
											<Plus className="h-10 w-10 mb-3 text-muted-foreground" />
											<span className="text-sm font-medium">Add New Search Space</span>
										</div>
									</Link>
								</Tilt>
							</motion.div>
						)}
					</div>
				</div>
			</motion.div>
		</motion.div>
	);
};

export default DashboardPage;
