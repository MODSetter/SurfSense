'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function AuthCallbackPage() {
	const router = useRouter();

	useEffect(() => {
		// SECURITY: With HttpOnly cookies, auth is handled automatically
		// No need to extract tokens from URL - just redirect to dashboard
		router.push('/dashboard');
	}, [router]);

	return (
		<div className="container mx-auto p-4 flex items-center justify-center min-h-screen">
			<div className="text-center">
				<h1 className="text-2xl font-bold mb-4">Authentication Successful</h1>
				<p className="text-gray-600 dark:text-gray-400 mb-4">
					Redirecting you to the dashboard...
				</p>
				<div className="flex justify-center">
					<div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
				</div>
			</div>
		</div>
	);
}
