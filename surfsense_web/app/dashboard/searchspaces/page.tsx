"use client";

import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { SearchSpaceForm } from "@/components/search-space-form";
export default function SearchSpacesPage() {
	const router = useRouter();
	const handleCreateSearchSpace = async (data: { name: string; description: string }) => {
		try {
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces`,
				{
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					body: JSON.stringify(data),
				}
			);

			if (!response.ok) {
				toast.error("Failed to create search space");
				throw new Error("Failed to create search space");
			}

			const result = await response.json();

			toast.success("Search space created successfully", {
				description: `"${data.name}" has been created.`,
			});

			router.push(`/dashboard`);

			return result;
		} catch (error) {
			console.error("Error creating search space:", error);
			throw error;
		}
	};

	return (
		<motion.div
			className="container mx-auto py-10"
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			transition={{ duration: 0.5 }}
		>
			<div className="mx-auto max-w-5xl">
				<SearchSpaceForm onSubmit={handleCreateSearchSpace} />
			</div>
		</motion.div>
	);
}
