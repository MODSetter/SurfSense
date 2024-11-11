

![header](https://github.com/user-attachments/assets/90f5ae85-94c4-4119-bbb4-8c3f308b7e39)



# SurfSense
While tools like NotebookLM and Perplexity are impressive and highly effective for conducting research on any topic, imagine having both at your disposal with complete privacy control. That's exactly what SurfSense offers. With SurfSense, you can create your own knowledge base for research, similar to NotebookLM, or easily research the web just like Perplexity. SurfSense also includes an effective cross-browser extension to directly save dynamic content bookmarks, such as social media chats, calendar invites, important emails, tutorials, recipes, and more to your SurfSense knowledge base. Now, you’ll never forget anything and can easily research everything.

# Video


https://github.com/user-attachments/assets/1105b5f6-3030-43e9-9f83-2df980eb2140








## Key Features

- 💡 **Idea**: Have your own private NotebookLM and Perplexity with better  integrations.
- ⚙️ **Cross Browser Extension**: Save your dynamic content bookmarks from your favourite browser.
- 📁 **Multiple File Format Uploading Support**: Save content from your own personal files(Documents, images and more) to your own personal knowledge base .
- 🔍 **Powerful Search**: Quickly research or find anything in your saved content.
- 💬 **Chat with your Saved Content**: Interact in Natural Language with your saved Web Browsing Sessions and get cited answers.
- 🎤 **Podcasts your Saved Content**: Create podcasts over your saved content in SurfSense knowledge base.
- 📄 **Cited Answers**: Get Cited answers just like Perplexity.
- 🔔 **Local LLM Support**: Works Flawlessly with Ollama local LLMs.
- 🏠 **Self Hostable**: Open source and easy to deploy locally.
- 📊 **Advanced RAG Techniques**: Utilize the power of Hierarchical Indices RAG.
- 🔟% **Cheap On Wallet**: Works Flawlessly with OpenAI gpt-4o-mini model and Ollama local LLMs.
- 🕸️ **No WebScraping**: Extension directly reads the data from DOM to get accurate data.


## CHANGELOG

**UPDATE 11 NOVEMBER 2024:** 
- Too many changes just fully rebranded it for better direction.
- SurfSense is now A Personal NotebookLM and Perplexity-like AI Assistant for Everyone.

all at https://github.com/MODSetter/SurfSense/blob/main/CHANGELOGs.md


## How to get started?

### PRE-START NOTE's

#### File Uploading Support

SurfSense now supports uploading various file types. To enable this feature, please set up the Unstructured.io library + its prerequisites. You can follow the setup guide here: https://github.com/Unstructured-IO/unstructured?tab=readme-ov-file#installing-the-library

#### Podcast Support

Make sure you correctly setup `ffmpeg`  in your system so mering of audios can happen.

---

### Docker Setup

1. Setup `SurfSense-Frontend/.env` and `backend/.env`
2. Run `docker-compose build --no-cache`.
3. After building image run `docker-compose up -d`
4. Now connect the extension with docker live backend url by updating `ss-cross-browser-extension/.env` and building it.


---
### Backend

For authentication purposes, you’ll also need a PostgreSQL instance running on your machine.

Now lets setup the SurfSense BackEnd
1. Clone this repo.
2. Go to ./backend subdirectory.
3. Setup Python Virtual Environment
4. Run `pip install -r requirements.txt` to install all required dependencies.
5. Update/Make the required Environment variables in `.env` following the `.env.example`
6. Backend is a FastAPI Backend so now just run the server on unicorn using command `uvicorn server:app --host 0.0.0.0 --port 8000`
7. If everything worked fine you should see screen like this.

![backend](https://i.ibb.co/542Vhqw/backendrunning.png)

---

### FrontEnd

For local frontend setup just fill out the `.env` file of frontend.

|ENV VARIABLE|DESCRIPTION|
|--|--|
| NEXT_PUBLIC_API_SECRET_KEY | Same String value your set for Backend |
| NEXT_PUBLIC_BACKEND_URL | Give hosted backend url here. Eg. `http://127.0.0.1:8000`|
| NEXT_PUBLIC_RECAPTCHA_SITE_KEY | Google Recaptcha v2 Client Key |
| RECAPTCHA_SECRET_KEY | Google Recaptcha v2 Server Key|

and run it using `pnpm run dev`

You should see your Next.js frontend running at `localhost:3000`

**Make sure to register an account from frontend so you can login to extension.**

---

### Extension

Extension is in plasmo framework which is a cross browser extension framework.

For building extension just fill out the `.env` file of frontend.

|ENV VARIABLE|DESCRIPTION|
|--|--|
| PLASMO_PUBLIC_BACKEND_URL| SurfSense Backend URL eg. "http://127.0.0.1:8000" |

Build the extension for your favorite browser using this guide: https://docs.plasmo.com/framework/workflows/build#with-a-specific-target 

When you load and start the extension you should see a Login page like this

![extlogin](https://github.com/user-attachments/assets/e69af4ed-9477-4cd5-9ec7-ad2efb1bec9a)


After logging in you should be able to use extension now.

![extmain](https://github.com/user-attachments/assets/86903ff2-7672-4010-8fb8-88c228cf05e3)


|Options|Explanations|
|--|--|
| Search Space | Search Space to save your dynamic bookmarks.  |
| Clear Inactive History Sessions | It clears the saved content for Inactive Tab Sessions.  |
| Save Current Webpage Snapshot | Stores the current webpage session info into SurfSense history store|
| Save to SurfSense | Processes the SurfSense History Store & Initiates a Save Job |



## Screenshots

![searchspacemain](https://github.com/user-attachments/assets/4941dadf-8dd6-45d8-8d62-20342d5f76a0)

---

![mainchat](https://github.com/user-attachments/assets/b2ceb449-df98-47e8-90c5-ddc84a1979b7)

---

![chat](https://github.com/user-attachments/assets/2f639710-31a4-4e54-90ae-9117a29b2d1a)


##  Tech Stack

 - **Extension** : Manifest v3 on Plasmo
 - **BackEnd** : FastAPI with LangChain
 - **FrontEnd**: Next.js with Aceternity.

#### Architecture:
In Progress...........

## Future Work
- Implement Canvas. 
- Complete Hybrid Search.
- Add support for file uploads QA. **[Done]**
- Shift to WebSockets for Streaming responses. **[Done]**
- Based on feedback, I will work on making it compatible with local models. **[Done]**
- Cross Browser Extension **[Done]**
- Critical Notifications **[Done | PAUSED]**
- Saving Chats **[Done]**
- Basic keyword search page for saved sessions **[Done]**
- Multi & Single Document Chat **[Done]**


## Contribute 

Contributions are very welcome! A contribution can be as small as a ⭐ or even finding and creating issues.
Fine-tuning the Backend is always desired.

