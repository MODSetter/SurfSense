import { intl } from "@/i18n/intl"

import type { GuideSlug } from "./guide-links"

export type Guide = { slug: GuideSlug; title: () => string }

export type GuideArea = { key: string; title: () => string; guides: Guide[] }

// The guides hub's groups and titles on surfsense.com, in its order
// (www/content/docs/v2/guides/meta.json). The pages themselves are English.
export const GUIDE_AREAS: readonly GuideArea[] = [
  {
    key: "get-started",
    title: () =>
      intl.formatMessage({
        id: "guides_dialog_get_started_title",
        defaultMessage: "Get started",
      }),
    guides: [
      {
        slug: "set-up",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_set_up_link",
            defaultMessage: "Set up SurfSense",
          }),
      },
      {
        slug: "local-model",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_local_model_link",
            defaultMessage: "Run a model on your computer",
          }),
      },
      {
        slug: "connect-a-server",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_connect_a_server_link",
            defaultMessage: "Use a model from a server or provider",
          }),
      },
    ],
  },
  {
    key: "sources-and-chat",
    title: () =>
      intl.formatMessage({
        id: "guides_dialog_sources_and_chat_title",
        defaultMessage: "Sources and chat",
      }),
    guides: [
      {
        slug: "add-sources",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_add_sources_link",
            defaultMessage: "Add files and folders",
          }),
      },
      {
        slug: "ask-and-cite",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_ask_and_cite_link",
            defaultMessage: "Ask a question and check its citations",
          }),
      },
      {
        slug: "pick-sources",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_pick_sources_link",
            defaultMessage: "Choose which sources to use",
          }),
      },
      {
        slug: "add-from-the-web",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_add_from_the_web_link",
            defaultMessage: "Add web pages and YouTube videos",
          }),
      },
      {
        slug: "organise-sources",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_organise_sources_link",
            defaultMessage: "Organise sources: notes, folders and previews",
          }),
      },
      {
        slug: "workspaces",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_workspaces_link",
            defaultMessage: "Keep projects apart with workspaces",
          }),
      },
    ],
  },
  {
    key: "studio",
    title: () =>
      intl.formatMessage({
        id: "guides_dialog_studio_title",
        defaultMessage: "Studio",
      }),
    guides: [
      {
        slug: "studio-documents",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_studio_documents_link",
            defaultMessage: "Make a Word document, deck or PDF in Studio",
          }),
      },
      {
        slug: "study-materials",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_study_materials_link",
            defaultMessage: "Make flashcards, a quiz and a mind map",
          }),
      },
      {
        slug: "podcast",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_podcast_link",
            defaultMessage: "Turn your sources into a podcast",
          }),
      },
      {
        slug: "refine-and-versions",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_refine_and_versions_link",
            defaultMessage: "Refine a document and open an earlier version",
          }),
      },
      {
        slug: "images",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_images_link",
            defaultMessage: "Make and edit images and infographics",
          }),
      },
    ],
  },
  {
    key: "agent-and-plugins",
    title: () =>
      intl.formatMessage({
        id: "guides_dialog_agent_and_plugins_title",
        defaultMessage: "Agent and plugins",
      }),
    guides: [
      {
        slug: "agent-documents",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_agent_documents_link",
            defaultMessage: "Have the agent write a report or a deck",
          }),
      },
      {
        slug: "tracked-changes",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_tracked_changes_link",
            defaultMessage: "Edit your own Word file with tracked changes",
          }),
      },
      {
        slug: "analyse-a-spreadsheet",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_analyse_a_spreadsheet_link",
            defaultMessage: "Analyse a spreadsheet and chart it",
          }),
      },
      {
        slug: "pdf-tools",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_pdf_tools_link",
            defaultMessage: "Merge, split, stamp and fill PDFs",
          }),
      },
      {
        slug: "web-research",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_web_research_link",
            defaultMessage: "Let the agent search and read the web",
          }),
      },
      {
        slug: "plugins",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_plugins_link",
            defaultMessage: "Connect a plugin and use it in a chat",
          }),
      },
    ],
  },
  {
    key: "voice",
    title: () =>
      intl.formatMessage({
        id: "guides_dialog_voice_title",
        defaultMessage: "Voice",
      }),
    guides: [
      {
        slug: "transcribe-a-recording",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_transcribe_a_recording_link",
            defaultMessage: "Turn a recording into a source",
          }),
      },
      {
        slug: "voice-input",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_voice_input_link",
            defaultMessage: "Dictate a question",
          }),
      },
    ],
  },
  {
    key: "jobs",
    title: () =>
      intl.formatMessage({
        id: "guides_dialog_jobs_title",
        defaultMessage: "Jobs",
      }),
    guides: [
      {
        slug: "business-trial",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_business_trial_link",
            defaultMessage: "Start a trial and add your license",
          }),
      },
      {
        slug: "security-questionnaire",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_security_questionnaire_link",
            defaultMessage:
              "Fill in a security questionnaire from your policies",
          }),
      },
      {
        slug: "contract-redline",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_contract_redline_link",
            defaultMessage: "Redline a contract against your playbook",
          }),
      },
    ],
  },
  {
    key: "privacy-and-updates",
    title: () =>
      intl.formatMessage({
        id: "guides_dialog_privacy_and_updates_title",
        defaultMessage: "Privacy and updates",
      }),
    guides: [
      {
        slug: "privacy-network",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_privacy_network_link",
            defaultMessage: "See and control what leaves your computer",
          }),
      },
      {
        slug: "updates",
        title: () =>
          intl.formatMessage({
            id: "guides_dialog_updates_link",
            defaultMessage: "Update SurfSense",
          }),
      },
    ],
  },
]
