/** Every walkthrough, in the order a new user meets them: each one starts where the one before it left the app. */

import { addFromTheWeb } from "./add-from-the-web.mjs";
import { addSources } from "./add-sources.mjs";
import { askAndCite } from "./ask-and-cite.mjs";
import { connectAServer } from "./connect-a-server.mjs";
import { localModel } from "./local-model.mjs";
import { pickSources } from "./pick-sources.mjs";
import { setUp } from "./set-up.mjs";
import { workspaces } from "./workspaces.mjs";

export const WALKTHROUGHS = [
	setUp,
	localModel,
	connectAServer,
	addSources,
	askAndCite,
	pickSources,
	addFromTheWeb,
	workspaces,
];
