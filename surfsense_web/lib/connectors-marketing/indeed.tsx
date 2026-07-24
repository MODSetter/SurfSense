import { IconBriefcase } from "@tabler/icons-react";
import type { ConnectorPageContent } from "./types";

export const indeed: ConnectorPageContent = {
	slug: "indeed",
	name: "Indeed",
	icon: IconBriefcase,

	metaTitle: "Indeed Scraper API for Jobs and Hiring Data | SurfSense",
	metaDescription:
		"Scrape public Indeed job postings with the SurfSense Indeed Scraper API: titles, companies, salaries, and full descriptions by search or company. No Indeed API. Start free.",
	keywords: [
		"indeed scraper",
		"indeed scraper api",
		"indeed api",
		"indeed jobs api",
		"scrape indeed",
		"indeed job scraper",
		"job posting scraper",
		"salary data api",
		"hiring data api",
		"indeed mcp",
		"labor market data",
		"recruiting data tool",
	],

	h1: "Indeed Scraper API for Job Postings and Hiring Data",
	heroLede:
		"The SurfSense Indeed API extracts public job postings, salaries, companies, and full descriptions by search query, company page, or job URL, without Indeed's official API. Give your AI agents a live feed of who is hiring, for what, at what pay, so you track the labor market as it moves.",

	transcript: {
		prompt: "Find remote data analyst roles posted this week and what they pay",
		toolCall:
			'indeed.scrape({ search_queries: ["data analyst"], location: "Remote",\n  remote: "remote", from_days: 7, sort: "date", max_items: 30 })',
		rows: [
			{
				primary: "Senior Data Analyst · Acme Corp",
				secondary: "Remote (US) · $120k–$145k/year · posted 2 days ago",
				tag: "salary listed",
			},
			{
				primary: "Data Analyst, Growth · Globex",
				secondary: "Remote · $95k–$110k/year · Indeed Apply",
				tag: "buying signal",
			},
			{
				primary: "Marketing Data Analyst · Initech",
				secondary: "Remote (US) · estimated $88k–$102k · posted today",
				tag: "new today",
			},
		],
		resultSummary: "30 jobs · 22 with salary · surfaced in 3.4s",
	},

	extractIntro:
		"Every call returns structured job items. Point the API at a search query, an Indeed search or company page, or a single job URL, and set scrape_job_details for the full description per job.",
	extractFields: [
		{
			label: "Job",
			description: "Title, job key, listing URL, apply URL, and whether Indeed Apply is enabled.",
		},
		{
			label: "Company",
			description: "Company name, profile URL, star rating, and review count where available.",
		},
		{
			label: "Location",
			description: "Formatted location, city, state, postal code, country, and remote or hybrid flags.",
		},
		{
			label: "Salary",
			description:
				"Pay text, min and max bounds, currency, period, and whether the figure is an Indeed estimate.",
		},
		{
			label: "Description",
			description:
				"Listing snippet by default; the full text and HTML description with scrape_job_details.",
		},
		{
			label: "Signals",
			description:
				"Job types, benefits, sponsored, urgently hiring, new, and expired flags, plus post age.",
		},
	],

	useCasesHeading: "What teams do with the Indeed API",
	useCases: [
		{
			title: "Competitor hiring intelligence",
			description:
				"Track what your competitors are hiring for and where. A spike in sales or ML roles is a roadmap signal months before it ships. Feed the stream to an agent that flags the moves that matter.",
		},
		{
			title: "Salary and compensation benchmarking",
			description:
				"Pull real posted salaries for a title in a location and benchmark your own bands against the live market, instead of a survey that is a year stale.",
		},
		{
			title: "Labor market and sector research",
			description:
				"Measure hiring demand for a role, skill, or sector over time. Turn thousands of postings into a demand index your analysts and clients can act on.",
		},
		{
			title: "Recruiting and lead sourcing",
			description:
				"Find companies actively hiring for a role and reach them while the need is hot. Job postings are a public, timely buying signal for staffing and B2B sales.",
		},
	],

	comparison: {
		heading: "An Indeed API alternative built for agents",
		intro:
			"Indeed retired its public Publisher jobs API and gates data behind partner programs. If you cannot get access or need clean structured jobs now, here is how SurfSense compares.",
		columnLabel: "DIY Indeed scraping",
		rows: [
			{
				feature: "Access",
				official: "Publisher API retired; partner-gated and approval-only",
				surfsense: "One API key; scrape public postings without an approval process",
			},
			{
				feature: "Anti-bot",
				official: "You fight Cloudflare, fingerprinting, and CAPTCHAs yourself",
				surfsense: "Warmed, rotated sessions managed for you; no proxy plumbing",
			},
			{
				feature: "Pricing",
				official: "Proxy, browser, and maintenance costs you own",
				surfsense: "Pay per job returned, with a free tier to start",
			},
			{
				feature: "Descriptions",
				official: "Extra page fetch and parsing you build and maintain",
				surfsense: "Full description per job with one scrape_job_details flag",
			},
			{
				feature: "Agent-ready",
				official: "No; you build the harness yourself",
				surfsense: "MCP server exposes indeed.scrape as a native tool",
			},
		],
	},

	api: {
		platform: "indeed",
		verb: "scrape",
		mcpTool: "indeed.scrape",
		requestBody: {
			search_queries: ["data analyst"],
			location: "Remote",
			remote: "remote",
			from_days: 7,
			sort: "date",
			max_items: 30,
		},
	},

	schema: {
		requestNote:
			"Provide at least one source: urls or search_queries. Up to 20 sources per call.",
		request: [
			{
				name: "urls",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Indeed URLs: a search page (/jobs?q=&l=), a company jobs page (/cmp/<slug>/jobs), or a single job (/viewjob?jk=...). Max 20.",
			},
			{
				name: "search_queries",
				type: "string[]",
				defaultValue: "[]",
				description:
					"Job search terms. Each returns up to max_items_per_query results, shaped by the filters below. Max 20.",
			},
			{
				name: "country",
				type: "string",
				defaultValue: '"us"',
				description: "Country code selecting the Indeed domain, e.g. 'us', 'gb', 'de'.",
			},
			{
				name: "location",
				type: "string",
				description: "Where to search, e.g. 'Remote', 'New York, NY'.",
			},
			{
				name: "radius",
				type: "integer",
				description: "Search radius in miles or km around location.",
			},
			{
				name: "job_type",
				type: "string",
				description: "Employment type: fulltime, parttime, contract, internship, and more.",
			},
			{
				name: "level",
				type: "string",
				description: "Experience level: entry_level, mid_level, or senior_level.",
			},
			{
				name: "remote",
				type: "string",
				description: "Work model filter: remote or hybrid.",
			},
			{
				name: "from_days",
				type: "integer",
				description: "Only return jobs posted within the last N days.",
			},
			{
				name: "sort",
				type: "string",
				defaultValue: '"relevance"',
				description: "Result ordering: relevance or date.",
			},
			{
				name: "scrape_job_details",
				type: "boolean",
				defaultValue: "false",
				description:
					"Fetch each job's detail page for the full description. Slower: one extra page load per job.",
			},
			{
				name: "max_items",
				type: "integer",
				defaultValue: "25",
				description: "Max total jobs to return across all sources. 1 to 100.",
			},
			{
				name: "max_items_per_query",
				type: "integer",
				defaultValue: "25",
				description: "Max jobs to pull per search or company target.",
			},
		],
		responseNote:
			"The response is { items: [...] } with one flat item per job. Fields Indeed omits are null. One returned job is one billable unit.",
		response: [
			{
				name: "jobKey / jobUrl / applyUrl",
				type: "string",
				description: "Indeed job key, listing URL, and third-party apply URL.",
			},
			{
				name: "title",
				type: "string",
				description: "The job title as posted.",
			},
			{
				name: "company / companyUrl",
				type: "string",
				description: "Company name and its Indeed profile URL.",
			},
			{
				name: "companyRating / companyReviewCount",
				type: "number / integer",
				description: "Employer star rating and number of reviews, where Indeed shows them.",
			},
			{
				name: "formattedLocation / isRemote / remoteType",
				type: "string / boolean",
				description: "Location string plus remote and hybrid flags.",
			},
			{
				name: "salary",
				type: "object",
				description:
					"salaryText, salaryMin, salaryMax, currency, period, and isEstimated when the pay is an Indeed estimate.",
			},
			{
				name: "jobTypes / benefits",
				type: "string[]",
				description: "Employment types and listed benefits parsed from the posting.",
			},
			{
				name: "descriptionText / descriptionHtml",
				type: "string",
				description: "Snippet by default; the full description when scrape_job_details is set.",
			},
			{
				name: "sponsored / urgentlyHiring / isNew / expired",
				type: "boolean",
				description: "Listing flags for ranking and filtering.",
			},
			{
				name: "age / datePublished / scrapedAt",
				type: "string",
				description: "Relative post age, ISO publish date, and when the job was scraped.",
			},
		],
	},

	faq: [
		{
			question: "Is scraping Indeed legal?",
			answer:
				"SurfSense reads only public Indeed job postings, the same listings any logged-out visitor can see. It never logs in and cannot access private or applicant data. As always, review Indeed's terms and your own compliance needs before you run at scale.",
		},
		{
			question: "Does Indeed have an official jobs API?",
			answer:
				"Indeed retired its public Publisher jobs API and now gates job data behind partner and approval programs. SurfSense is an independent alternative: you call one API, or add the MCP server to your agent, and get structured public postings back.",
		},
		{
			question: "Can I get the full job description?",
			answer:
				"Yes. By default each job returns the listing snippet, which is fast. Set scrape_job_details to true and SurfSense fetches each job's detail page for the full description text and HTML, at the cost of one extra page load per job.",
		},
		{
			question: "What are the rate limits?",
			answer:
				"Each call returns up to 100 jobs across all sources, with up to 20 URLs or search queries per request. SurfSense manages the anti-bot request budget for you, so you scale reads without running proxies or a headless browser yourself.",
		},
	],

	related: [
		{ label: "Reddit API", href: "/reddit" },
		{ label: "YouTube API", href: "/youtube" },
		{ label: "Google Maps API", href: "/google-maps" },
		{ label: "SERP API", href: "/google-search" },
		{ label: "Web Crawl API", href: "/web-crawl" },
		{ label: "SurfSense MCP Server", href: "/mcp-server" },
	],
};
