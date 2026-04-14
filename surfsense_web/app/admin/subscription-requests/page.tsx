"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { authenticatedFetch, isAuthenticated, redirectToLogin } from "@/lib/auth-utils";
import { BACKEND_URL } from "@/lib/env-config";

interface SubscriptionRequestItem {
	id: string;
	user_id: string;
	user_email: string;
	plan_id: string;
	status: string;
	created_at: string;
	approved_at: string | null;
	approved_by: string | null;
}

export default function AdminSubscriptionRequestsPage() {
	const [requests, setRequests] = useState<SubscriptionRequestItem[]>([]);
	const [loading, setLoading] = useState(true);
	const [actionInProgress, setActionInProgress] = useState<string | null>(null);
	const [accessDenied, setAccessDenied] = useState(false);

	const fetchRequests = async () => {
		if (!isAuthenticated()) {
			redirectToLogin();
			return;
		}

		try {
			const response = await authenticatedFetch(
				`${BACKEND_URL}/api/v1/admin/subscription-requests`
			);
			if (response.status === 401) {
				redirectToLogin();
				return;
			}
			if (response.status === 403) {
				setAccessDenied(true);
				return;
			}
			if (!response.ok) {
				toast.error("Failed to load subscription requests.");
				return;
			}
			const data: SubscriptionRequestItem[] = await response.json();
			setRequests(data);
		} catch {
			toast.error("Failed to load subscription requests.");
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		fetchRequests();
	// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	const handleAction = async (requestId: string, action: "approve" | "reject") => {
		setActionInProgress(requestId);
		try {
			const response = await authenticatedFetch(
				`${BACKEND_URL}/api/v1/admin/subscription-requests/${requestId}/${action}`,
				{ method: "POST" }
			);
			if (!response.ok) {
				const err = await response.json().catch(() => ({}));
				toast.error(err.detail ?? `Failed to ${action} request.`);
				return;
			}
			toast.success(`Request ${action}d successfully.`);
			setRequests((prev) => prev.filter((r) => r.id !== requestId));
		} catch {
			toast.error(`Failed to ${action} request.`);
		} finally {
			setActionInProgress(null);
		}
	};

	if (accessDenied) {
		return (
			<div className="flex h-screen items-center justify-center">
				<p className="text-lg font-medium text-destructive">
					Access denied. Superuser privileges required.
				</p>
			</div>
		);
	}

	if (loading) {
		return (
			<div className="flex h-screen items-center justify-center">
				<p className="text-muted-foreground">Loading…</p>
			</div>
		);
	}

	return (
		<div className="container mx-auto max-w-4xl py-10">
			<h1 className="mb-6 text-2xl font-bold">Subscription Requests</h1>

			{requests.length === 0 ? (
				<p className="text-muted-foreground">No pending subscription requests.</p>
			) : (
				<div className="overflow-x-auto rounded-lg border">
					<table className="w-full text-sm">
						<thead className="bg-muted/50">
							<tr>
								<th className="px-4 py-3 text-left font-medium">User</th>
								<th className="px-4 py-3 text-left font-medium">Plan</th>
								<th className="px-4 py-3 text-left font-medium">Requested At</th>
								<th className="px-4 py-3 text-left font-medium">Actions</th>
							</tr>
						</thead>
						<tbody className="divide-y">
							{requests.map((req) => (
								<tr key={req.id} className="hover:bg-muted/30">
									<td className="px-4 py-3">{req.user_email}</td>
									<td className="px-4 py-3 capitalize">{req.plan_id.replace(/_/g, " ")}</td>
									<td className="px-4 py-3">
										{new Date(req.created_at).toLocaleString()}
									</td>
									<td className="px-4 py-3">
										<div className="flex gap-2">
											<button
												className="rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
												disabled={actionInProgress === req.id}
												onClick={() => handleAction(req.id, "approve")}
											>
												Approve
											</button>
											<button
												className="rounded bg-destructive px-3 py-1 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
												disabled={actionInProgress === req.id}
												onClick={() => handleAction(req.id, "reject")}
											>
												Reject
											</button>
										</div>
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			)}
		</div>
	);
}
