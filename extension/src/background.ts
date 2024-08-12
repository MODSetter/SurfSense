import {
  initWebHistory,
  getRenderedHtml,
  initQueues,
} from "./commons";
import { WebHistory } from "./interfaces";

chrome.tabs.onCreated.addListener(async (tab: any) => {
  try {
    await initWebHistory(tab.id);
    await initQueues(tab.id);
  } catch (error) {
    console.log(error);
  }
});

chrome.tabs.onUpdated.addListener(
  async (tabId: number, changeInfo: any, tab: any) => {
    if (changeInfo.status === "complete" && tab.url) {
      await initWebHistory(tab.id);
      await initQueues(tab.id);

      const result = await chrome.scripting.executeScript({
        // @ts-ignore
        target: { tabId: tab.id },
        // @ts-ignore
        function: getRenderedHtml,
      });

      let toPushInTabHistory = result[0].result; // const { renderedHtml, title, url, entryTime } = result[0].result;

      let urlQueueListObj = await chrome.storage.local.get(["urlQueueList"]);
      let timeQueueListObj = await chrome.storage.local.get(["timeQueueList"]);

      urlQueueListObj.urlQueueList
        .find((data: WebHistory) => data.tabsessionId === tabId)
        .urlQueue.push(toPushInTabHistory.url);
      timeQueueListObj.timeQueueList
        .find((data: WebHistory) => data.tabsessionId === tabId)
        .timeQueue.push(toPushInTabHistory.entryTime);

      await chrome.storage.local.set({
        urlQueueList: urlQueueListObj.urlQueueList,
      });
      await chrome.storage.local.set({
        timeQueueList: timeQueueListObj.timeQueueList,
      });
    }
  }
);

chrome.tabs.onRemoved.addListener(async (tabId: number, removeInfo: object) => {
  let urlQueueListObj = await chrome.storage.local.get(["urlQueueList"]);
  let timeQueueListObj = await chrome.storage.local.get(["timeQueueList"]);
  if(urlQueueListObj.urlQueueList && timeQueueListObj.timeQueueList){

    const urlQueueListToSave  = urlQueueListObj.urlQueueList.map((element: WebHistory) => {
      if(element.tabsessionId !== tabId){
        return element
      }
    })
    const timeQueueListSave = timeQueueListObj.timeQueueList.map((element: WebHistory) => {
      if(element.tabsessionId !== tabId){
        return element
      }
    })
    await chrome.storage.local.set({
      urlQueueList: urlQueueListToSave.filter((item: any) => item),
    });
    await chrome.storage.local.set({
      timeQueueList: timeQueueListSave.filter((item: any) => item),
    });

  }

});


///// IGONRE THESE COMMENTS THESE CONTAINS SOME IDEAS THAT NEVER WORKED AS INTENTDED
// await initWebHistory(tabId);
// console.log("tab", tab);
// if (tab.status === "loading") {
//   if (tab.url) {
//     const autotrackerFlag = await chrome.storage.local.get(["autoTracker"]);

//     const lastUrlObj = await chrome.storage.local.get(["lastUrl"]);

//     if (autotrackerFlag.autoTracker) {
//       if (lastUrlObj.lastUrl[tabId] !== "START") {
//         console.log("loading");
//         console.log(lastUrlObj.lastUrl[tabId]);
//         //update last entry duration
//         try {
//           const lastEntryTimeObj = await chrome.storage.local.get([
//             "lastEntryTime",
//           ]);
//           let webhistoryObj = await chrome.storage.local.get([
//             "webhistory",
//           ]);
//           const webHistoryLength = webhistoryObj.webhistory.find(
//             (data: WebHistory) => data.tabsessionId === tabId
//           ).tabHistory.length;

//           if(webHistoryLength > 0){
//             webhistoryObj.webhistory.find(
//               (data: WebHistory) => data.tabsessionId === tabId
//             ).tabHistory[webHistoryLength - 1].duration =
//               Date.now() - lastEntryTimeObj.lastEntryTime[tabId];
//           }

//           await chrome.storage.local.set({
//             webhistory: webhistoryObj.webhistory,
//           });
//         } catch (error) {
//           console.log(error);
//         }
//       }
//     }
//   }
// }

