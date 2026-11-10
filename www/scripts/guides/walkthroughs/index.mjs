/** Every walkthrough, in the order a new user meets them: each one starts where the one before it left the app. */

import { addFromTheWeb } from "./add-from-the-web.mjs";
import { addSources } from "./add-sources.mjs";
import { askAndCite } from "./ask-and-cite.mjs";
import { connectAServer } from "./connect-a-server.mjs";
import { images } from "./images.mjs";
import { localModel } from "./local-model.mjs";
import { organiseSources } from "./organise-sources.mjs";
import { pickSources } from "./pick-sources.mjs";
import { podcast } from "./podcast.mjs";
import { refineAndVersions } from "./refine-and-versions.mjs";
import { setUp } from "./set-up.mjs";
import { studioDocuments } from "./studio-documents.mjs";
import { studyMaterials } from "./study-materials.mjs";
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
	studioDocuments,
	studyMaterials,
	refineAndVersions,
	podcast,
	images,
	organiseSources,
];
