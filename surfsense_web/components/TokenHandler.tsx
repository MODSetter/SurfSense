// mPass SSO: This component is disabled because oauth2-proxy ForwardAuth
// handles login via Cognito. The cookie-handoff pattern (proxy_login →
// cookie → frontend reads cookie → JWT in localStorage) replaces the
// native OAuth token extraction flow below.
//
// To restore native OAuth login, uncomment this file and re-register
// the /auth/callback route.


// "use client";
//
// import { useEffect } from "react";
// import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
// import { getAndClearRedirectPath, setBearerToken, setRefreshToken } from "@/lib/auth-utils";
// import { trackLoginSuccess } from "@/lib/posthog/events";
//
// interface TokenHandlerProps {
// 	redirectPath?: string;
// 	tokenParamName?: string;
// 	storageKey?: string;
// }
//
// const TokenHandler = ({
// 	redirectPath = "/dashboard",
// 	tokenParamName = "token",
// 	storageKey = "surfsense_bearer_token",
// }: TokenHandlerProps) => {
// 	useGlobalLoadingEffect(true);
//
// 	useEffect(() => {
// 		if (typeof window === "undefined") return;
//
// 		const params = new URLSearchParams(window.location.search);
// 		const token = params.get(tokenParamName);
// 		const refreshToken = params.get("refresh_token");
//
// 		if (token) {
// 			try {
// 				const alreadyTracked = sessionStorage.getItem("login_success_tracked");
// 				if (!alreadyTracked) {
// 					trackLoginSuccess("google");
// 				}
// 				sessionStorage.removeItem("login_success_tracked");
//
// 				localStorage.setItem(storageKey, token);
// 				setBearerToken(token);
//
// 				if (refreshToken) {
// 					setRefreshToken(refreshToken);
// 				}
//
// 				const savedRedirectPath = getAndClearRedirectPath();
// 				const finalRedirectPath = savedRedirectPath || redirectPath;
// 				window.location.href = finalRedirectPath;
// 			} catch (error) {
// 				console.error("Error storing token in localStorage:", error);
// 				window.location.href = redirectPath;
// 			}
// 		}
// 	}, [tokenParamName, storageKey, redirectPath]);
//
// 	return null;
// };
//
// export default TokenHandler;
