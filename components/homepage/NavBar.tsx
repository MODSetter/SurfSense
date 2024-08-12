"use client";
import React, { useState } from "react";
import { HoveredLink, Menu, MenuItem, ProductItem } from "../ui/navbar-menu";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "./theme-toggle";
import Image from "next/image";
import logo from "../../public/SurfSense.png"
import Link from "next/link";

export function MainNavbar() {
    return (
        <div className="relative w-full flex items-center justify-around">
            <Navbar className="top-2 px-2" />
        </div>
    );
}

function Navbar({ className }: { className?: string }) {
    const [active, setActive] = useState<string | null>(null);
    return (
        <div
            className={cn("fixed top-10 inset-x-0 max-w-7xl mx-auto z-50", className)}
        >
            <Menu setActive={setActive}>
                <Link href={"/"} className="flex items-center text-2xl font-semibold text-gray-900 dark:text-white">
                    <Image className="hidden sm:block w-8 h-8 mr-2" src={logo} alt="logo" />
                    <span className="hidden md:block">SurfSense</span>
                </Link>

                <div className="flex gap-2">
                    <Link href={"/login"}>
                        <button className="px-4 py-2 rounded-md border border-black bg-white text-black text-sm hover:shadow-[4px_4px_0px_0px_rgba(0,0,0)] transition duration-200">
                            Log In
                        </button>
                    </Link>

                    <Link href={"/signup"}>
                        <button className="px-4 py-2 rounded-md border border-black bg-white text-black text-sm hover:shadow-[4px_4px_0px_0px_rgba(0,0,0)] transition duration-200">
                            Sign Up
                        </button>
                    </Link>

                    <Link href={"/settings"}>
                        <button className="px-4 py-2 rounded-md border border-black bg-white text-black text-sm hover:shadow-[4px_4px_0px_0px_rgba(0,0,0)] transition duration-200">
                            Settings
                        </button>
                    </Link>

                    <Link href={"/chat"} className="grow">
                        <button className="px-4 py-2 rounded-md border border-black bg-white text-black text-sm hover:shadow-[4px_4px_0px_0px_rgba(0,0,0)] transition duration-200">
                            🧠
                        </button>
                    </Link>



                    <ThemeToggle />
                </div>

            </Menu>
        </div>
    );
}