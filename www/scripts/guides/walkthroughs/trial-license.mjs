/**
 * The Business trial the jobs guides show. A capture issues no license, so the
 * walkthroughs answer the app's license routes themselves, which also keeps a
 * real licensee's address off a public page. The jobs run because the capture
 * sets the backend's development switch, SURFSENSE_LOCAL_JOBS_UNLOCKED.
 */

const DAY_MS = 24 * 60 * 60 * 1000;

/** Every Business license and trial carries both jobs' codes (ADR 0086). */
export const TRIAL_LICENSE = {
	state: "active",
	plan: "trial",
	email: "you@example.com",
	expiry: new Date(Date.now() + 14 * DAY_MS).toISOString(),
	max_users: null,
	firm: "Example Tax & Accounting, LLC",
	jobs: ["JOB_QUESTIONNAIRE", "JOB_CONTRACT_REDLINE"],
};

/** The backend's answer while the license server is off in Settings › Network. */
const LICENSE_SERVER_OFF = {
	detail: {
		code: "egress_disabled",
		message: "Allow api.surfsense.com in Settings › Network.",
		destination: "host:api.surfsense.com",
		host: "api.surfsense.com",
		hosts: ["api.surfsense.com"],
		purpose: "job_packs",
	},
};

function corsHeaders(route) {
	return { "access-control-allow-origin": route.request().headers().origin ?? "*" };
}

/**
 * Answers the license routes as the trial would. With `licensed: false` the app
 * starts with no license and gets the trial when the walkthrough adds its file.
 * Its jobs download then answers as it would with that file on the backend:
 * refused until the license server is allowed, then each job whose pack the
 * capture installed at start.
 */
export async function answerAsTrial(page, apiUrl, { licensed = true } = {}) {
	let active = licensed;
	await page.route("**/license/status", (route) =>
		active ? route.fulfill({ json: TRIAL_LICENSE, headers: corsHeaders(route) }) : route.continue()
	);
	await page.route("**/license", (route) => {
		if (route.request().method() !== "PUT") return route.continue();
		active = true;
		return route.fulfill({ json: TRIAL_LICENSE, headers: corsHeaders(route) });
	});
	// A new license's plugin check would send the plugin server a key it never issued.
	await page.route("**/plugins/license/check*", (route) =>
		route.fulfill({ status: 204, headers: corsHeaders(route) })
	);

	const serverOn = async () => {
		const destinations = await (await fetch(`${apiUrl}/egress`)).json();
		return destinations.some((each) => each.host === "api.surfsense.com" && each.enabled);
	};
	await page.route("**/job-packs/download", async (route) => {
		if (route.request().method() !== "POST") return route.continue();
		if (!(await serverOn())) {
			return route.fulfill({ status: 403, json: LICENSE_SERVER_OFF, headers: corsHeaders(route) });
		}
		const packs = await (await fetch(`${apiUrl}/job-packs`)).json();
		// Each job the trial carries whose pack the capture installed, as a first download would.
		const outcomes = TRIAL_LICENSE.jobs.flatMap((entitlement) => {
			const pack = packs.find((each) => each.jobs.some((job) => job.entitlement === entitlement));
			return pack
				? [{ entitlement, outcome: "installed", message: "", version: pack.version, detail: null }]
				: [];
		});
		return route.fulfill({ json: { packs, outcomes }, headers: corsHeaders(route) });
	});
}
