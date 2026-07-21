"""``indeed.scrape`` capability registration (billed per job; see config
``INDEED_SCRAPE_MICROS_PER_JOB``)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.indeed.scrape.executor import build_scrape_executor
from app.capabilities.indeed.scrape.schemas import ScrapeInput, ScrapeOutput

INDEED_SCRAPE = Capability(
    name="indeed.scrape",
    description=(
        "Scrape public Indeed job postings, including title, company, location, "
        "salary, and description. Use urls or search_queries."
    ),
    input_schema=ScrapeInput,
    output_schema=ScrapeOutput,
    executor=build_scrape_executor(),
    billing_unit=BillingUnit.INDEED_JOB,
    docs_url="/docs/connectors/native/indeed",
)

register_capability(INDEED_SCRAPE)
