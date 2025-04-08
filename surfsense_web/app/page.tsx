"use client";
import React from "react";
import { Navbar } from "@/components/Navbar";
import { motion } from "framer-motion";
import { ModernHeroWithGradients } from "@/components/ModernHeroWithGradients";
import { Footer } from "@/components/Footer";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white">
      <Navbar />
      <ModernHeroWithGradients />
      <Footer />
    </main>
  );
} 