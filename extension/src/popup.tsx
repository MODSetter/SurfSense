import React, { useEffect, useState } from "react";
import {
  goTo,
  Router,
} from 'react-chrome-extension-router';
import { createRoot } from "react-dom/client";
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import "./assets/tailwind.css"

import { convertHtmlToMarkdown } from "dom-to-semantic-markdown";
import { WebHistory } from "./interfaces";
import { webhistoryToLangChainDocument, getRenderedHtml, emptyArr } from "./commons";
import Loading from "./pages/Loading";

import { LoginForm } from "./pages/LoginForm";
import { FillEnvVariables } from "./pages/EnvVarSettings";
import { API_SECRET_KEY, BACKEND_URL } from "./env";



export async function clearMem(): Promise<void> {
  try {

    let result = await chrome.storage.local.get(["webhistory"]);

    if (!result.webhistory) {
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
      const newHistory = result.webhistory.map((element: any) => {
        //@ts-ignore
        if (actives.includes(element.tabsessionId)) {
          return element
        }
      })


      await chrome.storage.local.set({ webhistory: newHistory.filter((item: any) => item) });

      toast.info("History Store Deleted!", {
        position: "bottom-center"
      });
    });
  } catch (error) {
    console.log(error);
  }
}


export const Popup = () => {
  const [noOfWebPages, setNoOfWebPages] = useState<number>(0);
  const [loading, setLoading] = useState(true);


  useEffect(() => {
    const verifyToken = async () => {
      const token = localStorage.getItem('token');
      console.log(token)
      try {
        const response = await fetch(`${BACKEND_URL}/verify-token/${token}`);

        if (!response.ok) {
          throw new Error('Token verification failed');
        }else{
          const NEO4JURL = localStorage.getItem('neourl');
          const NEO4JUSERNAME = localStorage.getItem('neouser');
          const NEO4JPASSWORD = localStorage.getItem('neopass');
          const OPENAIKEY = localStorage.getItem('openaikey');
    
          const check = (NEO4JURL && NEO4JUSERNAME && NEO4JPASSWORD && OPENAIKEY)
          if(!check){
            goTo(FillEnvVariables);
          }
        }
      } catch (error) {
        localStorage.removeItem('token');
        goTo(LoginForm);
      }

   

    };

    verifyToken();
    setLoading(false)
  }, []);


  useEffect(() => {
    async function onLoad() {
      try {
        chrome.storage.onChanged.addListener(
          (changes: any, areaName: string) => {
            if (changes.webhistory) {
              // console.log("changes.webhistory", changes.webhistory)
              const webhistory = changes.webhistory.newValue;

              let sum = 0
              webhistory.forEach((element: any) => {
                sum = sum + element.tabHistory.length
              });

              setNoOfWebPages(sum)
            }
            // console.log(changes)
            // console.log(areaName)
          }
        );



        const webhistoryObj = await chrome.storage.local.get(["webhistory"]);
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

  const saveData = async () => {

    try {
      // setLoading(true);

      const webhistoryObj = await chrome.storage.local.get(["webhistory"]);
      const webhistory = webhistoryObj.webhistory;
      if (webhistory) {

        let processedHistory: any[] = []
        let newHistoryAfterCleanup: any[] = []

        webhistory.forEach((element: any) => {
          let tabhistory = element.tabHistory;
          for (let i = 0; i < tabhistory.length; i++) {
            tabhistory[i].pageContentMarkdown = convertHtmlToMarkdown(tabhistory[i].renderedHtml, {
              extractMainContent: true,
              enableTableColumnTracking: true,
            })

            delete tabhistory[i].renderedHtml
          }

          processedHistory.push({
            tabsessionId: element.tabsessionId,
            tabHistory: tabhistory,
          })

          newHistoryAfterCleanup.push({
            tabsessionId: element.tabsessionId,
            tabHistory: emptyArr,
          })
        });

        await chrome.storage.local.set({ webhistory: newHistoryAfterCleanup });
        let toSaveFinally = []

        for (let i = 0; i < processedHistory.length; i++) {
          const markdownFormat = webhistoryToLangChainDocument(processedHistory[i].tabsessionId, processedHistory[i].tabHistory)
          toSaveFinally.push(...markdownFormat)
        }

        // console.log("SAVING", toSaveFinally)

        const toSend = {
          documents: toSaveFinally,
          neourl: localStorage.getItem('neourl'),
          neouser: localStorage.getItem('neouser'),
          neopass: localStorage.getItem('neopass'),
          openaikey: localStorage.getItem('openaikey'),
          apisecretkey: API_SECRET_KEY
        }

        // console.log("toSend",toSend)

        const requestOptions = {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(toSend),
        };

        toast.info("Save Job Initiated.", {
          position: "bottom-center"
        });

        const response = await fetch(`${BACKEND_URL}/kb/`, requestOptions);
        const res = await response.json();
        if (res.success) {
          toast.success("Save Job Completed.", {
            position: "bottom-center",
            autoClose: false
          });
        }

      }
    } catch (error) {
      console.log(error);
    }

  };

  // async function showMem(): Promise<void> {
  //   // localStorage.removeItem('token');
  //   // await chrome.storage.local.clear()
  //   const webhistoryObj = await chrome.storage.local.get(["webhistory"]);
  //   const urlQueue = await chrome.storage.local.get(["urlQueueList"]);
  //   const timeQueue = await chrome.storage.local.get(["timeQueueList"]);
  //   console.log("CURR MEM", webhistoryObj, urlQueue, timeQueue);

  //   // await chrome.storage.local.set({
  //   //   urlQueueList: urlQueueListObj.urlQueueList,
  //   // });
  //   // await chrome.storage.local.set({
  //   //   timeQueueList: timeQueueListObj.timeQueueList,
  //   // });
  //   // clearMem()
  // }

  async function logOut(): Promise<void> {
    localStorage.removeItem('token');
    goTo(LoginForm)
  }

  async function saveCurrSnapShot(): Promise<void> {
    chrome.tabs.query({ active: true, currentWindow: true }, async function (tabs) {
      const tab = tabs[0];
      if (tab.id) {
        // await initWebHistory(tab.id);
        // await initQueues(tab.id);
        const tabId: number = tab.id
        const result = await chrome.scripting.executeScript({
          // @ts-ignore
          target: { tabId: tab.id },
          // @ts-ignore
          function: getRenderedHtml,
        });

        let toPushInTabHistory = result[0].result; // const { renderedHtml, title, url, entryTime } = result[0].result;

        // //Updates 'tabhistory'
        let webhistoryObj = await chrome.storage.local.get(["webhistory"]);

        const webHistoryOfTabId = webhistoryObj.webhistory.filter(
          (data: WebHistory) => {
            return data.tabsessionId === tab.id;
          }
        );

        let tabhistory = webHistoryOfTabId[0].tabHistory;
       

        const urlQueueListObj = await chrome.storage.local.get(["urlQueueList"]);
        const timeQueueListObj = await chrome.storage.local.get(["timeQueueList"]);

        const isUrlQueueThere = urlQueueListObj.urlQueueList.find((data: WebHistory) => data.tabsessionId === tabId)
        const isTimeQueueThere = timeQueueListObj.timeQueueList.find((data: WebHistory) => data.tabsessionId === tabId)

        // console.log(isUrlQueueThere)
        // console.log(isTimeQueueThere)

        // console.log(isTimeQueueThere.timeQueue[isTimeQueueThere.length - 1])

        toPushInTabHistory.duration = toPushInTabHistory.entryTime - isTimeQueueThere.timeQueue[isTimeQueueThere.timeQueue.length - 1]
        if (isUrlQueueThere.urlQueue.length == 1) {
          toPushInTabHistory.reffererUrl = 'START'
        }
        if (isUrlQueueThere.urlQueue.length > 1) {
          toPushInTabHistory.reffererUrl = isUrlQueueThere.urlQueue[isUrlQueueThere.urlQueue.length - 2];
        }

        tabhistory.push(toPushInTabHistory);

        // console.log(toPushInTabHistory)

        //Update Webhistory
        try {
          webhistoryObj.webhistory.find(
            (data: WebHistory) => data.tabsessionId === tab.id
          ).tabHistory = tabhistory;

          await chrome.storage.local.set({
            webhistory: webhistoryObj.webhistory,
          });
        } catch (error) {
          console.log(error);
        }


        toast.success("Saved Snapshot !", {
          position: "bottom-center"
        });
      }

    });
  }

  if (loading) {
    return <Loading />;
  } else {
    return (
      <section className="dark bg-gray-50 dark:bg-gray-900">
        {/* <div onClick={() => showMem()}>ShowMem</div> */}
        <div className="flex flex-col items-center justify-center px-4 pt-4 pb-12 mx-auto md:h-screen lg:py-0">
          <div className="flex items-center mb-6 text-2xl font-semibold text-gray-900 dark:text-white">
            <img className="w-8 h-8 mr-2" src="./icon-128.png" alt="logo" />
            SurfSense
          </div>
          <div className="w-full bg-white rounded-lg shadow dark:border md:mt-0 sm:max-w-md xl:p-0 dark:bg-gray-800 dark:border-gray-700">
            <div className="p-6 space-y-4 md:space-y-6 sm:p-8">
              <div className="flex justify-between">
                <button type="button" onClick={() => goTo(FillEnvVariables)} className="px-3 py-2 text-xs font-medium text-center text-white bg-blue-700 rounded-lg hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" className="lucide lucide-settings"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" /><circle cx="12" cy="12" r="3" /></svg>
                </button>
                <button type="button" onClick={() => logOut()} className="px-3 py-2 text-xs font-medium text-center text-white bg-blue-700 rounded-lg hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" className="lucide lucide-log-out"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" x2="9" y1="12" y2="12" /></svg>
                </button>
              </div>

              <div className="flex flex-col gap-3">
                <div className="block max-w-sm p-4 bg-white border border-gray-200 rounded-lg shadow hover:bg-gray-100 dark:bg-gray-800 dark:border-gray-700 dark:hover:bg-gray-700">
                  <div className="flex flex-col gap-4 justify-center items-center text-2xl font-semibold text-gray-900 dark:text-white">
                    <img className="w-30 h-30 rounded-full" src="./brain.png" alt="brain" />
                    <div>
                      {noOfWebPages}
                    </div>
                  </div>
                </div>

                <button type="button" className="w-full text-white bg-gradient-to-r from-red-400 via-red-500 to-red-600 hover:bg-gradient-to-br focus:ring-4 focus:outline-none focus:ring-red-300 dark:focus:ring-red-800 font-medium rounded-lg text-sm px-5 py-2.5 text-center" onClick={() => clearMem()}>Clear History Store</button>
                <button type="button" className="w-full text-gray-900 bg-gradient-to-r from-red-200 via-red-300 to-yellow-200 hover:bg-gradient-to-bl focus:ring-4 focus:outline-none focus:ring-red-100 dark:focus:ring-red-400 font-medium rounded-lg text-sm px-5 py-2.5 text-center" onClick={() => saveCurrSnapShot()}>Save Current Webpage SnapShot</button>
                <button type="button" className="w-full text-gray-900 bg-gradient-to-r from-teal-200 to-lime-200 hover:bg-gradient-to-l hover:from-teal-200 hover:to-lime-200 focus:ring-4 focus:outline-none focus:ring-lime-200 dark:focus:ring-teal-700 font-medium rounded-lg text-sm px-5 py-2.5 text-center me-2 mb-2" onClick={() => saveData()}>Save to SurfSense</button>

              </div>
            </div>
          </div>
        </div>
      </section>
    )
  }
};


const root = createRoot(document.getElementById("root")!);

root.render(
  <React.StrictMode>
    <Router>
      <Popup />
    </Router>
    <ToastContainer autoClose={2000} />
  </React.StrictMode>
);

// chrome.tabs.query({ active: true, currentWindow: true }, async function (tabs) {
//   const tab = tabs[0];
//   if (tab.id) {
//     await initWebHistory(tab.id);
//     await initQueues(tab.id);
//   }
// });
// export const LoginForm = () => {
//   const [username, setUsername] = useState('');
//   const [password, setPassword] = useState('');
//   const [error, setError] = useState('');
//   const [loading, setLoading] = useState(false);

//   // const navigate = useNavigate();

//   const validateForm = () => {
//     if (!username || !password) {
//       setError('Username and password are required');
//       return false;
//     }
//     setError('');
//     return true;
//   };

//   const handleSubmit = async (event: { preventDefault: () => void; }) => {
//     event.preventDefault();
//     if (!validateForm()) return;
//     setLoading(true);

//     const formDetails = new URLSearchParams();
//     formDetails.append('username', username);
//     formDetails.append('password', password);

//     try {
//       const response = await fetch('http://localhost:8000/token', {
//         method: 'POST',
//         headers: {
//           'Content-Type': 'application/x-www-form-urlencoded',
//         },
//         body: formDetails,
//       });

//       setLoading(false);

//       if (response.ok) {
//         const data = await response.json();
//         await chrome.storage.local.set({
//           token: data.access_token,
//         });
//         // localStorage.setItem('token', data.access_token);
//         goTo(Popup);
//       } else {
//         const errorData = await response.json();
//         setError(errorData.detail || 'Authentication failed!');
//       }
//     } catch (error) {
//       setLoading(false);
//       setError('An error occurred. Please try again later.');
//     }
//   };

//   const goToRegister = async () => {
//     console.log("Reg")
//     goTo(RegisterForm)
//   }
//   return (
//     <>
//       <section className="dark bg-gray-50 dark:bg-gray-900">
//         <div onClick={() => clearMem}>CLEAR MEM</div>
//         <div className="flex flex-col items-center justify-center px-6 py-8 mx-auto md:h-screen lg:py-0">
//           <a href="#" className="flex items-center mb-6 text-2xl font-semibold text-gray-900 dark:text-white">
//             <img className="w-8 h-8 mr-2" src={"./icon-128.png"} alt="logo" />
//             SurfSense
//           </a>
//           <div className="w-full bg-white rounded-lg shadow dark:border md:mt-0 sm:max-w-md xl:p-0 dark:bg-gray-800 dark:border-gray-700">
//             <div className="p-6 space-y-4 md:space-y-6 sm:p-8">
//               <h1 className="text-xl font-bold leading-tight tracking-tight text-gray-900 md:text-2xl dark:text-white">
//                 Sign in to your account
//               </h1>
//               <form className="space-y-4 md:space-y-6" onSubmit={handleSubmit}>
//                 <div>
//                   <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Your email</label>
//                   <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} name="email" id="email" className="bg-gray-50 border border-gray-300 text-gray-900 rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" placeholder="name" />
//                 </div>
//                 <div>
//                   <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Password</label>
//                   <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} name="password" id="password" placeholder="••••••••" className="bg-gray-50 border border-gray-300 text-gray-900 rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" />
//                 </div>
//                 <button type="submit" disabled={loading} className="w-full text-white bg-primary-600 hover:bg-primary-700 focus:ring-4 focus:outline-none focus:ring-primary-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-primary-600 dark:hover:bg-primary-700 dark:focus:ring-primary-800">{loading ? 'Logging in...' : 'Login'}</button>
//                 <p className="text-sm font-light text-gray-500 dark:text-gray-400">
//                   Don’t have an account yet? <a href="#" className="font-medium text-primary-600 hover:underline dark:text-primary-500" onClick={() => goToRegister()}>Sign up</a>
//                 </p>
//                 {error && <p style={{ color: 'red' }}>{error}</p>}
//               </form>
//             </div>
//           </div>
//         </div>
//       </section>
//     </>
//   );
// }

// import { createGlobalState } from 'react-hooks-global-state';

// const initialState = { count: 0 };
// const { useGlobalState } = createGlobalState(initialState);
// const [count, setCount] = useGlobalState('count');

// setCount(v => v - 1);
// let saveJobsObj = await chrome.storage.local.get(["savejobs"]);

// await chrome.storage.local.set({
//   savejobs: saveJobsObj.savejobs - 1,
// });

// else{
//   toPushInTabHistory.reffererUrl = urlQueueLocal.urlQueue[tabId][urlQueueLocal.urlQueue[tabId].length - 1]
// }

// if(!tabhistory[tabhistory.length - 1].duration){
//   tabhistory[tabhistory.length - 1].duration = Date.now() - timeQueueLocal.timeQueue[tabId][timeQueueLocal.timeQueue[tabId].length - 1]
// }



// if (tabhistory.length === 0) {
//   toPushInTabHistory.duration = Date.now() - timeQueueLocal.timeQueue[tabId][timeQueueLocal.timeQueue[tabId].length - 1]
// }
// else {

// }

// const lastEntryTimeObj = await chrome.storage.local.get([
//   "lastEntryTime",
// ]);

// const autotrackerFlag = await chrome.storage.local.get(["autoTracker"]);
// // if (autotrackerFlag.autoTracker) {
// //   let urlQueue = await chrome.storage.local.get(["urlQueue"]);
// //   delete urlQueue.urlQueue[tabId];
// // }


// //When first entry
// if (tabhistory.length === 0) {
//   let urlQueue = await chrome.storage.local.get(["urlQueue"]);

//   if (autotrackerFlag.autoTracker) {
//     toPushInTabHistory.reffererUrl = "START";
//     try {
//       delete urlQueue.urlQueue[tabId];
//     } catch (error) {
//       console.log(error);
//     }
//   } else {

//     if (urlQueue.urlQueue[tabId].length >= 2) {
//       toPushInTabHistory.reffererUrl = urlQueue.urlQueue[tabId][urlQueue.urlQueue[tabId].length - 2];
//     } else {
//       toPushInTabHistory.reffererUrl = "START";
//     }

//   }
//   toPushInTabHistory.duration = Date.now() - lastEntryTimeObj.lastEntryTime[tabId];
//   tabhistory.push(toPushInTabHistory);
//   try {
//     webhistoryObj.webhistory.find(
//       (data: WebHistory) => data.tabsessionId === tab.id
//     ).tabHistory = tabhistory;
//     await chrome.storage.local.set({
//       webhistory: webhistoryObj.webhistory,
//     });
//   } catch (error) {
//     console.log(error);
//   }
// } else {
//   if (autotrackerFlag.autoTracker) {
//     toPushInTabHistory.reffererUrl = tabhistory[tabhistory.length - 1].url;
//   } else {
//     let urlQueue = await chrome.storage.local.get(["urlQueue"]);
//     toPushInTabHistory.reffererUrl = urlQueue.urlQueue[tabId][urlQueue.urlQueue[tabId].length - 2];
//   }
//   if (!tabhistory[tabhistory.length - 1].duration) {
//     toPushInTabHistory.duration = Date.now() - tabhistory[tabhistory.length - 1].entryTime
//   }
//   toPushInTabHistory.duration = Date.now() - lastEntryTimeObj.lastEntryTime[tabId];
//   tabhistory.push(toPushInTabHistory);

//   try {
//     webhistoryObj.webhistory.find(
//       (data: WebHistory) => data.tabsessionId === tab.id
//     ).tabHistory = tabhistory;
//     await chrome.storage.local.set({
//       webhistory: webhistoryObj.webhistory,
//     });
//   } catch (error) {
//     console.log(error);
//   }
// }
