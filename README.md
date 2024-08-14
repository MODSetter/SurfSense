
![header](https://github.com/user-attachments/assets/f5faf53e-799f-43dd-9470-6695bf2dea3e)


# SurfSense

When I’m browsing the internet, I tend to save a ton of content—but remembering when and what you saved? Total brain freeze! ❄️ That’s where SurfSense comes in. SurfSense is like a Knowledge Graph 🧠 Brain 🧠 for anything you see on the World Wide Web. Now, you’ll never forget any browsing session. Just ask your personal knowledge base anything about your saved content, and voilà—instant recall! 🧑‍💻🌐

# Video


https://github.com/user-attachments/assets/08b650ed-d84b-441b-a0e1-cf9f06431bf4



## Key Features

- 💡 **Idea**: Save any content you see on the internet in your own Knowledge Graph.
- 🔍 **Powerful Search**: Quickly find anything in your Web Browsing Sessions.
- 💬 **Chat with your Web History**: Interact in Natural Language with your saved Web Browsing Sessions.
- 🏠 **Self Hostable**: Open source and easy to deploy locally.
- 📊 **Use GraphRAG**: Utilize the power of GraphRAG to find meaningful relations in your saved content.
- 🔟% **Cheap On Wallet**: Works Flawlessly with OpenAI gpt-4o-mini model.
- 🕸️ **No WebScraping**: Extension directly reads the data from dom.

## How to get started?

Since the official Chrome extension for SurfSense is still under review, you'll need to set up the SurfSense Backend and SurfSense extension yourself for now. Don’t worry, it’s dead simple—just change a few environment variables, and you’ll be ready to go.

Before we begin, we need to set up our Neo4j Graph Database. This is where SurfSense stores all your saved information. For a quick setup, I suggest getting your free Neo4j Aura DB from [https://neo4j.com/cloud/platform/aura-graph-database/](https://neo4j.com/cloud/platform/aura-graph-database/) or setting it up locally.

After obtaining your Neo4j credentials, make sure to get your OpenAI API Key from [https://platform.openai.com/](https://platform.openai.com/).

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

After Setting up the BackEnd Lets do a quick build of the extension.

1. Go to ./extension subdirectory.
2. Run `pnpm i` to install required dependencies.
3. Update Env variables at `./src/env.tsx`

|ENV VARIABLE|Description  |
|--|--|
| API_SECRET_KEY | Same String value your set for Backend |
| BACKEND_URL | Give hosted backend url here. Eg. `http://127.0.0.1:8000`|

4. Run `pnpm run build` to build your extension. Build will be generated in `./dist` folder
5. Enable Developer Mode in Chrome and load the extinction from `./dist` folder.
6. Extension will load successfully.

Now resister a quick user through Swagger API > Try it Out: http://127.0.0.1:8000/docs#/default/register_user_register_post

Make Sure in request body `"apisecretkey"` value is same value as `API_SECRET_KEY` we been assigning.

---

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

---
Now just start browsing the Internet. Whatever you want to save any content take its Snapshot and save it to SurfSense. After Save Job is completed you are ready to ask anything about it to your Knowledge Graph Brain 🧠.

If you don't want to deal with frontend local setup you can quickly go to https://www.surfsense.net/ and start interacting with your Knowledge Graph Brain 🧠.
Just login to SurfSense at https://www.surfsense.net/login using these demo credentials
|key|val|
|--|--|
| Username | test  |
| Password | test|

and then set the credentials of Neo4j & OpenAPI in https://www.surfsense.net/settings.

---

For local frontend setup just fill out the `.env` file of frontend.

|ENV VARIABLE|Description  |
|--|--|
| NEXT_PUBLIC_API_SECRET_KEY | Same String value your set for Backend & Extension |
| NEXT_PUBLIC_BACKEND_URL | Give hosted backend url here. Eg. `http://127.0.0.1:8000`|
| NEXT_PUBLIC_RECAPTCHA_SITE_KEY | Google Recaptcha v2 Client Key |
| RECAPTCHA_SECRET_KEY | Google Recaptcha v2 Server Key|

and run it using `pnpm run dev`

---

After that just go to https://www.surfsense.net/chat and start interacting.
As an example lets visit : https://myanimelist.net/anime/season (Summer 2024 Anime atm) and save it to SurfSense.

Now lets ask SurfSense "Give list of summer 2024 animes with images."

Sample Response:

![res](https://i.ibb.co/k23FHzs/frontres.png)

Now Let's ask it more information about our related session.

![more](https://i.ibb.co/PWzM97G/front-more-info.png)

Sample More Description Response:

![res](https://i.ibb.co/cYtWJbB/more-info-out.png)

  

##  Tech Stack

 - **Extenstion** : Chrome Manifest v3
 - **BackEnd** : FastAPI with LangChain
 - **FrontEnd**: Next.js with Aceternity.

#### Architecture:
In Progress...........



## Contribute 

Contributions are very welcome! A contribution can be as small as a ⭐ or even finding and creating issues.
Fine-tuning the Backend is always desired.

