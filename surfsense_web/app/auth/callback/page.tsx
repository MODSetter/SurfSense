import { Suspense } from "react";
import TokenHandler from "@/components/TokenHandler";

export default function AuthCallbackPage() {
	return (
		<div className="container mx-auto p-4">
			<h1 className="text-2xl font-bold mb-4">Authentication Callback</h1>
			<Suspense
				fallback={
					<div className="flex items-center justify-center min-h-[200px]">
						<div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
					</div>
				}
			>
				<TokenHandler
					redirectPath="/dashboard"
					tokenParamName="token"
					storageKey="surfsense_bearer_token"
				/>
			</Suspense>
		</div>
	);
}
