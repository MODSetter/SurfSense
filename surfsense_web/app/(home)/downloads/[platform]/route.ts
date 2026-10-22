import { after } from "next/server";
import { installerRedirect } from "./installer-redirect";
import { getPublishedInstallers } from "./published-installers";
import { recordInstallerDownload } from "./record-installer-download";

/**
 * `/downloads/<platform>?src=&v=`: count the download, then 302 to the
 * installer on GitHub. The bytes never pass through here (a function response
 * is capped far below an installer's size). Every link outside the app points
 * here: the /downloads grid, the READMEs and the licence email.
 */

const redirect = installerRedirect({
	publishedInstallers: getPublishedInstallers,
	recordDownload: recordInstallerDownload,
	afterResponse: after,
});

export const GET = redirect.GET;
export const HEAD = redirect.HEAD;
