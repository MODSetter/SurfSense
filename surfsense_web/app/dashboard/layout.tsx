"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useLLMPreferences } from '@/hooks/use-llm-configs';
import { Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const router = useRouter();
  const { loading, error, isOnboardingComplete } = useLLMPreferences();
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  useEffect(() => {
    // Check if user is authenticated
    const token = localStorage.getItem('surfsense_bearer_token');
    if (!token) {
      router.push('/login');
      return;
    }
    setIsCheckingAuth(false);
  }, [router]);

  useEffect(() => {
    // Wait for preferences to load, then check if onboarding is complete
    if (!loading && !error && !isCheckingAuth) {
      if (!isOnboardingComplete()) {
        router.push('/onboard');
      }
    }
  }, [loading, error, isCheckingAuth, isOnboardingComplete, router]);

  // Show loading screen while checking authentication or loading preferences
  if (isCheckingAuth || loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen space-y-4">
        <Card className="w-[350px] bg-background/60 backdrop-blur-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xl font-medium">Loading Dashboard</CardTitle>
            <CardDescription>Checking your configuration...</CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center py-6">
            <Loader2 className="h-12 w-12 text-primary animate-spin" />
          </CardContent>
        </Card>
      </div>
    );
  }

  // Show error screen if there's an error loading preferences
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen space-y-4">
        <Card className="w-[400px] bg-background/60 backdrop-blur-sm border-destructive/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-xl font-medium text-destructive">Configuration Error</CardTitle>
            <CardDescription>Failed to load your LLM configuration</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Only render children if onboarding is complete
  if (isOnboardingComplete()) {
    return <>{children}</>;
  }

  // This should not be reached due to redirect, but just in case
  return (
    <div className="flex flex-col items-center justify-center min-h-screen space-y-4">
      <Card className="w-[350px] bg-background/60 backdrop-blur-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl font-medium">Redirecting...</CardTitle>
          <CardDescription>Taking you to complete your setup</CardDescription>
        </CardHeader>
        <CardContent className="flex justify-center py-6">
          <Loader2 className="h-12 w-12 text-primary animate-spin" />
        </CardContent>
      </Card>
    </div>
  );
} 