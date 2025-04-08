"use client";
import Link from "next/link";
import React from "react";
import Image from "next/image";
import { cn } from "@/lib/utils";

export const Logo = ({ className }: { className?: string }) => {
  return (
    <Link
      href="/"
    >
      <Image
        src="/icon-128.png"
        className={cn(className)}
        alt="logo"
        width={128}
        height={128}
      />
    </Link>
  );
};

