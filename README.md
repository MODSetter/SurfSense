

![header](https://github.com/user-attachments/assets/f5faf53e-799f-43dd-9470-6695bf2dea3e)


# SurfSense

Well when I’m browsing the internet, I tend to save a ton of content—but remembering when and what you saved? Total brain freeze! ❄️ That’s where SurfSense comes in. SurfSense is like a Knowledge Graph 🧠 Brain 🧠 for anything you see ( 📱 Social Media Chats, 📅Calender Invites, 📧 Important Mails, ⚓ Tutorials, 😋 Recipies and anything ) on the World Wide Web. Now, you’ll never forget any browsing session. Easily capture your web browsing session and desired webpage content using an easy-to-use Chrome extension. Then, ask your personal knowledge base anything about your saved content., and voilà—instant recall! 🧑‍💻🌐

# Video



https://github.com/user-attachments/assets/dd63bb04-6061-4331-a8e6-32a1a20bd350



## Key Features

- 💡 **Idea**: Save any content you see on the internet in your own Knowledge Graph.
- 🔍 **Powerful Search**: Quickly find anything in your Web Browsing Sessions.
- 💬 **Chat with your Web History**: Interact in Natural Language with your saved Web Browsing Sessions.
- 🏠 **Self Hostable**: Open source and easy to deploy locally.
- 📊 **Use GraphRAG**: Utilize the power of GraphRAG to find meaningful relations in your saved content.
- 🔟% **Cheap On Wallet**: Works Flawlessly with OpenAI gpt-4o-mini model.
- 🕸️ **No WebScraping**: Extension directly reads the data from DOM.

## How to get started?

Before we begin, we need to set up our Neo4j Graph Database. This is where SurfSense stores all your saved information. For a quick setup, I suggest getting your free Neo4j Aura DB from [https://neo4j.com/cloud/platform/aura-graph-database/](https://neo4j.com/cloud/platform/aura-graph-database/) or setting it up locally.

After obtaining your Neo4j credentials, make sure to get your OpenAI API Key from [https://platform.openai.com/](https://platform.openai.com/).

1. Register Your SurfSense account at https://www.surfsense.net/signup
2. Download SurfSense Extension from https://chromewebstore.google.com/detail/surfsense/jihmihbdpfjhppdlifphccgefjhifblf

Now you are ready to use SurfSense. Start by first logging into the Extension.

When you start the extension you should see a Login page like this

![extension login](https://i.ibb.co/qkkR5Lt/extlogin.png)



After logging in you will need to fill your Neo4j Credentials & OpenAPI Key.

![settings](https://i.ibb.co/j5PT171/extreqvalues.png)



After Saving you should be able to use extension now.

![main](https://i.ibb.co/pvHCDSb/extmain.png)

|Options|Explanations|
|--|--|
| Clear Inactive History Sessions | It clears the saved content for Inactive Tab Sessions.  |
| Save Current Webpage Snapshot | Stores the current webpage session info into SurfSense history store|
| Save to SurfSense | Processes the SurfSense History Store & Initiates a Save Job |

4. Now just start browsing the Internet. Whatever you want to save any content take its Snapshot and save it to SurfSense. After Save Job is completed you are ready to ask anything about it to your Knowledge Graph Brain 🧠.
5. Now go to SurfSense Chat Options at https://www.surfsense.net/chat & fill the Neo4j Credentials & OpenAPI Key if asked.

![newchatwindow](https://github.com/user-attachments/assets/71cfabdb-b6ee-403e-9f74-53eef026064c)


|OPTIONS|DESCRIPTION|
|--|--|
| Precision Chat | Used for detailed search and chatting with your saved web sessions and their content. |
| General Chat | Used for general questions about your content. Doesn't work well with Dates & Time.|

### Chat Screenshots
---
#### PRECISION

##### Search

![precision search](https://github.com/user-attachments/assets/88d32490-e8e8-4aec-bff4-8c3c42dc0e86)


##### Results

![pretable](https://github.com/user-attachments/assets/a4f90b6b-a455-43ee-85fa-1f74514b5854)


##### Multi Webpage Chat


![multichat](https://github.com/user-attachments/assets/57753233-23d6-4e59-a693-0380429f0987)

---

#### GENERAL
As an example lets visit : https://myanimelist.net/anime/season (Summer 2024 Anime atm) and save it to SurfSense.

Now lets ask SurfSense "Give list of summer 2024 animes with images."

Sample Response:

![res](https://i.ibb.co/k23FHzs/frontres.png)

Now Let's ask it more information about our related session.

![more](https://i.ibb.co/PWzM97G/front-more-info.png)

Sample More Description Response:

![res](https://i.ibb.co/cYtWJbB/more-info-out.png)

  



### Local Setup Guide

#### Backend

For authentication purposes, you’ll also need a PostgreSQL instance running on your machine.

Now lets setup the SurfSense BackEnd
1. Clone this repo.
2. Go to ./backend subdirectory.
3. Setup Python Virtual Enviroment
4. Run `pip install -r requirements.txt` to install all required dependencies.
5. Update the required Environment variables in envs.py
 
|ENV VARIABLE|Description  |
|--|--|
| POSTGRES_DATABASE_URL | postgresql+psycopg2://user:pass@host:5432/database|
| API_SECRET_KEY | Can be any Random String value. Make Sure to remember it for as you need to send it in request to Backend for security purposes.|


6. Backend is a FastAPI Backend so now just run the server on unicorn using command `uvicorn server:app --host 0.0.0.0 --port 8000`
7. If everything worked fine you should see screen like this.

![backend](https://i.ibb.co/542Vhqw/backendrunning.png)

---

#### Extension

After Setting up the BackEnd Lets do a quick build of the extension.

1. Go to ./extension subdirectory.
2. Run `pnpm i` to install required dependencies.
3. Update Env variables at `./src/env.tsx`

|ENV VARIABLE|DESCRIPTION|
|--|--|
| API_SECRET_KEY | Same String value your set for Backend |
| BACKEND_URL | Give hosted backend url here. Eg. `http://127.0.0.1:8000`|

4. Run `pnpm run build` to build your extension. Build will be generated in `./dist` folder
5. Enable Developer Mode in Chrome and load the extinction from `./dist` folder.
6. Extension will load successfully.

Now resister a quick user through Swagger API > Try it Out: http://127.0.0.1:8000/docs#/default/register_user_register_post

Make Sure in request body `"apisecretkey"` value is same value as `API_SECRET_KEY` we been assigning.

---

#### FrontEnd

For local frontend setup just fill out the `.env` file of frontend.

|ENV VARIABLE|DESCRIPTION|
|--|--|
| NEXT_PUBLIC_API_SECRET_KEY | Same String value your set for Backend & Extension |
| NEXT_PUBLIC_BACKEND_URL | Give hosted backend url here. Eg. `http://127.0.0.1:8000`|
| NEXT_PUBLIC_RECAPTCHA_SITE_KEY | Google Recaptcha v2 Client Key |
| RECAPTCHA_SECRET_KEY | Google Recaptcha v2 Server Key|

and run it using `pnpm run dev`

You should see your Next.js frontend running at `localhost:3000`

---


##  Tech Stack

 - **Extenstion** : Chrome Manifest v3
 - **BackEnd** : FastAPI with LangChain
 - **FrontEnd**: Next.js with Aceternity.

#### Architecture:
In Progress...........

## Future Work
- Generalize the way SurfSense uses Graphs. Will soon make an integration with FalkorDB soon.
- Saving Chats
- Basic keyword search page for saved sessions **[Done]**
- Multi & Single Document Chat **[Done]**
- Implement some tricks from GraphRAG papers to optimize current GraphRAG logic. 

## Contribute 

Contributions are very welcome! A contribution can be as small as a ⭐ or even finding and creating issues.
Fine-tuning the Backend is always desired.

