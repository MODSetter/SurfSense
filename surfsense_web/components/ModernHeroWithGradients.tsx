"use client";
import { cn } from "@/lib/utils";
import { IconArrowRight, IconBrandGithub } from "@tabler/icons-react";
import Link from "next/link";
import React from "react";
import { motion } from "framer-motion";
import { Logo } from "./Logo";

export function ModernHeroWithGradients() {
    return (
        <div className="relative h-full min-h-[50rem] w-full bg-gray-50 dark:bg-black">
            <div className="relative z-20 mx-auto w-full px-4 py-6 md:px-8 lg:px-4">
                <div className="relative my-12 overflow-hidden rounded-3xl bg-white py-16 shadow-sm dark:bg-gray-900/80 dark:shadow-lg dark:shadow-purple-900/10 md:py-48 mx-auto w-full max-w-[95%] xl:max-w-[98%]">
                    <TopLines />
                    <BottomLines />
                    <SideLines />
                    <TopGradient />
                    <BottomGradient />
                    <DarkModeGradient />

                    <div className="relative z-20 flex flex-col items-center justify-center overflow-hidden rounded-3xl p-4 md:p-12 lg:p-16">
                        <Link
                            href="https://github.com/MODSetter/SurfSense"
                            className="flex items-center gap-1 rounded-full border border-gray-200 bg-gradient-to-b from-gray-50 to-gray-100 px-4 py-1 text-center text-sm text-gray-800 shadow-sm dark:border-[#404040] dark:bg-gradient-to-b dark:from-[#5B5B5D] dark:to-[#262627] dark:text-white dark:shadow-inner dark:shadow-purple-500/10"
                        >
                            <span>SurfSense v0.0.6 Released</span>
                            <IconArrowRight className="h-4 w-4 text-gray-800 dark:text-white" />
                        </Link>
                        {/* Import the Logo component or define it in this file */}
                        <div className="flex items-center justify-center gap-4 mt-10 mb-2">
                            <div className="h-16 w-16">
                                <Logo className="rounded-md" />
                            </div>
                            <h1 className="bg-gradient-to-b from-gray-800 to-gray-600 bg-clip-text py-4 text-center text-3xl text-transparent dark:from-white dark:to-purple-300 md:text-5xl lg:text-8xl">
                                SurfSense
                            </h1>
                        </div>
                        <p className="mx-auto max-w-3xl py-6 text-center text-base text-gray-600 dark:text-neutral-300 md:text-lg lg:text-xl">
                            A Customizable AI Research Agent just like NotebookLM or Perplexity, but connected to external sources such as search engines (Tavily), Slack, Notion, and more.
                        </p>
                        <div className="flex flex-col items-center gap-6 py-6 sm:flex-row">
                            <Link
                                href="/login"
                                className="w-48 gap-1 rounded-full border border-gray-200 bg-gradient-to-b from-gray-50 to-gray-100 px-5 py-3 text-center text-sm font-medium text-gray-800 shadow-sm dark:border-[#404040] dark:bg-gradient-to-b dark:from-[#5B5B5D] dark:to-[#262627] dark:text-white dark:shadow-inner dark:shadow-purple-500/10"
                            >
                                Get Started
                            </Link>
                            <Link
                                href="https://github.com/MODSetter/SurfSense"
                                className="w-48 gap-1 rounded-full border border-transparent bg-gray-800 px-5 py-3 text-center text-sm font-medium text-white shadow-sm hover:bg-gray-700 dark:bg-gradient-to-r dark:from-purple-700 dark:to-indigo-800 dark:text-white dark:hover:from-purple-600 dark:hover:to-indigo-700 flex items-center justify-center"
                            >
                                <IconBrandGithub className="h-5 w-5 mr-2" />
                                <span>GitHub</span>
                            </Link>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

const TopLines = () => {
    return (
        <svg
            width="166"
            height="298"
            viewBox="0 0 166 298"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="aspect-square pointer-events-none absolute inset-x-0 top-0 h-[100px] w-full md:h-[200px]"
        >
            <line
                y1="-0.5"
                x2="406"
                y2="-0.5"
                transform="matrix(0 1 1 0 1 -108)"
                stroke="url(#paint0_linear_254_143)"
            />
            <line
                y1="-0.5"
                x2="406"
                y2="-0.5"
                transform="matrix(0 1 1 0 34 -108)"
                stroke="url(#paint1_linear_254_143)"
            />
            <line
                y1="-0.5"
                x2="406"
                y2="-0.5"
                transform="matrix(0 1 1 0 67 -108)"
                stroke="url(#paint2_linear_254_143)"
            />
            <line
                y1="-0.5"
                x2="406"
                y2="-0.5"
                transform="matrix(0 1 1 0 100 -108)"
                stroke="url(#paint3_linear_254_143)"
            />
            <line
                y1="-0.5"
                x2="406"
                y2="-0.5"
                transform="matrix(0 1 1 0 133 -108)"
                stroke="url(#paint4_linear_254_143)"
            />
            <line
                y1="-0.5"
                x2="406"
                y2="-0.5"
                transform="matrix(0 1 1 0 166 -108)"
                stroke="url(#paint5_linear_254_143)"
            />
            <defs>
                <linearGradient
                    id="paint0_linear_254_143"
                    x1="-7.42412e-06"
                    y1="0.500009"
                    x2="405"
                    y2="0.500009"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop stopColor="gray" className="dark:stop-color-white" />
                    <stop offset="1" stopOpacity="0" />
                </linearGradient>
                <linearGradient
                    id="paint1_linear_254_143"
                    x1="-7.42412e-06"
                    y1="0.500009"
                    x2="405"
                    y2="0.500009"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop stopColor="gray" className="dark:stop-color-white" />
                    <stop offset="1" stopOpacity="0" />
                </linearGradient>
                <linearGradient
                    id="paint2_linear_254_143"
                    x1="-7.42412e-06"
                    y1="0.500009"
                    x2="405"
                    y2="0.500009"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop stopColor="gray" className="dark:stop-color-white" />
                    <stop offset="1" stopOpacity="0" />
                </linearGradient>
                <linearGradient
                    id="paint3_linear_254_143"
                    x1="-7.42412e-06"
                    y1="0.500009"
                    x2="405"
                    y2="0.500009"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop stopColor="gray" className="dark:stop-color-white" />
                    <stop offset="1" stopOpacity="0" />
                </linearGradient>
                <linearGradient
                    id="paint4_linear_254_143"
                    x1="-7.42412e-06"
                    y1="0.500009"
                    x2="405"
                    y2="0.500009"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop stopColor="gray" className="dark:stop-color-white" />
                    <stop offset="1" stopOpacity="0" />
                </linearGradient>
                <linearGradient
                    id="paint5_linear_254_143"
                    x1="-7.42412e-06"
                    y1="0.500009"
                    x2="405"
                    y2="0.500009"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop stopColor="gray" className="dark:stop-color-white" />
                    <stop offset="1" stopOpacity="0" />
                </linearGradient>
            </defs>
        </svg>
    );
};

const BottomLines = () => {
    return (
        <svg
            width="445"
            height="418"
            viewBox="0 0 445 418"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="aspect-square pointer-events-none absolute inset-x-0 -bottom-20 z-20 h-[150px] w-full md:h-[300px]"
        >
            <line
                x1="139.5"
                y1="418"
                x2="139.5"
                y2="12"
                stroke="url(#paint0_linear_0_1)"
            />
            <line
                x1="172.5"
                y1="418"
                x2="172.5"
                y2="12"
                stroke="url(#paint1_linear_0_1)"
            />
            <line
                x1="205.5"
                y1="418"
                x2="205.5"
                y2="12"
                stroke="url(#paint2_linear_0_1)"
            />
            <line
                x1="238.5"
                y1="418"
                x2="238.5"
                y2="12"
                stroke="url(#paint3_linear_0_1)"
            />
            <line
                x1="271.5"
                y1="418"
                x2="271.5"
                y2="12"
                stroke="url(#paint4_linear_0_1)"
            />
            <line
                x1="304.5"
                y1="418"
                x2="304.5"
                y2="12"
                stroke="url(#paint5_linear_0_1)"
            />
            <path
                d="M1 149L109.028 235.894C112.804 238.931 115 243.515 115 248.361V417"
                stroke="url(#paint6_linear_0_1)"
                strokeOpacity="0.1"
                strokeWidth="1.5"
            />
            <path
                d="M444 149L335.972 235.894C332.196 238.931 330 243.515 330 248.361V417"
                stroke="url(#paint7_linear_0_1)"
                strokeOpacity="0.1"
                strokeWidth="1.5"
            />
            <defs>
                <linearGradient
                    id="paint0_linear_0_1"
                    x1="140.5"
                    y1="418"
                    x2="140.5"
                    y2="13"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop stopColor="gray" className="dark:stop-color-white" />
                    <stop offset="1" stopOpacity="0" />
                </linearGradient>
                <linearGradient
                    id="paint1_linear_0_1"
                    x1="173.5"
                    y1="418"
                    x2="173.5"
                    y2="13"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop stopColor="gray" className="dark:stop-color-white" />
                    <stop offset="1" stopOpacity="0" />
                </linearGradient>
                <linearGradient
                    id="paint2_linear_0_1"
                    x1="206.5"
                    y1="418"
                    x2="206.5"
                    y2="13"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop stopColor="gray" className="dark:stop-color-white" />
                    <stop offset="1" stopOpacity="0" />
                </linearGradient>
                <linearGradient
                    id="paint3_linear_0_1"
                    x1="239.5"
                    y1="418"
                    x2="239.5"
                    y2="13"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop stopColor="gray" className="dark:stop-color-white" />
                    <stop offset="1" stopOpacity="0" />
                </linearGradient>
                <linearGradient
                    id="paint4_linear_0_1"
                    x1="272.5"
                    y1="418"
                    x2="272.5"
                    y2="13"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop stopColor="gray" className="dark:stop-color-white" />
                    <stop offset="1" stopOpacity="0" />
                </linearGradient>
                <linearGradient
                    id="paint5_linear_0_1"
                    x1="305.5"
                    y1="418"
                    x2="305.5"
                    y2="13"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop stopColor="gray" className="dark:stop-color-white" />
                    <stop offset="1" stopOpacity="0" />
                </linearGradient>
                <linearGradient
                    id="paint6_linear_0_1"
                    x1="115"
                    y1="390.591"
                    x2="-59.1703"
                    y2="205.673"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop offset="0.481613" stopColor="#E8E8E8" className="dark:stop-color-[#F8F8F8]" />
                    <stop offset="1" stopColor="#E8E8E8" stopOpacity="0" className="dark:stop-color-[#F8F8F8]" />
                </linearGradient>
                <linearGradient
                    id="paint7_linear_0_1"
                    x1="330"
                    y1="390.591"
                    x2="504.17"
                    y2="205.673"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop offset="0.481613" stopColor="#E8E8E8" className="dark:stop-color-[#F8F8F8]" />
                    <stop offset="1" stopColor="#E8E8E8" stopOpacity="0" className="dark:stop-color-[#F8F8F8]" />
                </linearGradient>
            </defs>
        </svg>
    );
};

const SideLines = () => {
    return (
        <svg
            width="1382"
            height="370"
            viewBox="0 0 1382 370"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="pointer-events-none absolute inset-0 z-30 h-full w-full"
        >
            <path
                d="M268 115L181.106 6.97176C178.069 3.19599 173.485 1 168.639 1H0"
                stroke="url(#paint0_linear_337_46)"
                strokeOpacity="0.1"
                strokeWidth="1.5"
            />
            <path
                d="M1114 115L1200.89 6.97176C1203.93 3.19599 1208.52 1 1213.36 1H1382"
                stroke="url(#paint1_linear_337_46)"
                strokeOpacity="0.1"
                strokeWidth="1.5"
            />
            <path
                d="M268 255L181.106 363.028C178.069 366.804 173.485 369 168.639 369H0"
                stroke="url(#paint2_linear_337_46)"
                strokeOpacity="0.1"
                strokeWidth="1.5"
            />
            <path
                d="M1114 255L1200.89 363.028C1203.93 366.804 1208.52 369 1213.36 369H1382"
                stroke="url(#paint3_linear_337_46)"
                strokeOpacity="0.1"
                strokeWidth="1.5"
            />
            <defs>
                <linearGradient
                    id="paint0_linear_337_46"
                    x1="26.4087"
                    y1="1.00001"
                    x2="211.327"
                    y2="175.17"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop offset="0.481613" stopColor="#E8E8E8" className="dark:stop-color-[#F8F8F8]" />
                    <stop offset="1" stopColor="#E8E8E8" stopOpacity="0" className="dark:stop-color-[#F8F8F8]" />
                </linearGradient>
                <linearGradient
                    id="paint1_linear_337_46"
                    x1="1355.59"
                    y1="1.00001"
                    x2="1170.67"
                    y2="175.17"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop offset="0.481613" stopColor="#E8E8E8" className="dark:stop-color-[#F8F8F8]" />
                    <stop offset="1" stopColor="#E8E8E8" stopOpacity="0" className="dark:stop-color-[#F8F8F8]" />
                </linearGradient>
                <linearGradient
                    id="paint2_linear_337_46"
                    x1="26.4087"
                    y1="369"
                    x2="211.327"
                    y2="194.83"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop offset="0.481613" stopColor="#E8E8E8" className="dark:stop-color-[#F8F8F8]" />
                    <stop offset="1" stopColor="#E8E8E8" stopOpacity="0" className="dark:stop-color-[#F8F8F8]" />
                </linearGradient>
                <linearGradient
                    id="paint3_linear_337_46"
                    x1="1355.59"
                    y1="369"
                    x2="1170.67"
                    y2="194.83"
                    gradientUnits="userSpaceOnUse"
                >
                    <stop offset="0.481613" stopColor="#E8E8E8" className="dark:stop-color-[#F8F8F8]" />
                    <stop offset="1" stopColor="#E8E8E8" stopOpacity="0" className="dark:stop-color-[#F8F8F8]" />
                </linearGradient>
            </defs>
        </svg>
    );
};

const BottomGradient = ({ className }: { className?: string }) => {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="851"
            height="595"
            viewBox="0 0 851 595"
            fill="none"
            className={cn(
                "pointer-events-none absolute -right-80 bottom-0 h-full w-full opacity-30 dark:opacity-100 dark:hidden",
                className,
            )}
        >
            <path
                d="M118.499 0H532.468L635.375 38.6161L665 194.625L562.093 346H0L24.9473 121.254L118.499 0Z"
                fill="url(#paint0_radial_254_132)"
            />
            <defs>
                <radialGradient
                    id="paint0_radial_254_132"
                    cx="0"
                    cy="0"
                    r="1"
                    gradientUnits="userSpaceOnUse"
                    gradientTransform="translate(412.5 346) rotate(-91.153) scale(397.581 423.744)"
                >
                    <stop stopColor="#AAD3E9" />
                    <stop offset="0.25" stopColor="#7FB8D4" />
                    <stop offset="0.573634" stopColor="#5A9BB8" />
                    <stop offset="1" stopOpacity="0" />
                </radialGradient>
            </defs>
        </svg>
    );
};

const TopGradient = ({ className }: { className?: string }) => {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="1007"
            height="997"
            viewBox="0 0 1007 997"
            fill="none"
            className={cn(
                "pointer-events-none absolute -left-96 top-0 h-full w-full opacity-30 dark:opacity-100 dark:hidden",
                className,
            )}
        >
            <path
                d="M807 110.119L699.5 -117.546L8.5 -154L-141 246.994L-7 952L127 782.111L279 652.114L513 453.337L807 110.119Z"
                fill="url(#paint0_radial_254_135)"
            />
            <path
                d="M807 110.119L699.5 -117.546L8.5 -154L-141 246.994L-7 952L127 782.111L279 652.114L513 453.337L807 110.119Z"
                fill="url(#paint1_radial_254_135)"
            />
            <defs>
                <radialGradient
                    id="paint0_radial_254_135"
                    cx="0"
                    cy="0"
                    r="1"
                    gradientUnits="userSpaceOnUse"
                    gradientTransform="translate(77.0001 15.8894) rotate(90.3625) scale(869.41 413.353)"
                >
                    <stop stopColor="#AAD3E9" />
                    <stop offset="0.25" stopColor="#7FB8D4" />
                    <stop offset="0.573634" stopColor="#5A9BB8" />
                    <stop offset="1" stopOpacity="0" />
                </radialGradient>
                <radialGradient
                    id="paint1_radial_254_135"
                    cx="0"
                    cy="0"
                    r="1"
                    gradientUnits="userSpaceOnUse"
                    gradientTransform="translate(127.5 -31) rotate(1.98106) scale(679.906 715.987)"
                >
                    <stop stopColor="#AAD3E9" />
                    <stop offset="0.283363" stopColor="#7FB8D4" />
                    <stop offset="0.573634" stopColor="#5A9BB8" />
                    <stop offset="1" stopOpacity="0" />
                </radialGradient>
            </defs>
        </svg>
    );
};

const DarkModeGradient = ({ className }: { className?: string } = {}) => {
    return (
        <div className="hidden dark:block">
            <div className="absolute -left-48 -top-48 h-[800px] w-[800px] rounded-full bg-purple-900/20 blur-[180px]"></div>
            <div className="absolute -right-48 -bottom-48 h-[800px] w-[800px] rounded-full bg-indigo-900/20 blur-[180px]"></div>
            <div className="absolute left-1/2 top-1/2 h-[400px] w-[400px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-purple-800/10 blur-[120px]"></div>
        </div>
    );
}; 