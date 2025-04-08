"use client";
import React from "react";
import { IconBrandGoogleFilled } from "@tabler/icons-react";
import { motion } from "framer-motion";
import { Logo } from "@/components/Logo";

export function GoogleLoginButton() {
  const handleGoogleLogin = () => {
    // Redirect to Google OAuth authorization URL
    fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/auth/google/authorize`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to get authorization URL');
        }
        return response.json();
      })
      .then((data) => {
        if (data.authorization_url) {
          window.location.href = data.authorization_url;
        } else {
          console.error('No authorization URL received');
        }
      })
      .catch((error) => {
        console.error('Error during Google login:', error);
      });
  }
  return (
    <div className="relative w-full overflow-hidden">
      <AmbientBackground />
      <div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center">
        <Logo className="rounded-md" />
        <h1 className="my-8 text-xl font-bold text-neutral-800 dark:text-neutral-100 md:text-4xl">
          Welcome Back
        </h1>
        
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="group/btn relative flex w-full items-center justify-center space-x-2 rounded-lg bg-white px-6 py-4 text-neutral-700 shadow-lg transition-all duration-200 hover:shadow-xl dark:bg-neutral-800 dark:text-neutral-200"
          onClick={handleGoogleLogin}
        >
          <div className="absolute inset-0 h-full w-full transform opacity-0 transition duration-200 group-hover/btn:opacity-100">
            <div className="absolute -left-px -top-px h-4 w-4 rounded-tl-lg border-l-2 border-t-2 border-blue-500 bg-transparent transition-all duration-200 group-hover/btn:-left-2 group-hover/btn:-top-2"></div>
            <div className="absolute -right-px -top-px h-4 w-4 rounded-tr-lg border-r-2 border-t-2 border-blue-500 bg-transparent transition-all duration-200 group-hover/btn:-right-2 group-hover/btn:-top-2"></div>
            <div className="absolute -bottom-px -left-px h-4 w-4 rounded-bl-lg border-b-2 border-l-2 border-blue-500 bg-transparent transition-all duration-200 group-hover/btn:-bottom-2 group-hover/btn:-left-2"></div>
            <div className="absolute -bottom-px -right-px h-4 w-4 rounded-br-lg border-b-2 border-r-2 border-blue-500 bg-transparent transition-all duration-200 group-hover/btn:-bottom-2 group-hover/btn:-right-2"></div>
          </div>
          <IconBrandGoogleFilled className="h-5 w-5 text-neutral-700 dark:text-neutral-200" />
          <span className="text-base font-medium">Continue with Google</span>
        </motion.button>
      </div>
    </div>
  );
}



const AmbientBackground = () => {
  return (
    <div className="pointer-events-none absolute left-0 top-0 z-0 h-screen w-screen">
      <div
        style={{
          transform: "translateY(-350px) rotate(-45deg)",
          width: "560px",
          height: "1380px",
          background:
            "radial-gradient(68.54% 68.72% at 55.02% 31.46%, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.02) 50%, rgba(59, 130, 246, 0) 100%)",
        }}
        className="absolute left-0 top-0"
      />
      <div
        style={{
          transform: "rotate(-45deg) translate(5%, -50%)",
          transformOrigin: "top left",
          width: "240px",
          height: "1380px",
          background:
            "radial-gradient(50% 50% at 50% 50%, rgba(59, 130, 246, 0.06) 0%, rgba(59, 130, 246, 0.02) 80%, transparent 100%)",
        }}
        className="absolute left-0 top-0"
      />
      <div
        style={{
          position: "absolute",
          borderRadius: "20px",
          transform: "rotate(-45deg) translate(-180%, -70%)",
          transformOrigin: "top left",
          width: "240px",
          height: "1380px",
          background:
            "radial-gradient(50% 50% at 50% 50%, rgba(59, 130, 246, 0.04) 0%, rgba(59, 130, 246, 0.02) 80%, transparent 100%)",
        }}
        className="absolute left-0 top-0"
      />
    </div>
  );
}; 