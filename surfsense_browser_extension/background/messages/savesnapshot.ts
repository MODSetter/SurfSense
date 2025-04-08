import { DOMParser } from "linkedom"

import { Storage } from "@plasmohq/storage"
import type { PlasmoMessaging } from "@plasmohq/messaging"

import type { WebHistory } from "~utils/interfaces"
import { webhistoryToLangChainDocument, getRenderedHtml } from "~utils/commons"
import { convertHtmlToMarkdown } from "dom-to-semantic-markdown"

// @ts-ignore
global.Node = {
  ELEMENT_NODE: 1,
  ATTRIBUTE_NODE: 2,
  TEXT_NODE: 3,
  CDATA_SECTION_NODE: 4,
  PROCESSING_INSTRUCTION_NODE: 7,
  COMMENT_NODE: 8,
  DOCUMENT_NODE: 9,
  DOCUMENT_TYPE_NODE: 10,
  DOCUMENT_FRAGMENT_NODE: 11,
};

const handler: PlasmoMessaging.MessageHandler = async (req, res) => {
  try {
    chrome.tabs.query(
      { active: true, currentWindow: true },
      async function (tabs) {
        const storage = new Storage({ area: "local" })
        const tab = tabs[0]
        if (tab.id) {
          const tabId: number = tab.id
          console.log("tabs", tabs)
          const result = await chrome.scripting.executeScript({
            // @ts-ignore
            target: { tabId: tab.id },
            // @ts-ignore
            func: getRenderedHtml,
            // world: "MAIN"
          })

          console.log("SnapRes", result)

          let toPushInTabHistory: any = result[0].result // const { renderedHtml, title, url, entryTime } = result[0].result;

          toPushInTabHistory.pageContentMarkdown = convertHtmlToMarkdown(
            toPushInTabHistory.renderedHtml,
            {
              extractMainContent: true,
              enableTableColumnTracking: true,
              includeMetaData: false,
              overrideDOMParser: new DOMParser()
            }
          )

          delete toPushInTabHistory.renderedHtml

          console.log("toPushInTabHistory", toPushInTabHistory)

          const urlQueueListObj: any = await storage.get("urlQueueList")
          const timeQueueListObj: any = await storage.get("timeQueueList")

          const isUrlQueueThere = urlQueueListObj.urlQueueList.find(
            (data: WebHistory) => data.tabsessionId === tabId
          )
          const isTimeQueueThere = timeQueueListObj.timeQueueList.find(
            (data: WebHistory) => data.tabsessionId === tabId
          )

          toPushInTabHistory.duration =
            toPushInTabHistory.entryTime -
            isTimeQueueThere.timeQueue[isTimeQueueThere.timeQueue.length - 1]
          if (isUrlQueueThere.urlQueue.length == 1) {
            toPushInTabHistory.reffererUrl = "START"
          }
          if (isUrlQueueThere.urlQueue.length > 1) {
            toPushInTabHistory.reffererUrl =
              isUrlQueueThere.urlQueue[isUrlQueueThere.urlQueue.length - 2]
          }

          let toSaveFinally: any[] = []

          const markdownFormat = webhistoryToLangChainDocument(
            tab.id,
            [toPushInTabHistory]
          )
          toSaveFinally.push(...markdownFormat)
          
          console.log("toSaveFinally", toSaveFinally)

          // Log first item to debug metadata structure
          if (toSaveFinally.length > 0) {
            console.log("First item metadata:", toSaveFinally[0].metadata);
          }

          // Create content array for documents in the format expected by the new API
          // The metadata is already in the correct format in toSaveFinally
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
            res.send({
              message: "Snapshot Saved Successfully"
            })
          }
        }
      }
    )
  } catch (error) {
    console.log(error)
  }
}

export default handler