// const autotrackerFlag = await chrome.storage.local.get(["autoTracker"]);
// if (!autotrackerFlag.autoTracker) {
//   await initURlQueue(tab.id);
// }

// const lastUrl = {
//   // @ts-ignore
//   [tab.id]: "START",
// };

// // console.log(lastUrl);

// await chrome.storage.local.set({
//   lastUrl: lastUrl,
// });

// const lastEntryTime = {
//   // @ts-ignore
//   [tab.id]: Date.now(),
// };

// // console.log(lastUrl);

// await chrome.storage.local.set({
//   lastEntryTime: lastEntryTime,
// });

// let webhistoryObj = await chrome.storage.local.get(["webhistory"]);
// const webHistoryOfTabId = webhistoryObj.webhistory.filter(
//   (data: WebHistory) => {
//     return data.tabsessionId === tab.id;
//   }
// );
// let tabhistory = webHistoryOfTabId[0].tabHistory;

// if (tabhistory.length === 0) {
//   toPushInTabHistory.reffererUrl = "START";
// } else {
//   toPushInTabHistory.reffererUrl = tabhistory[tabhistory.length - 1].url;
//   tabhistory[tabhistory.length - 1].duration =
//     toPushInTabHistory.entryTime -
//     tabhistory[tabhistory.length - 1].entryTime;
// }

// tabhistory.push(toPushInTabHistory);

// //Update Webhistory
// try {
//   webhistoryObj.webhistory.find(
//     (data: WebHistory) => data.tabsessionId === tab.id
//   ).tabHistory = tabhistory;

//   await chrome.storage.local.set({
//     webhistory: webhistoryObj.webhistory,
//   });
// } catch (error) {
//   console.log(error);
// }

// const autotrackerFlag = await chrome.storage.local.get(["autoTracker"]);
// if (autotrackerFlag.autoTracker) {
//   const result = await chrome.scripting.executeScript({
//     // @ts-ignore
//     target: { tabId: tab.id },
//     // @ts-ignore
//     function: getRenderedHtml,
//   });

//   let toPushInTabHistory = result[0].result; // const { renderedHtml, title, url, entryTime } = result[0].result;

//   // //Updates 'tabhistory'
//   let webhistoryObj = await chrome.storage.local.get(["webhistory"]);

//   const webHistoryOfTabId = webhistoryObj.webhistory.filter(
//     (data: WebHistory) => {
//       return data.tabsessionId === tab.id;
//     }
//   );

//   let tabhistory = webHistoryOfTabId[0].tabHistory;

//   // let lastUrlObj = await chrome.storage.local.get(["lastUrl"]);
//   const lastEntryTimeObj = await chrome.storage.local.get([
//     "lastEntryTime",
//   ]);
//   lastEntryTimeObj.lastEntryTime[tabId] = Date.now();

//   await chrome.storage.local.set({
//     lastEntryTime: lastEntryTimeObj.lastEntryTime,
//   });

//   //When first entry
//   if (tabhistory.length === 0) {
//     let lastUrlObj = await chrome.storage.local.get(["lastUrl"]);
//     lastUrlObj.lastUrl[tabId] = tab.url;
//     await chrome.storage.local.set({
//       lastUrl: lastUrlObj.lastUrl,
//     });

//     toPushInTabHistory.reffererUrl = "START";
//     toPushInTabHistory.entryTime = Date.now();
//     tabhistory.push(toPushInTabHistory);
//     try {
//       webhistoryObj.webhistory.find(
//         (data: WebHistory) => data.tabsessionId === tab.id
//       ).tabHistory = tabhistory;

//       await chrome.storage.local.set({
//         webhistory: webhistoryObj.webhistory,
//       });
//     } catch (error) {
//       console.log(error);
//     }
//   } else {
//     const lastUrlObj = await chrome.storage.local.get(["lastUrl"]);

//     toPushInTabHistory.reffererUrl = lastUrlObj.lastUrl[tabId];
//     toPushInTabHistory.entryTime = Date.now();
//     tabhistory.push(toPushInTabHistory);

