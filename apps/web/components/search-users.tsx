"use client";
import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "./ui/skeleton";
import { Input } from "@/components/ui/input";
import { UsersService, UserSearchResults } from "@/lib/api/client";

const searchOnFields = ["id", "email", "forename", "surname"];

const FormSchema = z.object({
  keyword: z.string().optional(),
  searchOn: z.enum(["id", "email", "forename", "surname"]).optional(),
  searchResults: z
    .string()
    .min(1, {
      message: "Must return at least 1 result",
    })
    .optional(),
});

export default function SearchUsers() {
  const [searchResults, setSearchResults] = React.useState<UserSearchResults>({
    results: [],
  });
  const [error, setError] = React.useState(null);
  const [loading, setLoading] = React.useState(false);

  const form = useForm<z.infer<typeof FormSchema>>({
    resolver: zodResolver(FormSchema),
    defaultValues: {
      keyword: ".com",
      searchOn: "email",
      searchResults: "10",
    },
  });

  const onSubmit = async (data: z.infer<typeof FormSchema>) => {
    console.log(data);
    try {
      setLoading(true); // set loading state
      setError(null); // clear error state if it exists
      const maxResults = data.searchResults ? parseInt(data.searchResults) : 10;
      const response = await UsersService.usersSearchUsers({
        keyword: data.keyword,
        searchOn: data.searchOn,
        maxResults: maxResults,
      });
      setLoading(false);
      console.log(response);
      setSearchResults(response);
      setError(null);
    } catch (error) {
      console.log("Error received", error);
      setLoading(false);
      setSearchResults({ results: [] });
      setError(error);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Form {...form}>
        <Card>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <CardHeader>
              <CardTitle>FastAPI data</CardTitle>
              <CardDescription>
                Data coming from FastAPI backend
              </CardDescription>
            </CardHeader>

            <CardContent>
              <div className="flex flex-col md:flex-row gap-8 w-full">
                <FormField
                  control={form.control}
                  name="keyword"
                  render={({ field }) => (
                    <FormItem className="w-full md:w-1/3">
                      <FormLabel>Keyword</FormLabel>
                      <FormControl>
                        <Input
                          className="text-foreground bg-none w-full"
                          placeholder="shadcn"
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>The keyword to search.</FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="searchResults"
                  render={({ field }) => (
                    <FormItem className="w-full md:w-1/3">
                      <FormLabel>Max results</FormLabel>
                      <FormControl>
                        <Input
                          className="text-foreground bg-none w-full"
                          min={1}
                          type="number"
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>
                        Set maximum number of results to return.
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="searchOn"
                  render={({ field }) => (
                    <FormItem className="w-full md:w-1/3">
                      <FormLabel>Search field</FormLabel>
                      <FormControl>
                        <RadioGroup
                          defaultValue="email"
                          onValueChange={field.onChange}
                          className="grid grid-cols-2 gap-x-8 w-full text-foreground"
                        >
                          {searchOnFields.map((item) => (
                            <FormItem
                              key={item}
                              className="flex space-x-1 space-y-0 "
                            >
                              <FormControl>
                                <RadioGroupItem value={item} />
                              </FormControl>
                              <FormLabel className="font-normal">
                                {item.charAt(0).toUpperCase() + item.slice(1)}
                              </FormLabel>
                            </FormItem>
                          ))}
                        </RadioGroup>
                      </FormControl>
                      <FormDescription>The field to search on.</FormDescription>
                    </FormItem>
                  )}
                />
              </div>
            </CardContent>
            <CardFooter>
              <div className="flex flex-row gap-4 w-full my-4">
                <Button className="min-w-24" type="submit">
                  Submit
                </Button>
                <Button
                  className="min-w-24"
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    form.reset();
                    setError(null); // clear error state
                  }}
                >
                  Reset form
                </Button>
              </div>
            </CardFooter>
          </form>
        </Card>
      </Form>

      {loading ? (
        <Skeleton className="bg-foreground/10 text-foreground p-5 rounded-lg" />
      ) : null}

      {searchResults.results.length >= 1 ? (
        // Render the results if searchResults is set
        <div className="bg-foreground/10 text-foreground p-5 rounded-lg max-h-80 overflow-y-auto">
          {/* Replace this with your code to render the results */}
          <pre>{JSON.stringify(searchResults, null, 2)}</pre>
        </div>
      ) : null}

      {/* This can be handled better to understand what type of error is occurring rather than just a blanket handler */}
      {error ? (
        <div>
          Couldn't find any results that match your criteria. Please try again.
        </div>
      ) : null}
    </div>
  );
}
