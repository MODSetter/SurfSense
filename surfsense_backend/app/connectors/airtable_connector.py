"""
Airtable connector for fetching records from Airtable bases.
"""

import json
import logging
import time
from typing import Any

import httpx
from dateutil.parser import isoparse

from app.schemas.airtable_auth_credentials import AirtableAuthCredentialsBase

logger = logging.getLogger(__name__)


class AirtableConnector:
    """
    Connector for interacting with Airtable API using OAuth 2.0 credentials.
    """

    def __init__(self, credentials: AirtableAuthCredentialsBase):
        """
        Initialize the AirtableConnector with OAuth credentials.

        Args:
            credentials: Airtable OAuth credentials
        """
        self.credentials = credentials
        self.base_url = "https://api.airtable.com/v0"
        self._client = None

    def _get_client(self) -> httpx.Client:
        """
        Get or create an HTTP client with proper authentication headers.

        Returns:
            Configured httpx.Client instance
        """
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.credentials.access_token}",
                "Content-Type": "application/json",
            }
            self._client = httpx.Client(
                headers=headers,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    def _make_request(
        self, method: str, url: str, **kwargs
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Make an HTTP request with error handling and retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for the request

        Returns:
            Tuple of (response_data, error_message)
        """
        client = self._get_client()
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = client.request(method, url, **kwargs)

                if response.status_code == 429:
                    # Rate limited - wait and retry
                    retry_after = int(response.headers.get("Retry-After", retry_delay))
                    logger.warning(
                        f"Rate limited by Airtable API. Waiting {retry_after} seconds. "
                        f"Attempt {attempt + 1}/{max_retries}"
                    )
                    time.sleep(retry_after)
                    retry_delay *= 2
                    continue

                if response.status_code == 401:
                    return None, "Authentication failed. Please check your credentials."

                if response.status_code == 403:
                    return (
                        None,
                        "Access forbidden. Please check your permissions and scopes.",
                    )

                if response.status_code >= 400:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("error", {}).get(
                            "message", error_detail
                        )
                    except Exception:
                        pass
                    return None, f"API error {response.status_code}: {error_detail}"

                return response.json(), None

            except httpx.TimeoutException:
                if attempt == max_retries - 1:
                    return None, "Request timeout. Please try again later."
                logger.warning(
                    f"Request timeout. Retrying... Attempt {attempt + 1}/{max_retries}"
                )
                time.sleep(retry_delay)
                retry_delay *= 2

            except Exception as e:
                if attempt == max_retries - 1:
                    return None, f"Request failed: {e!s}"
                logger.warning(
                    f"Request failed: {e!s}. Retrying... Attempt {attempt + 1}/{max_retries}"
                )
                time.sleep(retry_delay)
                retry_delay *= 2

        return None, "Max retries exceeded"

    def get_bases(self) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get list of accessible bases.

        Returns:
            Tuple of (bases_list, error_message)
        """
        url = f"{self.base_url}/meta/bases"
        response_data, error = self._make_request("GET", url)

        if error:
            return [], error

        if not response_data or "bases" not in response_data:
            return [], "No bases found in response"

        return response_data["bases"], None

    def get_base_schema(self, base_id: str) -> tuple[dict[str, Any] | None, str | None]:
        """
        Get schema information for a specific base.

        Args:
            base_id: The base ID

        Returns:
            Tuple of (schema_data, error_message)
        """
        url = f"{self.base_url}/meta/bases/{base_id}/tables"
        return self._make_request("GET", url)

    def get_records(
        self,
        base_id: str,
        table_id: str,
        max_records: int = 100,
        offset: str | None = None,
        filter_by_formula: str | None = None,
        sort: list[dict[str, str]] | None = None,
        fields: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """
        Get records from a specific table in a base.

        Args:
            base_id: The base ID
            table_id: The table ID or name
            max_records: Maximum number of records to return (max 100)
            offset: Pagination offset
            filter_by_formula: Airtable formula to filter records
            sort: List of sort specifications
            fields: List of field names to include

        Returns:
            Tuple of (records_list, next_offset, error_message)
        """
        url = f"{self.base_url}/{base_id}/{table_id}"

        params = {}
        if max_records:
            params["maxRecords"] = min(max_records, 100)  # Airtable max is 100
        if offset:
            params["offset"] = offset
        if filter_by_formula:
            params["filterByFormula"] = filter_by_formula
        if sort:
            for i, sort_spec in enumerate(sort):
                params[f"sort[{i}][field]"] = sort_spec["field"]
                params[f"sort[{i}][direction]"] = sort_spec.get("direction", "asc")
        if fields:
            for i, field in enumerate(fields):
                params[f"fields[{i}]"] = field

        response_data, error = self._make_request("GET", url, params=params)

        if error:
            return [], None, error

        if not response_data:
            return [], None, "No data in response"

        records = response_data.get("records", [])
        next_offset = response_data.get("offset")

        return records, next_offset, None

    def get_all_records(
        self,
        base_id: str,
        table_id: str,
        max_records: int = 2500,
        filter_by_formula: str | None = None,
        sort: list[dict[str, str]] | None = None,
        fields: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get all records from a table with pagination.

        Args:
            base_id: The base ID
            table_id: The table ID or name
            max_records: Maximum total records to fetch
            filter_by_formula: Airtable formula to filter records
            sort: List of sort specifications
            fields: List of field names to include

        Returns:
            Tuple of (all_records, error_message)
        """
        all_records = []
        offset = None
        fetched_count = 0

        while fetched_count < max_records:
            batch_size = min(100, max_records - fetched_count)

            records, next_offset, error = self.get_records(
                base_id=base_id,
                table_id=table_id,
                max_records=batch_size,
                offset=offset,
                filter_by_formula=filter_by_formula,
                sort=sort,
                fields=fields,
            )

            if error:
                return all_records, error

            if not records:
                break

            all_records.extend(records)
            fetched_count += len(records)

            if not next_offset:
                break

            offset = next_offset

            # Small delay to be respectful to the API
            time.sleep(0.1)

        return all_records, None

    def get_records_by_date_range(
        self,
        base_id: str,
        table_id: str,
        date_field: str,
        start_date: str,
        end_date: str,
        max_records: int = 2500,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get records filtered by a date range.

        Args:
            base_id: The base ID
            table_id: The table ID or name
            date_field: Name of the date field to filter on
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            max_records: Maximum total records to fetch

        Returns:
            Tuple of (records, error_message)
        """
        try:
            # Parse and validate dates
            start_dt = isoparse(start_date)
            end_dt = isoparse(end_date)

            if start_dt >= end_dt:
                return (
                    [],
                    f"start_date ({start_date}) must be before end_date ({end_date})",
                )

            # Create Airtable formula for date filtering
            # filter_formula = (
            #    f"AND("
            #    f"IS_AFTER({{date_field}}, '{start_date}'), "
            #    f"IS_BEFORE({{date_field}}, '{end_date}')"
            #    f")"
            # ).replace("{date_field}", date_field)
            # TODO: Investigate how to properly use filter formula

            return self.get_all_records(
                base_id=base_id,
                table_id=table_id,
                max_records=max_records,
                # filter_by_formula=filter_formula,
            )

        except Exception as e:
            return [], f"Error filtering by date range: {e!s}"

    def format_record_to_markdown(
        self, record: dict[str, Any], table_name: str = ""
    ) -> str:
        """
        Format an Airtable record as markdown.

        Args:
            record: The Airtable record
            table_name: Name of the table (optional)

        Returns:
            Formatted markdown string
        """
        record_id = record.get("id", "Unknown")
        fields = record.get("fields", {})
        created_time = record.get("CREATED_TIME()", "")

        markdown_parts = []

        # Title
        title = "Airtable Record"
        if table_name:
            title += f" from {table_name}"
        markdown_parts.append(f"# {title}")
        markdown_parts.append("")

        # Metadata
        markdown_parts.append("## Record Information")
        markdown_parts.append(f"- **Record ID**: {record_id}")
        if created_time:
            markdown_parts.append(f"- **Created**: {created_time}")
        markdown_parts.append("")

        # Fields
        if fields:
            markdown_parts.append("## Fields")
            for field_name, field_value in fields.items():
                markdown_parts.append(f"### {field_name}")

                if isinstance(field_value, list):
                    for item in field_value:
                        if isinstance(item, dict):
                            # Handle attachments, linked records, etc.
                            if "url" in item:
                                markdown_parts.append(f"- [Attachment]({item['url']})")
                            else:
                                markdown_parts.append(f"- {json.dumps(item, indent=2)}")
                        else:
                            markdown_parts.append(f"- {item}")
                elif isinstance(field_value, dict):
                    markdown_parts.append(
                        f"```json\n{json.dumps(field_value, indent=2)}\n```"
                    )
                else:
                    markdown_parts.append(str(field_value))

                markdown_parts.append("")

        return "\n".join(markdown_parts)
