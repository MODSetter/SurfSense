"""
JSONata transformation templates for each connector type.

These templates transform connector-specific JSON responses into standardized
Document format that SurfSense can store and search.

Template Structure:
    Each template should produce a dictionary with these fields:
    - title: Document title (string)
    - content: Main content/body (string)
    - document_type: Connector type (string, matches DocumentType enum)
    - document_metadata: Additional metadata (dict)

JSONata Resources:
    - Documentation: https://docs.jsonata.org
    - Try online: https://try.jsonata.org
    - Cheat sheet: https://docs.jsonata.org/overview
"""

# GitHub Issue/PR Template
# Transforms GitHub API responses for issues and pull requests
GITHUB_ISSUE_TEMPLATE = """
{
    "title": title,
    "content": body,
    "document_type": "GITHUB_CONNECTOR",
    "document_metadata": {
        "url": html_url,
        "author": user.login,
        "created_at": created_at,
        "updated_at": updated_at,
        "labels": labels.name,
        "state": state,
        "comments_count": comments,
        "repository": repository_url,
        "number": number,
        "is_pull_request": $exists(pull_request)
    }
}
"""

# Gmail Message Template
# Transforms Gmail API message responses
GMAIL_MESSAGE_TEMPLATE = """
{
    "title": payload.headers[name="Subject"].value,
    "content": $join(payload.parts[mimeType="text/plain"].body.data, "\\n"),
    "document_type": "GOOGLE_GMAIL_CONNECTOR",
    "document_metadata": {
        "from": payload.headers[name="From"].value,
        "to": payload.headers[name="To"].value,
        "cc": payload.headers[name="Cc"].value,
        "date": payload.headers[name="Date"].value,
        "thread_id": threadId,
        "message_id": id,
        "labels": labelIds,
        "snippet": snippet
    }
}
"""

# Slack Message Template
# Transforms Slack API message responses
SLACK_MESSAGE_TEMPLATE = """
{
    "title": $substring(text, 0, 100),
    "content": text,
    "document_type": "SLACK_CONNECTOR",
    "document_metadata": {
        "channel": channel,
        "channel_name": channel_name,
        "user": user,
        "user_name": user_name,
        "timestamp": ts,
        "thread_ts": thread_ts,
        "reactions": reactions.{
            "name": name,
            "count": count,
            "users": users
        },
        "attachments": attachments.{
            "title": title,
            "text": text,
            "fallback": fallback
        }
    }
}
"""

# Jira Issue Template
# Transforms Jira API issue responses
JIRA_ISSUE_TEMPLATE = """
{
    "title": fields.summary,
    "content": fields.description,
    "document_type": "JIRA_CONNECTOR",
    "document_metadata": {
        "key": key,
        "id": id,
        "status": fields.status.name,
        "priority": fields.priority.name,
        "issue_type": fields.issuetype.name,
        "assignee": fields.assignee.displayName,
        "reporter": fields.reporter.displayName,
        "created": fields.created,
        "updated": fields.updated,
        "resolved": fields.resolutiondate,
        "project": fields.project.name,
        "project_key": fields.project.key,
        "labels": fields.labels,
        "components": fields.components.name
    }
}
"""

# Discord Message Template
# Transforms Discord API message responses
DISCORD_MESSAGE_TEMPLATE = """
{
    "title": $substring(content, 0, 100),
    "content": content,
    "document_type": "DISCORD_CONNECTOR",
    "document_metadata": {
        "author": author.username,
        "author_id": author.id,
        "channel_id": channel_id,
        "guild_id": guild_id,
        "timestamp": timestamp,
        "message_id": id,
        "is_pinned": pinned,
        "mentions": mentions.{
            "id": id,
            "username": username
        },
        "attachments": attachments.{
            "id": id,
            "filename": filename,
            "url": url,
            "size": size
        },
        "embeds": embeds.{
            "title": title,
            "description": description,
            "url": url
        }
    }
}
"""

