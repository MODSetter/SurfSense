import React, { useMemo, useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import { Citation } from "./chat/Citation";
import { Source } from "./chat/types";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight, oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { Check, Copy } from "lucide-react";
import { useTheme } from "next-themes";

interface MarkdownViewerProps {
  content: string;
  className?: string;
  getCitationSource?: (id: number) => Source | null;
}

export function MarkdownViewer({ content, className, getCitationSource }: MarkdownViewerProps) {
  // Memoize the markdown components to prevent unnecessary re-renders
  const components = useMemo(() => {
    return {
      // Define custom components for markdown elements
      p: ({node, children, ...props}: any) => {
        // If there's no getCitationSource function, just render normally
        if (!getCitationSource) {
          return <p className="my-2" {...props}>{children}</p>;
        }
        
        // Process citations within paragraph content
        return <p className="my-2" {...props}>{processCitationsInReactChildren(children, getCitationSource)}</p>;
      },
      a: ({node, children, ...props}: any) => {
        // Process citations within link content if needed
        const processedChildren = getCitationSource 
          ? processCitationsInReactChildren(children, getCitationSource) 
          : children;
        return <a className="text-primary hover:underline" {...props}>{processedChildren}</a>;
      },
      li: ({node, children, ...props}: any) => {
        // Process citations within list item content
        const processedChildren = getCitationSource 
          ? processCitationsInReactChildren(children, getCitationSource) 
          : children;
        return <li {...props}>{processedChildren}</li>;
      },
      ul: ({node, ...props}: any) => <ul className="list-disc pl-5 my-2" {...props} />,
      ol: ({node, ...props}: any) => <ol className="list-decimal pl-5 my-2" {...props} />,
      h1: ({node, children, ...props}: any) => {
        const processedChildren = getCitationSource 
          ? processCitationsInReactChildren(children, getCitationSource) 
          : children;
        return <h1 className="text-2xl font-bold mt-6 mb-2" {...props}>{processedChildren}</h1>;
      },
      h2: ({node, children, ...props}: any) => {
        const processedChildren = getCitationSource 
          ? processCitationsInReactChildren(children, getCitationSource) 
          : children;
        return <h2 className="text-xl font-bold mt-5 mb-2" {...props}>{processedChildren}</h2>;
      },
      h3: ({node, children, ...props}: any) => {
        const processedChildren = getCitationSource 
          ? processCitationsInReactChildren(children, getCitationSource) 
          : children;
        return <h3 className="text-lg font-bold mt-4 mb-2" {...props}>{processedChildren}</h3>;
      },
      h4: ({node, children, ...props}: any) => {
        const processedChildren = getCitationSource 
          ? processCitationsInReactChildren(children, getCitationSource) 
          : children;
        return <h4 className="text-base font-bold mt-3 mb-1" {...props}>{processedChildren}</h4>;
      },
      blockquote: ({node, ...props}: any) => <blockquote className="border-l-4 border-muted pl-4 italic my-2" {...props} />,
      hr: ({node, ...props}: any) => <hr className="my-4 border-muted" {...props} />,
      img: ({node, ...props}: any) => <img className="max-w-full h-auto my-4 rounded" {...props} />,
      table: ({node, ...props}: any) => <div className="overflow-x-auto my-4"><table className="min-w-full divide-y divide-border" {...props} /></div>,
      th: ({node, ...props}: any) => <th className="px-3 py-2 text-left font-medium bg-muted" {...props} />,
      td: ({node, ...props}: any) => <td className="px-3 py-2 border-t border-border" {...props} />,
      code: ({node, className, children, ...props}: any) => {
        const match = /language-(\w+)/.exec(className || '');
        const language = match ? match[1] : '';
        const isInline = !match;
        
        if (isInline) {
          return <code className="bg-muted px-1 py-0.5 rounded text-xs" {...props}>{children}</code>;
        }
        
        // For code blocks, add syntax highlighting and copy functionality
        return (
          <CodeBlock language={language} {...props}>
            {String(children).replace(/\n$/, '')}
          </CodeBlock>
        );
      }
    };
  }, [getCitationSource]);

  return (
    <div className={cn("prose prose-sm dark:prose-invert max-w-none", className)}>
      <ReactMarkdown
        rehypePlugins={[rehypeRaw, rehypeSanitize]}
        remarkPlugins={[remarkGfm]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

// Code block component with syntax highlighting and copy functionality
const CodeBlock = ({ children, language }: { children: string, language: string }) => {
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
  const isDarkTheme = mounted && (resolvedTheme === 'dark' || theme === 'dark');
  const syntaxTheme = isDarkTheme ? oneDark : oneLight;

  return (
    <div className="relative my-4 group">
      <div className="absolute right-2 top-2 z-10">
        <button
          onClick={handleCopy}
          className="p-1.5 rounded-md bg-background/80 hover:bg-background border border-border flex items-center justify-center transition-colors"
          aria-label="Copy code"
        >
          {copied ? 
            <Check size={14} className="text-green-500" /> : 
            <Copy size={14} className="text-muted-foreground" />
          }
        </button>
      </div>
      {mounted ? (
        <SyntaxHighlighter
          language={language || 'text'}
          style={{
            ...syntaxTheme,
            'pre[class*="language-"]': {
              ...syntaxTheme['pre[class*="language-"]'],
              margin: 0,
              border: 'none',
              borderRadius: '0.375rem',
              background: 'var(--syntax-bg)'
            },
            'code[class*="language-"]': {
              ...syntaxTheme['code[class*="language-"]'],
              border: 'none',
              background: 'var(--syntax-bg)'
            }
          }}
          customStyle={{
            margin: 0,
            borderRadius: '0.375rem',
            fontSize: '0.75rem',
            lineHeight: '1.5rem',
            backgroundColor: 'var(--syntax-bg)',
            border: 'none',
          }}
          codeTagProps={{
            className: "font-mono",
            style: {
              border: 'none',
              background: 'var(--syntax-bg)'
            }
          }}
          showLineNumbers={false}
          wrapLines={false}
          lineProps={{
            style: {
              wordBreak: 'break-all', 
              whiteSpace: 'pre-wrap',
              border: 'none',
              borderBottom: 'none',
              paddingLeft: 0,
              paddingRight: 0,
              margin: '0.25rem 0'
            }
          }}
          PreTag="div"
        >
          {children}
        </SyntaxHighlighter>
      ) : (
        <div className="bg-muted p-4 rounded-md">
          <pre className="m-0 p-0 border-0">
            <code className="text-xs font-mono border-0 leading-6">{children}</code>
          </pre>
        </div>
      )}
    </div>
  );
};

// Helper function to process citations within React children
const processCitationsInReactChildren = (children: React.ReactNode, getCitationSource: (id: number) => Source | null): React.ReactNode => {
  // If children is not an array or string, just return it
  if (!children || (typeof children !== 'string' && !Array.isArray(children))) {
    return children;
  }
  
  // Handle string content directly - this is where we process citation references
  if (typeof children === 'string') {
    return processCitationsInText(children, getCitationSource);
  }
  
  // Handle arrays of children recursively
  if (Array.isArray(children)) {
    return React.Children.map(children, child => {
      if (typeof child === 'string') {
        return processCitationsInText(child, getCitationSource);
      }
      return child;
    });
  }
  
  return children;
};

// Process citation references in text content
const processCitationsInText = (text: string, getCitationSource: (id: number) => Source | null): React.ReactNode[] => {
  // Use improved regex to catch citation numbers more reliably
  // This will match patterns like [1], [42], etc. including when they appear at the end of a line or sentence
  const citationRegex = /\[(\d+)\]/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;
  let position = 0;
  
  while ((match = citationRegex.exec(text)) !== null) {
    // Add text before the citation
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }
    
    // Add the citation component
    const citationId = parseInt(match[1], 10);
    const source = getCitationSource(citationId);
    
    parts.push(
      <Citation 
        key={`citation-${citationId}-${position}`}
        citationId={citationId}
        citationText={match[0]}
        position={position}
        source={source}
      />
    );
    
    lastIndex = match.index + match[0].length;
    position++;
  }
  
  // Add any remaining text after the last citation
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }
  
  return parts;
}; 