"""
Home Assistant connector for fetching smart home data.

This connector interfaces with the Home Assistant REST API to retrieve:
- Entity states and history
- Automations and scripts
- Logbook events
- Device and area information
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class HomeAssistantConnector:
    """Connector for Home Assistant smart home platform."""

    def __init__(self, ha_url: str, access_token: str):
        """
        Initialize the Home Assistant connector.

        Args:
            ha_url: Base URL of Home Assistant instance (e.g., http://homeassistant.local:8123)
            access_token: Long-lived access token for authentication
        """
        self.ha_url = ha_url.rstrip("/")
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self, endpoint: str, method: str = "GET", data: dict | None = None
    ) -> tuple[Any | None, str | None]:
        """
        Make an authenticated request to Home Assistant API.

        Args:
            endpoint: API endpoint (e.g., /api/states)
            method: HTTP method
            data: Optional request body

        Returns:
            Tuple of (response_data, error_message)
        """
        url = f"{self.ha_url}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, url, headers=self.headers, json=data, timeout=30
                ) as response:
                    if response.status == 200:
                        return await response.json(), None
                    elif response.status == 401:
                        return None, "Invalid or expired access token"
                    elif response.status == 404:
                        return None, f"Endpoint not found: {endpoint}"
                    else:
                        error_text = await response.text()
                        return None, f"API error {response.status}: {error_text}"
        except aiohttp.ClientConnectorError as e:
            return None, f"Connection error: Unable to reach Home Assistant at {self.ha_url}. {e!s}"
        except TimeoutError:
            return None, f"Request timeout connecting to {self.ha_url}"
        except Exception as e:
            return None, f"Unexpected error: {e!s}"

    async def test_connection(self) -> tuple[bool, str | None]:
        """
        Test the connection to Home Assistant.

        Returns:
            Tuple of (success, error_message)
        """
        result, error = await self._make_request("/api/")
        if error:
            return False, error
        return True, None

    async def get_states(self) -> tuple[list[dict], str | None]:
        """
        Get all entity states.

        Returns:
            Tuple of (states_list, error_message)
        """
        return await self._make_request("/api/states")

    async def get_entity_history(
        self,
        entity_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> tuple[list[dict], str | None]:
        """
        Get history for a specific entity.

        Args:
            entity_id: Entity ID (e.g., sensor.temperature)
            start_time: Start of history period
            end_time: End of history period

        Returns:
            Tuple of (history_list, error_message)
        """
        if start_time is None:
            start_time = datetime.now() - timedelta(days=1)
        if end_time is None:
            end_time = datetime.now()

        start_str = start_time.isoformat()
        end_str = end_time.isoformat()

        endpoint = f"/api/history/period/{start_str}?end_time={end_str}&filter_entity_id={entity_id}"
        result, error = await self._make_request(endpoint)

        if error:
            return [], error
        # History returns nested list, flatten it
        if result and len(result) > 0:
            return result[0], None
        return [], None

    async def get_logbook(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        entity_id: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """
        Get logbook entries.

        Args:
            start_time: Start of period
            end_time: End of period
            entity_id: Optional entity to filter by

        Returns:
            Tuple of (logbook_entries, error_message)
        """
        if start_time is None:
            start_time = datetime.now() - timedelta(days=1)

        start_str = start_time.isoformat()
        endpoint = f"/api/logbook/{start_str}"

        if end_time:
            endpoint += f"?end_time={end_time.isoformat()}"
        if entity_id:
            separator = "&" if "?" in endpoint else "?"
            endpoint += f"{separator}entity={entity_id}"

        return await self._make_request(endpoint)

    async def get_services(self) -> tuple[dict, str | None]:
        """
        Get all available services.

        Returns:
            Tuple of (services_dict, error_message)
        """
        return await self._make_request("/api/services")

    async def get_config(self) -> tuple[dict, str | None]:
        """
        Get Home Assistant configuration.

        Returns:
            Tuple of (config_dict, error_message)
        """
        return await self._make_request("/api/config")

    async def get_events(self) -> tuple[list[dict], str | None]:
        """
        Get list of available event types.

        Returns:
            Tuple of (events_list, error_message)
        """
        return await self._make_request("/api/events")

    async def get_automations(self) -> tuple[list[dict], str | None]:
        """
        Get all automation entities.

        Returns:
            Tuple of (automations_list, error_message)
        """
        states, error = await self.get_states()
        if error:
            return [], error

        automations = [
            state for state in states if state.get("entity_id", "").startswith("automation.")
        ]
        return automations, None

    async def get_scripts(self) -> tuple[list[dict], str | None]:
        """
        Get all script entities.

        Returns:
            Tuple of (scripts_list, error_message)
        """
        states, error = await self.get_states()
        if error:
            return [], error

        scripts = [state for state in states if state.get("entity_id", "").startswith("script.")]
        return scripts, None

    async def get_scenes(self) -> tuple[list[dict], str | None]:
        """
        Get all scene entities.

        Returns:
            Tuple of (scenes_list, error_message)
        """
        states, error = await self.get_states()
        if error:
            return [], error

        scenes = [state for state in states if state.get("entity_id", "").startswith("scene.")]
        return scenes, None

    async def get_sensors(self) -> tuple[list[dict], str | None]:
        """
        Get all sensor entities.

        Returns:
            Tuple of (sensors_list, error_message)
        """
        states, error = await self.get_states()
        if error:
            return [], error

        sensors = [state for state in states if state.get("entity_id", "").startswith("sensor.")]
        return sensors, None

    async def get_all_indexable_data(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list[dict], str | None]:
        """
        Get all data suitable for indexing.

        This includes:
        - Automations with their configurations
        - Scripts with their configurations
        - Scenes
        - Logbook events for the specified period

        Args:
            start_date: Start of period for logbook events
            end_date: End of period for logbook events

        Returns:
            Tuple of (indexable_items, error_message)
        """
        items = []
        errors = []

        # Get automations
        automations, error = await self.get_automations()
        if error:
            errors.append(f"Automations: {error}")
        else:
            for auto in automations:
                items.append({
                    "type": "automation",
                    "entity_id": auto.get("entity_id"),
                    "name": auto.get("attributes", {}).get("friendly_name", auto.get("entity_id")),
                    "state": auto.get("state"),
                    "last_triggered": auto.get("attributes", {}).get("last_triggered"),
                    "attributes": auto.get("attributes", {}),
                })

        # Get scripts
        scripts, error = await self.get_scripts()
        if error:
            errors.append(f"Scripts: {error}")
        else:
            for script in scripts:
                items.append({
                    "type": "script",
                    "entity_id": script.get("entity_id"),
                    "name": script.get("attributes", {}).get("friendly_name", script.get("entity_id")),
                    "state": script.get("state"),
                    "last_triggered": script.get("attributes", {}).get("last_triggered"),
                    "attributes": script.get("attributes", {}),
                })

        # Get scenes
        scenes, error = await self.get_scenes()
        if error:
            errors.append(f"Scenes: {error}")
        else:
            for scene in scenes:
                items.append({
                    "type": "scene",
                    "entity_id": scene.get("entity_id"),
                    "name": scene.get("attributes", {}).get("friendly_name", scene.get("entity_id")),
                    "state": scene.get("state"),
                    "attributes": scene.get("attributes", {}),
                })

        # Get logbook events
        logbook, error = await self.get_logbook(start_time=start_date, end_time=end_date)
        if error:
            errors.append(f"Logbook: {error}")
        else:
            for entry in logbook:
                items.append({
                    "type": "logbook_event",
                    "entity_id": entry.get("entity_id"),
                    "name": entry.get("name", "Unknown"),
                    "message": entry.get("message", ""),
                    "when": entry.get("when"),
                    "state": entry.get("state"),
                    "domain": entry.get("domain"),
                })

        error_msg = "; ".join(errors) if errors else None
        return items, error_msg

    def format_automation_to_markdown(self, automation: dict) -> str:
        """Format an automation to markdown."""
        name = automation.get("name", "Unknown Automation")
        entity_id = automation.get("entity_id", "")
        state = automation.get("state", "unknown")
        last_triggered = automation.get("last_triggered", "Never")
        attributes = automation.get("attributes", {})

        md = f"# Automation: {name}\n\n"
        md += f"**Entity ID:** {entity_id}\n"
        md += f"**State:** {state}\n"
        md += f"**Last Triggered:** {last_triggered}\n\n"

        if attributes.get("id"):
            md += f"**Automation ID:** {attributes.get('id')}\n"
        if attributes.get("mode"):
            md += f"**Mode:** {attributes.get('mode')}\n"
        if attributes.get("current"):
            md += f"**Current Running:** {attributes.get('current')}\n"

        return md

    def format_script_to_markdown(self, script: dict) -> str:
        """Format a script to markdown."""
        name = script.get("name", "Unknown Script")
        entity_id = script.get("entity_id", "")
        state = script.get("state", "unknown")
        last_triggered = script.get("last_triggered", "Never")
        attributes = script.get("attributes", {})

        md = f"# Script: {name}\n\n"
        md += f"**Entity ID:** {entity_id}\n"
        md += f"**State:** {state}\n"
        md += f"**Last Triggered:** {last_triggered}\n\n"

        if attributes.get("mode"):
            md += f"**Mode:** {attributes.get('mode')}\n"

        return md

    def format_scene_to_markdown(self, scene: dict) -> str:
        """Format a scene to markdown."""
        name = scene.get("name", "Unknown Scene")
        entity_id = scene.get("entity_id", "")
        attributes = scene.get("attributes", {})

        md = f"# Scene: {name}\n\n"
        md += f"**Entity ID:** {entity_id}\n"

        if attributes.get("entity_id"):
            md += f"\n**Controlled Entities:**\n"
            for eid in attributes.get("entity_id", []):
                md += f"- {eid}\n"

        return md

    def format_logbook_event_to_markdown(self, event: dict) -> str:
        """Format a logbook event to markdown."""
        name = event.get("name", "Unknown")
        entity_id = event.get("entity_id", "")
        message = event.get("message", "")
        when = event.get("when", "")
        state = event.get("state", "")
        domain = event.get("domain", "")

        md = f"# Event: {name}\n\n"
        md += f"**Time:** {when}\n"
        if entity_id:
            md += f"**Entity ID:** {entity_id}\n"
        if domain:
            md += f"**Domain:** {domain}\n"
        if state:
            md += f"**State:** {state}\n"
        if message:
            md += f"\n**Message:** {message}\n"

        return md

    def format_item_to_markdown(self, item: dict) -> str:
        """Format any item to markdown based on its type."""
        item_type = item.get("type", "")

        if item_type == "automation":
            return self.format_automation_to_markdown(item)
        elif item_type == "script":
            return self.format_script_to_markdown(item)
        elif item_type == "scene":
            return self.format_scene_to_markdown(item)
        elif item_type == "logbook_event":
            return self.format_logbook_event_to_markdown(item)
        else:
            # Generic formatting
            return f"# {item.get('name', 'Unknown')}\n\n{item}"
