import type { PlasmoMessaging } from "@plasmohq/messaging"
import { Storage } from "@plasmohq/storage"

import {
  emptyArr,
  webhistoryToLangChainDocument
} from "~utils/commons"

const clearMemory = async () => {
  try {
    const storage = new Storage({ area: "local" })

    let webHistory: any = await storage.get("webhistory")
    let urlQueue: any = await storage.get("urlQueueList")
    let timeQueue: any = await storage.get("timeQueueList")

    if (!webHistory.webhistory) {
      return
    }

    //Main Cleanup COde
    chrome.tabs.query({}, async (tabs) => {
      //Get Active Tabs Ids
      // console.log("Event Tabs",tabs)
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

      await storage.set("webhistory", {
        webhistory: newHistory.filter((item: any) => item)
      })
      await storage.set("urlQueueList", {
        urlQueueList: newUrlQueue.filter((item: any) => item)
      })
      await storage.set("timeQueueList", {
        timeQueueList: newTimeQueue.filter((item: any) => item)
      })
    })
  } catch (error) {
    console.log(error)
  }
}

const handler: PlasmoMessaging.MessageHandler = async (req, res) => {
  try {
    const storage = new Storage({ area: "local" })

    const webhistoryObj: any = await storage.get("webhistory")
    const webhistory = webhistoryObj.webhistory
    if (webhistory) {
      let toSaveFinally: any[] = []
      let newHistoryAfterCleanup: any[] = []

      for (let i = 0; i < webhistory.length; i++) {
        const markdownFormat = webhistoryToLangChainDocument(
          webhistory[i].tabsessionId,
          webhistory[i].tabHistory
        )
        toSaveFinally.push(...markdownFormat)
        newHistoryAfterCleanup.push({
          tabsessionId: webhistory[i].tabsessionId,
          tabHistory: emptyArr
        })
      }

      await storage.set("webhistory",{ webhistory: newHistoryAfterCleanup });

      // Log first item to debug metadata structure
      if (toSaveFinally.length > 0) {
        console.log("First item metadata:", toSaveFinally[0].metadata);
      }

      // Create content array for documents in the format expected by the new API
      const content = toSaveFinally.map(item => ({
        metadata: {
          BrowsingSessionId: String(item.metadata.BrowsingSessionId || ""),
          VisitedWebPageURL: String(item.metadata.VisitedWebPageURL || ""),
          VisitedWebPageTitle: String(item.metadata.VisitedWebPageTitle || "No Title"),
          VisitedWebPageDateWithTimeInISOString: String(item.metadata.VisitedWebPageDateWithTimeInISOString || ""),
          VisitedWebPageReffererURL: String(item.metadata.VisitedWebPageReffererURL || ""),
          VisitedWebPageVisitDurationInMilliseconds: String(item.metadata.VisitedWebPageVisitDurationInMilliseconds || "0")
        },
        pageContent: String(item.pageContent || "")
      }));

      const token = await storage.get("token");
      const search_space_id = parseInt(await storage.get("search_space_id"), 10);

      const toSend = {
        document_type: "EXTENSION",
        content: content,
        search_space_id: search_space_id
      }

      console.log("toSend", toSend)

      const requestOptions = {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(toSend)
      }

      const response = await fetch(
        `${process.env.PLASMO_PUBLIC_BACKEND_URL}/api/v1/documents/`,
        requestOptions
      )
      const resp = await response.json()
      if (resp) {
        await clearMemory()
        res.send({
          message: "Save Job Started"
        })
      }
    }
  } catch (error) {
    console.log(error)
  }
}

export default handler