# Notion Page Template
# Transforms Notion API page responses
# Handles complex block structure with proper null safety and nested content extraction
NOTION_PAGE_TEMPLATE = """
{
    "title": (
        $exists(properties.Name.title[0].plain_text) ?
        properties.Name.title[0].plain_text :
        $exists(properties.title.title[0].plain_text) ?
        properties.title.title[0].plain_text :
        "Untitled"
    ),
    "content": $join([
        /* Extract title as H1 heading */
        $exists(properties.Name.title[0]) ?
            "# " & properties.Name.title[0].plain_text & "\\n\\n" : "",

        /* Extract rich text from non-title property types */
        properties.$spread().(
            $value.type = "rich_text" ?
                $join($value.rich_text[].plain_text, " ") & "\\n" :
            ""
        ),

        /* Extract content from blocks if available */
        $exists(blocks) ? $join(
            blocks[].(
                type = "paragraph" ? paragraph.rich_text[].plain_text & "\\n" :
                type = "heading_1" ? "# " & heading_1.rich_text[].plain_text & "\\n" :
                type = "heading_2" ? "## " & heading_2.rich_text[].plain_text & "\\n" :
                type = "heading_3" ? "### " & heading_3.rich_text[].plain_text & "\\n" :
                type = "bulleted_list_item" ? "- " & bulleted_list_item.rich_text[].plain_text & "\\n" :
                type = "numbered_list_item" ? "1. " & numbered_list_item.rich_text[].plain_text & "\\n" :
                type = "code" ? "```\\n" & code.rich_text[].plain_text & "\\n```\\n" :
                type = "quote" ? "> " & quote.rich_text[].plain_text & "\\n" :
                ""
            )
        ) : ""
    ]),
    "document_type": "NOTION_CONNECTOR",
    "document_metadata": {
        "page_id": id,
        "created_time": created_time,
        "last_edited_time": last_edited_time,
        "url": url,
        "archived": $exists(archived) ? archived : false,
        "created_by": $exists(created_by.id) ? created_by.id : null,
        "last_edited_by": $exists(last_edited_by.id) ? last_edited_by.id : null,
        "icon": $exists(icon.emoji) ? icon.emoji : null,
        "cover": $exists(cover.external.url) ? cover.external.url : null,
        "properties": properties
    }
}
"""

# Confluence Page Template
# Transforms Confluence API page responses
CONFLUENCE_PAGE_TEMPLATE = """
{
    "title": title,
    "content": body.storage.value,
    "document_type": "CONFLUENCE_CONNECTOR",
    "document_metadata": {
        "id": id,
        "space_key": space.key,
        "space_name": space.name,
        "version": version.number,
        "created": version.when,
        "created_by": version.by.displayName,
        "url": _links.webui,
        "status": status,
        "labels": metadata.labels.results.name
    }
}
"""

# Google Calendar Event Template
# Transforms Google Calendar API event responses
GOOGLE_CALENDAR_EVENT_TEMPLATE = """
{
    "title": summary,
    "content": description,
    "document_type": "GOOGLE_CALENDAR_CONNECTOR",
    "document_metadata": {
        "id": id,
        "start": start.dateTime,
        "end": end.dateTime,
        "created": created,
        "updated": updated,
        "creator": creator.email,
        "organizer": organizer.email,
        "attendees": attendees.{
            "email": email,
            "status": responseStatus
        },
        "location": location,
        "url": htmlLink,
        "recurrence": recurrence
    }
}
"""

# Linear Issue Template
# Transforms Linear API issue responses
# Includes null safety checks for optional fields
LINEAR_ISSUE_TEMPLATE = """
{
    "title": title,
    "content": description,
    "document_type": "LINEAR_CONNECTOR",
    "document_metadata": {
        "id": id,
        "identifier": identifier,
        "state": $exists(state) ? state.name : "No Status",
        "priority": priority,
        "assignee": $exists(assignee) ? assignee.name : null,
        "creator": $exists(creator) ? creator.name : null,
        "created_at": createdAt,
        "updated_at": updatedAt,
        "completed_at": $exists(completedAt) ? completedAt : null,
        "project": $exists(project) ? project.name : null,
        "team": $exists(team) ? team.name : null,
        "labels": $exists(labels.nodes) ? labels.nodes.name : [],
        "url": url
    }
}
"""

# Template registry
# Maps connector type identifiers to their JSONata transformation templates
CONNECTOR_TEMPLATES = {
    "github": GITHUB_ISSUE_TEMPLATE,
    "gmail": GMAIL_MESSAGE_TEMPLATE,
    "slack": SLACK_MESSAGE_TEMPLATE,
    "jira": JIRA_ISSUE_TEMPLATE,
    "discord": DISCORD_MESSAGE_TEMPLATE,
    "notion": NOTION_PAGE_TEMPLATE,
    "confluence": CONFLUENCE_PAGE_TEMPLATE,
    "google_calendar": GOOGLE_CALENDAR_EVENT_TEMPLATE,
    "linear": LINEAR_ISSUE_TEMPLATE,
}