//     try {
//       webhistoryObj.webhistory.find(
//         (data: WebHistory) => data.tabsessionId === tab.id
//       ).tabHistory = tabhistory;
//       // console.log("webhistory",webhistoryObj);
//       await chrome.storage.local.set({
//         webhistory: webhistoryObj.webhistory,
//       });
//     } catch (error) {
//       console.log(error);
//     }

//     lastUrlObj.lastUrl[tabId] = tab.url;
//     await chrome.storage.local.set({
//       lastUrl: lastUrlObj.lastUrl,
//     });
//   }
// } else {
//   await initURlQueue(tab.id);
//   let urlQueue = await chrome.storage.local.get(["urlQueue"]);
//   // console.log("urlQueue", urlQueue);
//   urlQueue.urlQueue[tabId].push(tab.url)

//   urlQueue.urlQueue[tabId] = [...new Set(urlQueue.urlQueue[tabId])]
//   await chrome.storage.local.set({
//     urlQueue: urlQueue.urlQueue,
//   });

//   const lastEntryTimeObj = await chrome.storage.local.get([
//     "lastEntryTime",
//   ]);
//   lastEntryTimeObj.lastEntryTime[tabId] = Date.now();

//   await chrome.storage.local.set({
//     lastEntryTime: lastEntryTimeObj.lastEntryTime,
//   });
// }

// chrome.tabs.onRemoved.addListener(async (tabId: number, removeInfo: object) => {
//   const autotrackerFlag = await chrome.storage.local.get(["autoTracker"]);
//   //duration, referURL edge conditions
//   let webhistoryObj = await chrome.storage.local.get(["webhistory"]);
//   const webHistoryLength = webhistoryObj.webhistory.find(
//     (data: WebHistory) => data.tabsessionId === tabId
//   ).tabHistory.length;

//   if (webHistoryLength > 0) {
//     if (
//       !webhistoryObj.webhistory.find(
//         (data: WebHistory) => data.tabsessionId === tabId
//       ).tabHistory[webHistoryLength - 1].duration
//     ) {
//       webhistoryObj.webhistory.find(
//         (data: WebHistory) => data.tabsessionId === tabId
//       ).tabHistory[webHistoryLength - 1].duration =
//         Date.now() -
//         webhistoryObj.webhistory.find(
//           (data: WebHistory) => data.tabsessionId === tabId
//         ).tabHistory[webHistoryLength - 1].entryTime;
//     }
//   }

//   let urlQueueLocal = await chrome.storage.local.get(["urlQueue"]);
//   let timeQueueLocal = await chrome.storage.local.get(["timeQueue"]);
//   delete urlQueueLocal.urlQueue[tabId]
//   delete timeQueueLocal.timeQueue[tabId]
//   await chrome.storage.local.set({
//     urlQueue: urlQueueLocal.urlQueue,
//   });
//   await chrome.storage.local.set({
//     timeQueue: timeQueueLocal.timeQueue,
//   });

//   // if (autotrackerFlag.autoTracker) {
//   //   try {
//   //     const lastEntryTimeObj = await chrome.storage.local.get([
//   //       "lastEntryTime",
//   //     ]);
//   //     let webhistoryObj = await chrome.storage.local.get(["webhistory"]);
//   //     const webHistoryLength = webhistoryObj.webhistory.find(
//   //       (data: WebHistory) => data.tabsessionId === tabId
//   //     ).tabHistory.length;

//   //     if (webHistoryLength > 0) {
//   //       webhistoryObj.webhistory.find(
//   //         (data: WebHistory) => data.tabsessionId === tabId
//   //       ).tabHistory[webHistoryLength - 1].duration =
//   //         Date.now() - lastEntryTimeObj.lastEntryTime[tabId];
//   //     }

//   //     await chrome.storage.local.set({
//   //       webhistory: webhistoryObj.webhistory,
//   //     });
//   //   } catch (error) {
//   //     console.log(error);
//   //   }
//   // } else {
//   //   await initURlQueue(tabId);
//   //   let urlQueue = await chrome.storage.local.get(["urlQueue"]);
//   //   delete urlQueue.urlQueue[tabId];
//   //   chrome.storage.local.set({
//   //     urlQueue: urlQueue.urlQueue,
//   //   });
//   // }
// });

