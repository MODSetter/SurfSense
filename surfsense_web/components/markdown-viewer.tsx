import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import { Citation } from "./chat/Citation";
import { Source } from "./chat/types";

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
        const isInline = !match;
        return isInline 
          ? <code className="bg-muted px-1 py-0.5 rounded text-xs" {...props}>{children}</code>
          : (
            <div className="relative my-4">
              <pre className="bg-muted p-4 rounded-md overflow-x-auto">
                <code className="text-xs" {...props}>{children}</code>
              </pre>
            </div>
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