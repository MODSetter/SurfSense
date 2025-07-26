"use client";

import React, { useState, useEffect } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import {
  oneLight,
  oneDark,
} from "react-syntax-highlighter/dist/cjs/styles/prism";
import { Check, Copy } from "lucide-react";
import { useTheme } from "next-themes";

// Code block component with syntax highlighting and copy functionality
export const CodeBlock = ({
  children,
  language,
}: {
  children: string;
  language: string;
}) => {
  const [copied, setCopied] = useState(false);
  const { resolvedTheme, theme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Prevent hydration issues
  useEffect(() => {
    setMounted(true);
  }, []);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(children);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Choose theme based on current system/user preference
  const isDarkTheme = mounted && (resolvedTheme === "dark" || theme === "dark");
  const syntaxTheme = isDarkTheme ? oneDark : oneLight;

  return (
    <div className="relative my-4 group">
      <div className="absolute right-2 top-2 z-10">
        <button
          onClick={handleCopy}
          className="p-1.5 rounded-md bg-background/80 hover:bg-background border border-border flex items-center justify-center transition-colors"
          aria-label="Copy code"
        >
          {copied ? (
            <Check size={14} className="text-green-500" />
          ) : (
            <Copy size={14} className="text-muted-foreground" />
          )}
        </button>
      </div>
      {mounted ? (
        <SyntaxHighlighter
          language={language || "text"}
          style={{
            ...syntaxTheme,
            'pre[class*="language-"]': {
              ...syntaxTheme['pre[class*="language-"]'],
              margin: 0,
              border: "none",
              borderRadius: "0.375rem",
              background: "var(--syntax-bg)",
            },
            'code[class*="language-"]': {
              ...syntaxTheme['code[class*="language-"]'],
              border: "none",
              background: "var(--syntax-bg)",
            },
          }}
          customStyle={{
            margin: 0,
            borderRadius: "0.375rem",
            fontSize: "0.75rem",
            lineHeight: "1.5rem",
            backgroundColor: "var(--syntax-bg)",
            border: "none",
          }}
          codeTagProps={{
            className: "font-mono",
            style: {
              border: "none",
              background: "var(--syntax-bg)",
            },
          }}
          showLineNumbers={false}
          wrapLines={false}
          lineProps={{
            style: {
              wordBreak: "break-all",
              whiteSpace: "pre-wrap",
              border: "none",
              borderBottom: "none",
              paddingLeft: 0,
              paddingRight: 0,
              margin: "0.25rem 0",
            },
          }}
          PreTag="div"
        >
          {children}
        </SyntaxHighlighter>
      ) : (
        <div className="bg-muted p-4 rounded-md">
          <pre className="m-0 p-0 border-0">
            <code className="text-xs font-mono border-0 leading-6">
              {children}
            </code>
          </pre>
        </div>
      )}
    </div>
  );
};

// Create language renderer function
const createLanguageRenderer = (lang: string) => 
  ({ code }: { code: string }) => (
    <CodeBlock language={lang}>{code}</CodeBlock>
  );

// Define language renderers for common programming languages
export const languageRenderers = {
  "javascript": createLanguageRenderer("javascript"),
  "typescript": createLanguageRenderer("typescript"),
  "python": createLanguageRenderer("python"),
  "java": createLanguageRenderer("java"),
  "csharp": createLanguageRenderer("csharp"),
  "cpp": createLanguageRenderer("cpp"),
  "c": createLanguageRenderer("c"),
  "php": createLanguageRenderer("php"),
  "ruby": createLanguageRenderer("ruby"),
  "go": createLanguageRenderer("go"),
  "rust": createLanguageRenderer("rust"),
  "swift": createLanguageRenderer("swift"),
  "kotlin": createLanguageRenderer("kotlin"),
  "scala": createLanguageRenderer("scala"),
  "sql": createLanguageRenderer("sql"),
  "json": createLanguageRenderer("json"),
  "xml": createLanguageRenderer("xml"),
  "yaml": createLanguageRenderer("yaml"),
  "bash": createLanguageRenderer("bash"),
  "shell": createLanguageRenderer("shell"),
  "powershell": createLanguageRenderer("powershell"),
  "dockerfile": createLanguageRenderer("dockerfile"),
  "html": createLanguageRenderer("html"),
  "css": createLanguageRenderer("css"),
  "scss": createLanguageRenderer("scss"),
  "less": createLanguageRenderer("less"),
  "markdown": createLanguageRenderer("markdown"),
  "text": createLanguageRenderer("text"),
}; 