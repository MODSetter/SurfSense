"use client";

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Tag, TagInput } from "emblor";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import { Globe, Loader2 } from "lucide-react";

// URL validation regex
const urlRegex = /^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*\/?$/;

export default function WebpageCrawler() {
  const params = useParams();
  const router = useRouter();
  const search_space_id = params.search_space_id as string;
  
  const [urlTags, setUrlTags] = useState<Tag[]>([]);
  const [activeTagIndex, setActiveTagIndex] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Function to validate a URL
  const isValidUrl = (url: string): boolean => {
    return urlRegex.test(url);
  };

  // Function to handle URL submission
  const handleSubmit = async () => {
    // Validate that we have at least one URL
    if (urlTags.length === 0) {
      setError("Please add at least one URL");
      return;
    }

    // Validate all URLs
    const invalidUrls = urlTags.filter(tag => !isValidUrl(tag.text));
    if (invalidUrls.length > 0) {
      setError(`Invalid URLs detected: ${invalidUrls.map(tag => tag.text).join(', ')}`);
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      toast("URL Crawling", {
        description: "Starting URL crawling process...",
      });

      // Extract URLs from tags
      const urls = urlTags.map(tag => tag.text);

      // Make API call to backend
      const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/documents/`, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem("surfsense_bearer_token")}`
        },
        body: JSON.stringify({
          "document_type": "CRAWLED_URL",
          "content": urls,
          "search_space_id": parseInt(search_space_id)
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to crawl URLs");
      }

      await response.json();

      toast("Crawling Successful", {
        description: "URLs have been submitted for crawling",
      });

      // Redirect to documents page
      router.push(`/dashboard/${search_space_id}/documents`);
    } catch (error: any) {
      setError(error.message || "An error occurred while crawling URLs");
      toast("Crawling Error", {
        description: `Error crawling URLs: ${error.message}`,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Function to add a new URL tag
  const handleAddTag = (text: string) => {
    // Basic URL validation
    if (!isValidUrl(text)) {
      toast("Invalid URL", {
        description: "Please enter a valid URL",
      });
      return;
    }

    // Check for duplicates
    if (urlTags.some(tag => tag.text === text)) {
      toast("Duplicate URL", {
        description: "This URL has already been added",
      });
      return;
    }

    // Add the new tag
    const newTag: Tag = {
      id: Date.now().toString(),
      text: text,
    };

    setUrlTags([...urlTags, newTag]);
  };

  return (
    <div className="container mx-auto py-8">
      <Card className="max-w-2xl mx-auto">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Add Webpages for Crawling
          </CardTitle>
          <CardDescription>
            Enter URLs to crawl and add to your document collection
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="url-input">Enter URLs to crawl</Label>
              <TagInput
                id="url-input"
                tags={urlTags}
                setTags={setUrlTags}
                placeholder="Enter a URL and press Enter"
                onAddTag={handleAddTag}
                styleClasses={{
                  inlineTagsContainer:
                    "border-input rounded-lg bg-background shadow-sm shadow-black/5 transition-shadow focus-within:border-ring focus-within:outline-none focus-within:ring-[3px] focus-within:ring-ring/20 p-1 gap-1",
                  input: "w-full min-w-[80px] focus-visible:outline-none shadow-none px-2 h-7",
                  tag: {
                    body: "h-7 relative bg-background border border-input hover:bg-background rounded-md font-medium text-xs ps-2 pe-7 flex",
                    closeButton:
                      "absolute -inset-y-px -end-px p-0 rounded-e-lg flex size-7 transition-colors outline-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring/70 text-muted-foreground/80 hover:text-foreground",
                  },
                }}
                activeTagIndex={activeTagIndex}
                setActiveTagIndex={setActiveTagIndex}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Add multiple URLs by pressing Enter after each one
              </p>
            </div>

            {error && (
              <div className="text-sm text-red-500 mt-2">
                {error}
              </div>
            )}

            <div className="bg-muted/50 rounded-lg p-4 text-sm">
              <h4 className="font-medium mb-2">Tips for URL crawling:</h4>
              <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
                <li>Enter complete URLs including http:// or https://</li>
                <li>Make sure the websites allow crawling</li>
                <li>Public webpages work best</li>
                <li>Crawling may take some time depending on the website size</li>
              </ul>
            </div>
          </div>
        </CardContent>
        <CardFooter className="flex justify-between">
          <Button 
            variant="outline" 
            onClick={() => router.push(`/dashboard/${search_space_id}/documents`)}
          >
            Cancel
          </Button>
          <Button 
            onClick={handleSubmit} 
            disabled={isSubmitting || urlTags.length === 0}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Submitting...
              </>
            ) : (
              'Submit URLs for Crawling'
            )}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}