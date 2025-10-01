"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { MoveLeftIcon, Plus, Search, Trash2 } from "lucide-react";
import { motion, type Variants } from "motion/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
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
	Form,
	FormControl,
	FormDescription,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Spotlight } from "@/components/ui/spotlight";
import { Tilt } from "@/components/ui/tilt";
import { cn } from "@/lib/utils";

// Define the form schema with Zod
const searchSpaceFormSchema = z.object({
	name: z.string().min(3, "Name is required"),
	description: z.string().min(10, "Description is required"),
});

// Define the type for the form values
type SearchSpaceFormValues = z.infer<typeof searchSpaceFormSchema>;

interface SearchSpaceFormProps {
	onSubmit?: (data: { name: string; description: string }) => void;
	onDelete?: () => void;
	className?: string;
	isEditing?: boolean;
	initialData?: { name: string; description: string };
}

export function SearchSpaceForm({
	onSubmit,
	onDelete,
	className,
	isEditing = false,
	initialData = { name: "", description: "" },
}: SearchSpaceFormProps) {
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);
	const router = useRouter();

	// Initialize the form with React Hook Form and Zod validation
	const form = useForm<SearchSpaceFormValues>({
		resolver: zodResolver(searchSpaceFormSchema),
		defaultValues: {
			name: initialData.name,
			description: initialData.description,
		},
	});

	// Handle form submission
	const handleFormSubmit = (values: SearchSpaceFormValues) => {
		if (onSubmit) {
			onSubmit(values);
		}
	};

	// Handle delete confirmation
	const handleDelete = () => {
		if (onDelete) {
			onDelete();
		}
		setShowDeleteDialog(false);
	};

	// Animation variants
	const containerVariants = {
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

	return (
		<motion.div
			className={cn("space-y-8", className)}
			initial="hidden"
			animate="visible"
			variants={containerVariants}
		>
			<motion.div className="flex items-center justify-between" variants={itemVariants}>
				<div className="flex flex-col space-y-2">
					<h2 className="text-3xl font-bold tracking-tight">
						{isEditing ? "Edit Search Space" : "Create Search Space"}
					</h2>
					<p className="text-muted-foreground">
						{isEditing
							? "Update your search space details"
							: "Create a new search space to organize your documents, chats, and podcasts."}
					</p>
				</div>
				<Button
					variant="ghost"
					className="group relative rounded-full p-3 bg-background/80 hover:bg-muted border border-border hover:border-primary/20 shadow-sm hover:shadow-md transition-all duration-200 backdrop-blur-sm"
					onClick={() => {
						router.push("/dashboard");
					}}
				>
					<MoveLeftIcon
						size={18}
						className="text-muted-foreground group-hover:text-foreground transition-colors duration-200"
					/>
					<div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-500/10 to-purple-500/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
				</Button>
			</motion.div>

			<motion.div className="w-full" variants={itemVariants}>
				<Tilt
					rotationFactor={6}
					isRevese
					springOptions={{
						stiffness: 26.7,
						damping: 4.1,
						mass: 0.2,
					}}
					className="group relative rounded-lg"
				>
					<Spotlight
						className="z-10 from-blue-500/20 via-blue-300/10 to-blue-200/5 blur-2xl"
						size={300}
						springOptions={{
							stiffness: 26.7,
							damping: 4.1,
							mass: 0.2,
						}}
					/>
					<div className="flex flex-col p-8 rounded-xl border-2 bg-muted/30 backdrop-blur-sm transition-all hover:border-primary/50 shadow-sm">
						<div className="flex items-center justify-between mb-4">
							<div className="flex items-center space-x-4">
								<span className="p-3 rounded-full bg-blue-100 dark:bg-blue-950/50">
									<Search className="size-6 text-blue-500" />
								</span>
								<h3 className="text-xl font-semibold">Search Space</h3>
							</div>
							{isEditing && onDelete && (
								<AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
									<AlertDialogTrigger asChild>
										<Button
											variant="ghost"
											size="icon"
											className="h-8 w-8 rounded-full hover:bg-destructive/90 hover:text-destructive-foreground"
										>
											<Trash2 className="h-4 w-4" />
										</Button>
									</AlertDialogTrigger>
									<AlertDialogContent>
										<AlertDialogHeader>
											<AlertDialogTitle>Are you sure?</AlertDialogTitle>
											<AlertDialogDescription>
												This action cannot be undone. This will permanently delete your search
												space.
											</AlertDialogDescription>
										</AlertDialogHeader>
										<AlertDialogFooter>
											<AlertDialogCancel>Cancel</AlertDialogCancel>
											<AlertDialogAction onClick={handleDelete}>Delete</AlertDialogAction>
										</AlertDialogFooter>
									</AlertDialogContent>
								</AlertDialog>
							)}
						</div>
						<p className="text-muted-foreground">
							A search space allows you to organize and search through your documents, generate
							podcasts, and have AI-powered conversations about your content.
						</p>
					</div>
				</Tilt>
			</motion.div>

			<Separator className="my-4" />

			<Form {...form}>
				<form onSubmit={form.handleSubmit(handleFormSubmit)} className="space-y-6">
					<FormField
						control={form.control}
						name="name"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Name</FormLabel>
								<FormControl>
									<Input placeholder="Enter search space name" {...field} />
								</FormControl>
								<FormDescription>A unique name for your search space.</FormDescription>
								<FormMessage />
							</FormItem>
						)}
					/>

					<FormField
						control={form.control}
						name="description"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Description</FormLabel>
								<FormControl>
									<Input placeholder="Enter search space description" {...field} />
								</FormControl>
								<FormDescription>
									A brief description of what this search space will be used for.
								</FormDescription>
								<FormMessage />
							</FormItem>
						)}
					/>

					<div className="flex justify-end pt-2">
						<Button type="submit" className="w-full sm:w-auto">
							<Plus className="mr-2 h-4 w-4" />
							{isEditing ? "Update" : "Create"}
						</Button>
					</div>
				</form>
			</Form>
		</motion.div>
	);
}

export default SearchSpaceForm;
