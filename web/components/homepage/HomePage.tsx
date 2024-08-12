"use client";

import { motion } from "framer-motion";
import React from "react";
import { AuroraBackground } from "../ui/aurora-background";

import icon from "../../public/SurfSense.png"
import Image from "next/image";
import Link from "next/link";

export function HomePage() {
    return (
        <AuroraBackground>
            <motion.div
                initial={{ opacity: 0.0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{
                    delay: 0.3,
                    duration: 0.8,
                    ease: "easeInOut",
                }}
                className="relative flex flex-col gap-4 items-center justify-center px-4"
            >
                <div className="flex items-center mb-4 text-5xl font-semibold text-gray-900 dark:text-white">
                    <Image className="w-64 h-64 rounded-full" src={icon} alt="logo" />
                </div>
                <div className="text-3xl md:text-7xl font-bold dark:text-white text-center">
                    SurfSense 
                </div>
                {/* <div className="text-lg font-semibold dark:text-neutral-200">Beta v0.0.1</div> */}
                <div className="font-extralight text-base md:text-4xl dark:text-neutral-200 py-4">
                    A Knowledge Graph 🧠 Brain 🧠 for World Wide Web Surfers.
                </div>
                <button className="relative inline-flex h-12 overflow-hidden rounded-full p-[1px] focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 focus:ring-offset-slate-50">
                    <span className="absolute inset-[-1000%] animate-[spin_2s_linear_infinite] bg-[conic-gradient(from_90deg_at_50%_50%,#E2CBFF_0%,#393BB2_50%,#E2CBFF_100%)]" />
                    <Link href={'/signup'} className="inline-flex h-full w-full cursor-pointer items-center justify-center rounded-full bg-slate-950 px-8 py-4 text-2xl font-medium text-white backdrop-blur-3xl">
                        Sign Up
                    </Link>
                </button>
            </motion.div>
        </AuroraBackground>
    );
}
