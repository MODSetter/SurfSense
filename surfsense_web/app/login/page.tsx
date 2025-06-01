"use client";

import { useState, useEffect, Suspense } from "react";
import { GoogleLoginButton } from "./GoogleLoginButton";
import { LocalLoginForm } from "./LocalLoginForm";
import { Logo } from "@/components/Logo";
import { AmbientBackground } from "./AmbientBackground";
import { useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";

function LoginContent() {
  const [authType, setAuthType] = useState<string | null>(null);
  const [registrationSuccess, setRegistrationSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const searchParams = useSearchParams();

  useEffect(() => {
    // Check if the user was redirected from registration
    if (searchParams.get("registered") === "true") {
      setRegistrationSuccess(true);
    }

    // Get the auth type from environment variables
    setAuthType(process.env.NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE || "GOOGLE");
    setIsLoading(false);
  }, [searchParams]);

  // Show loading state while determining auth type
  if (isLoading) {
    return (
      <div className="relative w-full overflow-hidden">
        <AmbientBackground />
        <div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center">
          <Logo className="rounded-md" />
          <div className="mt-8 flex items-center space-x-2">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            <span className="text-muted-foreground">Loading...</span>
          </div>
        </div>
      </div>
    );
  }

  if (authType === "GOOGLE") {
    return <GoogleLoginButton />;
  }

  return (
    <div className="relative w-full overflow-hidden">
      <AmbientBackground />
      <div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center">
        <Logo className="rounded-md" />
        <h1 className="my-8 text-xl font-bold text-neutral-800 dark:text-neutral-100 md:text-4xl">
          Sign In
        </h1>

        {registrationSuccess && (
          <div className="mb-4 w-full rounded-md bg-green-50 p-4 text-sm text-green-500 dark:bg-green-900/20 dark:text-green-200">
            Registration successful! You can now sign in with your credentials.
          </div>
        )}

        <LocalLoginForm />
      </div>
    </div>
  );
}

// Loading fallback for Suspense
const LoadingFallback = () => (
  <div className="relative w-full overflow-hidden">
    <AmbientBackground />
    <div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center">
      <Logo className="rounded-md" />
      <div className="mt-8 flex items-center space-x-2">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        <span className="text-muted-foreground">Loading...</span>
      </div>
    </div>
  </div>
);

export default function LoginPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <LoginContent />
    </Suspense>
  );
} 