import { Storage } from "@plasmohq/storage"
import type { WebHistory } from "./interfaces"

export const emptyArr: any[] = []

export const initQueues = async (tabId: number) => {
  const storage = new Storage({ area: "local" })

  let urlQueueListObj: any = await storage.get("urlQueueList")
  let timeQueueListObj: any = await storage.get("timeQueueList")

  if (!urlQueueListObj && !timeQueueListObj) {
    await storage.set("urlQueueList", {
      urlQueueList: [{ tabsessionId: tabId, urlQueue: [] }]
    })
    await storage.set("timeQueueList", {
      timeQueueList: [{ tabsessionId: tabId, timeQueue: [] }]
    })

    return
  }

  if (urlQueueListObj.urlQueueList && timeQueueListObj.timeQueueList) {
    const isUrlQueueThere = urlQueueListObj.urlQueueList.find(
      (data: WebHistory) => data.tabsessionId === tabId
    )
    const isTimeQueueThere = timeQueueListObj.timeQueueList.find(
      (data: WebHistory) => data.tabsessionId === tabId
    )

    if (!isUrlQueueThere) {
      urlQueueListObj.urlQueueList.push({ tabsessionId: tabId, urlQueue: [] })

      await storage.set("urlQueueList", {
        urlQueueList: urlQueueListObj.urlQueueList
      })
    }

    if (!isTimeQueueThere) {
      timeQueueListObj.timeQueueList.push({
        tabsessionId: tabId,
        timeQueue: []
      })

      await storage.set("timeQueueList", {
        timeQueueList: timeQueueListObj.timeQueueList
      })
    }

    return
  }
}

export function getRenderedHtml() {
  return {
    url: window.location.href,
    entryTime: Date.now(),
    title: document.title,
    renderedHtml: document.documentElement.outerHTML
  }
}

export const initWebHistory = async (tabId: number) => {
const storage = new Storage({ area: "local" })
  const result: any = await storage.get("webhistory")

  if (result === undefined) {
    await storage.set("webhistory", { webhistory: emptyArr })
    return
  }

  const ifIdExists = result.webhistory.find(
    (data: WebHistory) => data.tabsessionId === tabId
  )

  if (ifIdExists === undefined) {
    let webHistory = result.webhistory
    const initData = {
      tabsessionId: tabId,
      tabHistory: emptyArr
    }

    webHistory.push(initData)

    try {
      await storage.set("webhistory", { webhistory: webHistory })
      return
    } catch (error) {
      console.log(error)
    }
  } else {
    return
  }
}

export function toIsoString(date: Date) {
  var tzo = -date.getTimezoneOffset(),
    dif = tzo >= 0 ? "+" : "-",
    pad = function (num: number) {
      return (num < 10 ? "0" : "") + num
    }

  return (
    date.getFullYear() +
    "-" +
    pad(date.getMonth() + 1) +
    "-" +
    pad(date.getDate()) +
    "T" +
    pad(date.getHours()) +
    ":" +
    pad(date.getMinutes()) +
    ":" +
    pad(date.getSeconds()) +
    dif +
    pad(Math.floor(Math.abs(tzo) / 60)) +
    ":" +
    pad(Math.abs(tzo) % 60)
  )
}

export const webhistoryToLangChainDocument = (
  tabId: number,
  tabHistory: any[]
) => {
  let toSaveFinally = []
  for (let j = 0; j < tabHistory.length; j++) {
    const mtadata = {
      BrowsingSessionId: `${tabId}`,
      VisitedWebPageURL: `${tabHistory[j].url}`,
      VisitedWebPageTitle: `${tabHistory[j].title}`,
      VisitedWebPageDateWithTimeInISOString: `${toIsoString(new Date(tabHistory[j].entryTime))}`,
      VisitedWebPageReffererURL: `${tabHistory[j].reffererUrl}`,
      VisitedWebPageVisitDurationInMilliseconds: tabHistory[j].duration
    }

    toSaveFinally.push({
      metadata: mtadata,
      pageContent: tabHistory[j].pageContentMarkdown
    })
  }

  return toSaveFinally
}
