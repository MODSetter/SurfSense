"use client";

import dynamic from "next/dynamic";

// Dynamically import BlockNote editor with SSR disabled
export const BlockNoteEditor = dynamic(() => import("./BlockNoteEditor"), { ssr: false });
