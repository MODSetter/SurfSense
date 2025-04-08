import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom"
import icon from "data-base64:~assets/icon.png"
import { convertHtmlToMarkdown } from "dom-to-semantic-markdown";
import type { WebHistory } from "~utils/interfaces";
import { getRenderedHtml } from "~utils/commons";
import Loading from "./Loading";
import brain from "data-base64:~assets/brain.png"
import { Storage } from "@plasmohq/storage"
import { sendToBackground } from "@plasmohq/messaging"
import { Check, ChevronsUpDown } from "lucide-react"
import { cn } from "~/lib/utils"
import { Button } from "~/routes/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "~/routes/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "~/routes/ui/popover"
import { useToast } from "~routes/ui/use-toast";
import {
  CircleIcon,
  CrossCircledIcon,
  DiscIcon,
  ExitIcon,
  FileIcon,
  ReloadIcon,
  ResetIcon,
  UploadIcon
} from "@radix-ui/react-icons"

const HomePage = () => {
  const { toast } = useToast()
  const navigation = useNavigate()
  const [noOfWebPages, setNoOfWebPages] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = React.useState(false)
  const [value, setValue] = React.useState<string>("")
  const [searchspaces, setSearchSpaces] = useState([])
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    const checkSearchSpaces = async () => {
      const storage = new Storage({ area: "local" })
      const token = await storage.get('token');
      try {
        const response = await fetch(
          `${process.env.PLASMO_PUBLIC_BACKEND_URL}/api/v1/searchspaces/`,
          {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          }
        );

        if (!response.ok) {
          throw new Error("Token verification failed");
        } else {
          const res = await response.json()
          console.log(res)
          setSearchSpaces(res)
        }
      } catch (error) {
        await storage.remove('token');
        await storage.remove('showShadowDom');
        navigation("/login")
      }
    };

    checkSearchSpaces();
    setLoading(false);
  }, []);


  useEffect(() => {
    async function onLoad() {
      try {
        chrome.storage.onChanged.addListener(
          (changes: any, areaName: string) => {
            if (changes.webhistory) {
              const webhistory = JSON.parse(changes.webhistory.newValue);
              console.log("webhistory", webhistory)

              let sum = 0
              webhistory.webhistory.forEach((element: any) => {
                sum = sum + element.tabHistory.length
              });

              setNoOfWebPages(sum)
            }
          }
        );

        const storage = new Storage({ area: "local" })
        const searchspace = await storage.get("search_space");

        if(searchspace){
          setValue(searchspace)
        }

        await storage.set("showShadowDom", true)

        const webhistoryObj: any = await storage.get("webhistory");
        if (webhistoryObj.webhistory.length) {
          const webhistory = webhistoryObj.webhistory;

          if (webhistoryObj) {
            let sum = 0
            webhistory.forEach((element: any) => {
              sum = sum + element.tabHistory.length
            });
            setNoOfWebPages(sum)
          }
        } else {
          setNoOfWebPages(0)
        }
      } catch (error) {
        console.log(error);
      }
    }

    onLoad()
  }, []);

  async function clearMem(): Promise<void> {
    try {
      const storage = new Storage({ area: "local" })
  
      let webHistory: any = await storage.get("webhistory");
      let urlQueue: any = await storage.get("urlQueueList");
      let timeQueue: any = await storage.get("timeQueueList");
  
      if (!webHistory.webhistory) {
        return
      }
  
      //Main Cleanup COde
      chrome.tabs.query({}, async (tabs) => {
        //Get Active Tabs Ids
        let actives = tabs.map((tab) => {
          if (tab.id) {
            return tab.id
          }
        })
  
        actives = actives.filter((item: any) => item)
  
        //Only retain which is still active
        const newHistory = webHistory.webhistory.map((element: any) => {
          //@ts-ignore
          if (actives.includes(element.tabsessionId)) {
            return element
          }
        })
  
        const newUrlQueue = urlQueue.urlQueueList.map((element: any) => {
          //@ts-ignore
          if (actives.includes(element.tabsessionId)) {
            return element
          }
        })
  
        const newTimeQueue = timeQueue.timeQueueList.map((element: any) => {
          //@ts-ignore
          if (actives.includes(element.tabsessionId)) {
            return element
          }
        })
  
        await storage.set("webhistory", { webhistory: newHistory.filter((item: any) => item) });
        await storage.set("urlQueueList", { urlQueueList: newUrlQueue.filter((item: any) => item) });
        await storage.set("timeQueueList", { timeQueueList: newTimeQueue.filter((item: any) => item) });
        toast({
          title: "History store cleared",
          description: "Inactive history sessions have been removed",
          variant: "destructive",
        })
      });
    } catch (error) {
      console.log(error);
    }
  }

  async function saveCurrSnapShot(): Promise<void> {
    chrome.tabs.query({ active: true, currentWindow: true }, async function (tabs) {
      const storage = new Storage({ area: "local" })
      const tab = tabs[0];
      if (tab.id) {
        const tabId: number = tab.id
        const result = await chrome.scripting.executeScript({
          // @ts-ignore
          target: { tabId: tab.id },
          // @ts-ignore
          func: getRenderedHtml,
        });

        let toPushInTabHistory: any = result[0].result;

        //Updates 'tabhistory'
        let webhistoryObj: any = await storage.get("webhistory");

        const webHistoryOfTabId = webhistoryObj.webhistory.filter(
          (data: WebHistory) => {
            return data.tabsessionId === tab.id;
          }
        );

        toPushInTabHistory.pageContentMarkdown = convertHtmlToMarkdown(
          toPushInTabHistory.renderedHtml,
          {
            extractMainContent: true,
            includeMetaData: false,
            enableTableColumnTracking: true
          }
        )

        delete toPushInTabHistory.renderedHtml

        let tabhistory = webHistoryOfTabId[0].tabHistory;

        const urlQueueListObj: any = await storage.get("urlQueueList");
        const timeQueueListObj: any = await storage.get("timeQueueList");

        const isUrlQueueThere = urlQueueListObj.urlQueueList.find((data: WebHistory) => data.tabsessionId === tabId)
        const isTimeQueueThere = timeQueueListObj.timeQueueList.find((data: WebHistory) => data.tabsessionId === tabId)

        toPushInTabHistory.duration = toPushInTabHistory.entryTime - isTimeQueueThere.timeQueue[isTimeQueueThere.timeQueue.length - 1]
        if (isUrlQueueThere.urlQueue.length == 1) {
          toPushInTabHistory.reffererUrl = 'START'
        }
        if (isUrlQueueThere.urlQueue.length > 1) {
          toPushInTabHistory.reffererUrl = isUrlQueueThere.urlQueue[isUrlQueueThere.urlQueue.length - 2];
        }

        webHistoryOfTabId[0].tabHistory.push(toPushInTabHistory);
        
        await storage.set("webhistory", webhistoryObj);
        
        toast({
          title: "Snapshot saved",
          description: `Captured: ${toPushInTabHistory.title}`,
        })
      }

    });
  }

  const saveDatamessage = async () => {
    if (value === "") {
      toast({
        title: "Select a SearchSpace !",
      })
      return
    }
    
    const storage = new Storage({ area: "local" })
    const search_space_id = await storage.get("search_space_id");
    
    if (!search_space_id) {
      toast({
        title: "Invalid SearchSpace selected!",
        variant: "destructive",
      })
      return
    }

    setIsSaving(true);
    toast({
      title: "Save job running",
      description: "Saving captured content to SurfSense",
    })

    try {
      const resp = await sendToBackground({
        // @ts-ignore
        name: "savedata",
      })

      toast({
        title: resp.message,
      })
    } catch (error) {
      toast({
        title: "Error saving data",
        description: "Please try again",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false);
    }
  }

  async function logOut(): Promise<void> {
    const storage = new Storage({ area: "local" })
    await storage.remove('token');
    await storage.remove('showShadowDom');
    navigation("/login")
  }

  if (loading) {
    return <Loading />;
  } else {
    return searchspaces.length === 0 ? (
      <div className="flex min-h-screen flex-col bg-gradient-to-br from-gray-900 to-gray-800">
        <div className="flex flex-1 items-center justify-center p-4">
          <div className="w-full max-w-md space-y-8">
            <div className="flex flex-col items-center space-y-2 text-center">
              <div className="rounded-full bg-gray-800 p-3 shadow-lg ring-2 ring-gray-700">
                <img className="h-12 w-12" src={icon} alt="SurfSense" />
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white">SurfSense</h1>
              <div className="mt-4 rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-4 text-yellow-300">
                <p className="text-sm">Please create a Search Space to continue</p>
              </div>
            </div>
            
            <div className="mt-6 flex justify-center">
              <Button 
                onClick={logOut}
                variant="outline"
                className="flex items-center space-x-2 border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700"
              >
                <ExitIcon className="h-4 w-4" />
                <span>Sign Out</span>
              </Button>
            </div>
          </div>
        </div>
      </div>
    ) : (
      <div className="flex min-h-screen flex-col bg-gradient-to-br from-gray-900 to-gray-800">
        <div className="container mx-auto max-w-md p-4">
          <div className="flex items-center justify-between border-b border-gray-700 pb-4">
            <div className="flex items-center space-x-3">
              <div className="rounded-full bg-gray-800 p-2 shadow-md ring-1 ring-gray-700">
                <img className="h-6 w-6" src={icon} alt="SurfSense" />
              </div>
              <h1 className="text-xl font-semibold text-white">SurfSense</h1>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={logOut}
              className="rounded-full text-gray-400 hover:bg-gray-800 hover:text-white"
            >
              <ExitIcon className="h-4 w-4" />
              <span className="sr-only">Log out</span>
            </Button>
          </div>

          <div className="space-y-3 py-4">
            <div className="flex flex-col items-center justify-center rounded-lg border border-gray-700 bg-gray-800/50 p-6 backdrop-blur-sm">
              <div className="flex h-28 w-28 items-center justify-center rounded-full bg-gradient-to-br from-gray-700 to-gray-800 shadow-inner">
                <div className="flex flex-col items-center">
                  <img className="mb-2 h-10 w-10 opacity-80" src={brain} alt="brain" />
                  <span className="text-2xl font-semibold text-white">{noOfWebPages}</span>
                </div>
              </div>
              <p className="mt-4 text-sm text-gray-400">Captured web pages</p>
            </div>

            <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 backdrop-blur-sm">
              <label className="mb-2 block text-sm font-medium text-gray-300">
                Search Space
              </label>
              <Popover open={open} onOpenChange={setOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    className="w-full justify-between border-gray-700 bg-gray-900 text-white hover:bg-gray-700"
                  >
                    {value
                      ? searchspaces.find((space) => space.name === value)?.name
                      : "Select Search Space..."}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-full border-gray-700 bg-gray-800/90 p-0 backdrop-blur-sm">
                  <Command className="bg-transparent">
                    <CommandInput placeholder="Search spaces..." className="border-gray-700 bg-gray-900 text-gray-200" />
                    <CommandList>
                      <CommandEmpty>No search spaces found.</CommandEmpty>
                      <CommandGroup>
                        {searchspaces.map((space) => (
                          <CommandItem
                            key={space.name}
                            value={space.name}
                            onSelect={async (currentValue) => {
                              const storage = new Storage({ area: "local" })
                              if (currentValue === value) {
                                await storage.set("search_space", "");
                                await storage.set("search_space_id", 0);
                              } else {
                                const selectedSpace = searchspaces.find((space) => space.name === currentValue);
                                await storage.set("search_space", currentValue);
                                await storage.set("search_space_id", selectedSpace.id);
                              }
                              setValue(currentValue === value ? "" : currentValue)
                              setOpen(false)
                            }}
                            className="aria-selected:bg-gray-700"
                          >
                            <Check
                              className={cn(
                                "mr-2 h-4 w-4",
                                value === space.name ? "opacity-100" : "opacity-0"
                              )}
                            />
                            <div className="flex items-center">
                              <DiscIcon className="mr-2 h-4 w-4 text-teal-400" />
                              {space.name}
                            </div>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            <div className="grid gap-3">
              <Button
                variant="destructive"
                className="group flex w-full items-center justify-center space-x-2 bg-red-500/90 text-white hover:bg-red-600"
                onClick={() => clearMem()}
              >
                <CrossCircledIcon className="h-4 w-4 transition-transform group-hover:scale-110" />
                <span>Clear Inactive History</span>
              </Button>
              
              <Button
                variant="outline"
                className="group flex w-full items-center justify-center space-x-2 border-amber-500/50 bg-amber-500/10 text-amber-200 hover:bg-amber-500/20"
                onClick={() => saveCurrSnapShot()}
              >
                <FileIcon className="h-4 w-4 transition-transform group-hover:scale-110" />
                <span>Save Current Page</span>
              </Button>
              
              <Button
                variant="default" 
                className="group flex w-full items-center justify-center space-x-2 bg-gradient-to-r from-teal-500 to-emerald-500 text-white transition-all hover:from-teal-600 hover:to-emerald-600"
                onClick={() => saveDatamessage()}
                disabled={isSaving}
              >
                {isSaving ? (
                  <>
                    <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
                    <span>Saving to SurfSense...</span>
                  </>
                ) : (
                  <>
                    <UploadIcon className="h-4 w-4 transition-transform group-hover:scale-110" />
                    <span>Save to SurfSense</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }
};

export default HomePage