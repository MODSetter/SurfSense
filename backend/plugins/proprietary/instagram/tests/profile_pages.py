"""A profile's logged-out page and embed, built in the shape Instagram serves them."""

import json
from typing import Any


def _relay(data: dict[str, Any]) -> str:
    """A preloaded query's result as a logged-out page inlines it."""
    result = {"__bbox": {"complete": True, "result": {"data": data}}}
    return json.dumps(
        {
            "require": [
                [
                    "ScheduledServerJS",
                    "handle",
                    None,
                    [
                        {
                            "__bbox": {
                                "require": [
                                    [
                                        "RelayPrefetchedStreamCache",
                                        "next",
                                        [],
                                        ["adp_1", result],
                                    ]
                                ]
                            }
                        }
                    ],
                ]
            ]
        }
    )


def media(username: str, number: int) -> dict[str, Any]:
    """One post as the embed holds it in full."""
    return {
        "__typename": "GraphImage",
        "id": f"m{number}",
        "shortcode": f"C{number}",
        "edge_media_to_caption": {"edges": [{"node": {"text": f"Sunset {number}"}}]},
        "owner": {"id": "7", "username": username},
        "taken_at_timestamp": 1_790_000_000 + number,
        "pinned_for_users": [],
    }


def profile_pages(
    username: str, numbers: list[int], *, followers: int = 280_000_000
) -> dict[str, str]:
    """``{path: html}`` for a profile whose grid and embed both hold ``numbers``."""
    user = {
        "xig_user_by_username": {
            "pk": "7",
            "username": username,
            "full_name": "National Geographic",
            "follower_count": followers,
            "polaris_ordered_timeline_connection": {
                "edges": [{"node": {"code": f"C{n}", "pk": f"m{n}"}} for n in numbers]
            },
        }
    }
    context = {
        "context": {
            "username": username,
            "posts_count": len(numbers),
            "graphql_media": [{"shortcode_media": media(username, n)} for n in numbers],
        }
    }
    embed = json.dumps({"contextJSON": json.dumps(context)})
    return {
        f"{username}/": f'<script type="application/json" data-sjs>{_relay(user)}</script>',
        f"{username}/embed/": f"<script>s.handle({embed});</script>",
    }
