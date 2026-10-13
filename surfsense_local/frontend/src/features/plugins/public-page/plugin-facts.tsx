import type { ReactNode } from "react"

import { intl } from "@/i18n/intl"

import type { Plugin } from "../api"
import { entryNeeds, isRegistryEntry, type ListedEntry } from "./listed-entry"
import { PluginPageLink } from "./plugin-page-link"

type SignIn = Plugin["auth_type"]

// What connecting asks of the user, named; an account is the plugin's own service's.
function signInLabel(signIn: SignIn, plugin: string) {
  switch (signIn) {
    case "license":
      return intl.formatMessage({
        id: "plugins_page_sign_in_license_label",
        defaultMessage: "SurfSense license",
      })
    case "token":
      return intl.formatMessage({
        id: "plugins_page_sign_in_key_label",
        defaultMessage: "API key",
      })
    case "oauth":
      return intl.formatMessage(
        {
          id: "plugins_page_sign_in_account_label",
          defaultMessage: "Your {plugin} account",
        },
        { plugin }
      )
    case "none":
      return intl.formatMessage({
        id: "plugins_page_sign_in_none_label",
        defaultMessage: "None",
      })
  }
}

// `2026-10` as a date in its month, so the month is named in the user's language.
function addedMonth(added: string): Date {
  const [year, month] = added.split("-").map(Number)
  return new Date(year, month - 1, 1)
}

function Fact({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[8rem_1fr] gap-3 py-1.5 text-sm">
      <dt className="text-muted-foreground">{term}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  )
}

/** How a listed plugin signs in, the hosts it connects to, when it was added, and its pages, from its entry. */
export function PluginFacts({ entry }: { entry: ListedEntry }) {
  const registry = isRegistryEntry(entry) ? entry : null
  const accessNote =
    registry?.access === "external" ? registry.access_note : null
  const homepage = registry?.homepage
  const privacyPolicy = registry?.privacy_policy
  return (
    <dl>
      <Fact
        term={intl.formatMessage({
          id: "plugins_page_publisher_label",
          defaultMessage: "Publisher",
        })}
      >
        {/* A product name, never translated. */}
        {isRegistryEntry(entry) ? entry.author : "SurfSense"}
      </Fact>
      <Fact
        term={intl.formatMessage({
          id: "plugins_page_authentication_label",
          defaultMessage: "Authentication",
        })}
      >
        {signInLabel(entryNeeds(entry), entry.name)}
        {accessNote ? (
          <span className="block text-muted-foreground">{accessNote}</span>
        ) : null}
      </Fact>
      <Fact
        term={intl.formatMessage({
          id: "plugins_page_hosts_label",
          defaultMessage: "Connects to",
        })}
      >
        {registry ? registry.server_host : entry.hosts.join(", ")}
      </Fact>
      {/* An OAuth plugin's other hosts see the sign-in, never a call. */}
      {registry?.sign_in_hosts.length ? (
        <Fact
          term={intl.formatMessage({
            id: "plugins_page_sign_in_hosts_label",
            defaultMessage: "Signs in with",
          })}
        >
          {registry.sign_in_hosts.join(", ")}
        </Fact>
      ) : null}
      {entry.added ? (
        <Fact
          term={intl.formatMessage({
            id: "plugins_page_added_label",
            defaultMessage: "Added",
          })}
        >
          {intl.formatDate(addedMonth(entry.added), {
            year: "numeric",
            month: "long",
          })}
        </Fact>
      ) : null}
      {homepage ? (
        <Fact
          term={intl.formatMessage({
            id: "plugins_page_homepage_label",
            defaultMessage: "Homepage",
          })}
        >
          <PluginPageLink pluginId={entry.id} page="homepage" url={homepage} />
        </Fact>
      ) : null}
      {privacyPolicy ? (
        <Fact
          term={intl.formatMessage({
            id: "plugins_page_privacy_label",
            defaultMessage: "Privacy policy",
          })}
        >
          <PluginPageLink
            pluginId={entry.id}
            page="privacy_policy"
            url={privacyPolicy}
          />
        </Fact>
      ) : null}
    </dl>
  )
}
