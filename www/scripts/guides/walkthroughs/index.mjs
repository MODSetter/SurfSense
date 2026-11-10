/** Every walkthrough, in the order a new user meets them: each one starts where the one before it left the app. */

import { addFromTheWeb } from "./add-from-the-web.mjs";
import { addSources } from "./add-sources.mjs";
import { agentDocuments } from "./agent-documents.mjs";
import { analyseASpreadsheet } from "./analyse-a-spreadsheet.mjs";
import { askAndCite } from "./ask-and-cite.mjs";
import { businessTrial } from "./business-trial.mjs";
import { connectAServer } from "./connect-a-server.mjs";
import { contractRedline } from "./contract-redline.mjs";
import { images } from "./images.mjs";
import { localModel } from "./local-model.mjs";
import { organiseSources } from "./organise-sources.mjs";
import { pdfTools } from "./pdf-tools.mjs";
import { pickSources } from "./pick-sources.mjs";
import { plugins } from "./plugins.mjs";
import { podcast } from "./podcast.mjs";
import { privacyNetwork } from "./privacy-network.mjs";
import { refineAndVersions } from "./refine-and-versions.mjs";
import { securityQuestionnaire } from "./security-questionnaire.mjs";
import { setUp } from "./set-up.mjs";
import { studioDocuments } from "./studio-documents.mjs";
import { studyMaterials } from "./study-materials.mjs";
import { trackedChanges } from "./tracked-changes.mjs";
import { transcribeARecording } from "./transcribe-a-recording.mjs";
import { updates } from "./updates.mjs";
import { voiceInput } from "./voice-input.mjs";
import { webResearch } from "./web-research.mjs";
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
	agentDocuments,
	trackedChanges,
	analyseASpreadsheet,
	pdfTools,
	webResearch,
	plugins,
	transcribeARecording,
	voiceInput,
	privacyNetwork,
	updates,
	businessTrial,
	securityQuestionnaire,
	contractRedline,
];