// if (tabhistory.length > 0) {
//   //updates duration of last entry in 'tabhistory'
//   tabhistory[tabhistory.length - 1].duration =
//     toPushInTabHistory.entryTime -
//     tabhistory[tabhistory.length - 1].entryTime;

//   //Update refferer Url
//   toPushInTabHistory.reffererUrl = tabhistory[tabhistory.length - 1].url;

//   if (tabhistory.length == 1) {
//     tabhistory[0].reffererUrl = "START";
//   }
// }
// tabhistory.push(toPushInTabHistory);

// //Set Updated tabhistory
// try {
//   webhistoryObj.webhistory.find(
//     (data: WebHistory) => data.tabsessionId === tab.id
//   ).tabHistory = tabhistory;
//   // console.log("webhistory",webhistoryObj);
//   await chrome.storage.local.set({
//     webhistory: webhistoryObj.webhistory,
//   });
// } catch (error) {
//   console.log(error);
// }

// try {
//   let webhistoryObj = await chrome.storage.local.get(["webhistory"]);
//   const webHistoryLength = webhistoryObj.webhistory.find(
//     (data: WebHistory) => data.tabsessionId === tabId
//   ).tabHistory.length;
//   const lastWebPageEntryTime = webhistoryObj.webhistory.find(
//     (data: WebHistory) => data.tabsessionId === tabId
//   ).tabHistory[webHistoryLength - 1].entryTime;
//   webhistoryObj.webhistory.find(
//     (data: WebHistory) => data.tabsessionId === tabId
//   ).tabHistory[webHistoryLength - 1].duration =
//     Date.now() - lastWebPageEntryTime;
//   //Edge Condition of reffererUrl
//   if (webHistoryLength == 1) {
//     webhistoryObj.webhistory.find(
//       (data: WebHistory) => data.tabsessionId === tabId
//     ).tabHistory[0].reffererUrl = "START";
//   }
//   //Sets 'webhistory'
//   try {
//     await chrome.storage.local.set({ webhistory: webhistoryObj.webhistory });
//     // const result = await chrome.storage.local.get(["webhistory"]);
//     // console.log("webhistoryinRemoved",result);
//   } catch (error) {
//     console.log(error);
//   }
// } catch (error) {
//   console.log(error);
// }
// await chrome.storage.local.set({ id: tab.id });
// await chrome.storage.local.set({ tabhistory: [] });
// const result = await chrome.storage.local.get(["id"]);
// console.log(result);

// const tabid = await chrome.storage.local.get(["id"]);
// const toPushinWebHostory = {
//   tabsessionId: tabid.id,
//   tabHistory: tabhistory,
// };

// //Updates 'webhistory'
// const webhistoryObj = await chrome.storage.local.get(["webhistory"]);
// // console.log("WEBH", webhistoryObj);
// const webhistory = webhistoryObj.webhistory;
// webhistory.push(toPushinWebHostory);

// //Sets 'webhistory'
// try {
//   await chrome.storage.local.set({ webhistory: webhistory });
//   const result = await chrome.storage.local.get(["webhistory"]);
//   console.log("RES",result)
// } catch (error) {
//   console.log(error);
// }

// try {
//   let lastUrlObj = await chrome.storage.local.get(["lastUrl"]);

//   // console.log("Before Update", lastUrlObj);
//   if(tab.url !== lastUrlObj.lastUrl[tabId]){
//     // console.log("Before Update", lastUrlObj);
//     lastUrlObj.lastUrl[tabId] = tab.url;
//     // console.log("After Update", lastUrlObj);

//     await chrome.storage.local.set({
//       lastUrl: lastUrlObj.lastUrl,
//     });

//     //Update DURATION of old url
//   }

//   // // const lastUrl = await chrome.storage.local.get(["lastUrl"]);

//   // await chrome.storage.local.set({
//   //   lastUrl: lastUrlObj.lastUrl,
//   // });
// } catch (error) {
//   console.log(error);
// }
