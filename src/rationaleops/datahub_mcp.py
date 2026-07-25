"""Read-only integration with the official DataHub MCP server."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Mapping
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from rationaleops.models import (
    GlossaryContext,
    ImpactContext,
    OwnerContext,
    QueryContext,
)


class DataHubMcpError(RuntimeError):
    """Raised when the optional MCP integration is unavailable or fails."""


def _content_value(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        if isinstance(structured, Mapping) and set(structured) == {"result"}:
            return structured["result"]
        return structured
    text_blocks = [
        block.text
        for block in getattr(result, "content", [])
        if getattr(block, "type", None) == "text"
    ]
    combined = "\n".join(text_blocks)
    try:
        return json.loads(combined)
    except json.JSONDecodeError:
        return combined


class DataHubMcpReader:
    """Launch the official server over stdio and collect DataHub evidence."""

    def __init__(
        self,
        *,
        server: str,
        token: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.server = server
        self.token = token
        self.timeout = timeout_seconds

    def _parameters(self) -> Any:
        try:
            from mcp import StdioServerParameters
        except ImportError as exc:
            raise DataHubMcpError(
                "install the MCP extra with `uv sync --extra mcp`"
            ) from exc
        env = dict(os.environ)
        env["DATAHUB_GMS_URL"] = self.server
        if self.token:
            env["DATAHUB_GMS_TOKEN"] = self.token
        env["DATAHUB_MCP_MUTATION_TOOLS_ENABLED"] = "false"
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server_datahub"],
            env=env,
        )

    async def _check_server_reachable(self) -> None:
        """Pre-flight health check — fail within ~5 s if GMS is down or unreachable."""
        import httpx

        url = f"{self.server.rstrip('/')}/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
        except Exception as exc:
            raise DataHubMcpError(
                f"DataHub GMS unreachable at {self.server}: {exc}"
            ) from exc
        if resp.status_code != 200:
            raise DataHubMcpError(
                f"DataHub GMS unhealthy at {self.server} (HTTP {resp.status_code})"
            )

    async def _session(self, stack: AsyncExitStack) -> Any:
        try:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise DataHubMcpError(
                "install the MCP extra with `uv sync --extra mcp`"
            ) from exc
        error_log = stack.enter_context(
            Path(os.devnull).open("w", encoding="utf-8")  # noqa: SIM115
        )
        read_stream, write_stream = await stack.enter_async_context(
            stdio_client(self._parameters(), errlog=error_log)
        )
        session = await stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await asyncio.wait_for(session.initialize(), timeout=self.timeout)
        return session

    async def list_tools(self) -> tuple[dict[str, Any], ...]:
        async with AsyncExitStack() as stack:
            session = await self._session(stack)
            response = await session.list_tools()
            return tuple(tool.model_dump(mode="json") for tool in response.tools)

    async def collect_evidence(self, dataset_urn: str) -> dict[str, Any]:
        calls = (
            ("get_dataset_queries", {"urn": dataset_urn, "count": 10}),
            (
                "get_lineage",
                {
                    "urn": dataset_urn,
                    "upstream": False,
                    "max_hops": 3,
                    "max_results": 100,
                },
            ),
            ("get_entities", {"urns": [dataset_urn]}),
            ("list_schema_fields", {"urn": dataset_urn, "limit": 100}),
        )
        evidence: dict[str, Any] = {}
        async with AsyncExitStack() as stack:
            session = await self._session(stack)
            for name, arguments in calls:
                result = await asyncio.wait_for(
                    session.call_tool(name, arguments=arguments),
                    timeout=self.timeout,
                )
                if getattr(result, "isError", False):
                    raise DataHubMcpError(f"DataHub MCP tool failed: {name}")
                evidence[name] = _content_value(result)
        return evidence

    async def get_query_context(self, dataset_urn: str) -> QueryContext:
        """Map raw MCP evidence into the typed RationaleOps context.

        Runs a pre-flight health check first so that an unreachable GMS
        fails within ~5 s instead of hanging indefinitely.
        """

        await self._check_server_reachable()

        # per-call timeout × 4 evidence calls + 5 s buffer
        total_timeout = self.timeout * 4 + 5

        async def _collect_and_map() -> QueryContext:
            evidence = await self.collect_evidence(dataset_urn)

            query_result = evidence["get_dataset_queries"]
            queries = query_result.get("queries", [])
            if not queries:
                raise DataHubMcpError("DataHub MCP returned no query evidence")
            query = queries[0]

            entities = evidence["get_entities"]
            if not entities:
                raise DataHubMcpError("DataHub MCP returned no dataset metadata")
            entity = entities[0]
            ownership = entity.get("ownership") or {}
            owners = ownership.get("owners") or []
            if not owners:
                raise DataHubMcpError("dataset has no owner for interview routing")
            owner = owners[0]["owner"]
            owner_info = owner.get("info") or {}
            authorized = tuple(
                dict.fromkeys(
                    item["urn"]
                    for item in (
                        (owner_info.get("admins") or [])
                        + (owner_info.get("members") or [])
                    )
                    if item.get("urn")
                )
            )
            if not authorized:
                raise DataHubMcpError("dataset owner has no authorized confirmer")

            glossary_items: list[GlossaryContext] = []
            glossary = entity.get("glossaryTerms") or {}
            for association in glossary.get("terms") or []:
                term = association.get("term") or {}
                properties = term.get("properties") or {}
                glossary_items.append(
                    GlossaryContext(
                        term=properties.get("name") or term.get("hierarchicalName"),
                        definition=properties.get("description") or "",
                        urn=term["urn"],
                    )
                )

            custom_properties = {
                item["key"]: item["value"]
                for item in (entity.get("properties") or {}).get("customProperties", [])
            }
            downstream = evidence["get_lineage"].get("downstreams") or {}
            search_results = downstream.get("searchResults") or []
            critical_assets = tuple(
                result["entity"]["urn"]
                for result in search_results[:8]
                if result.get("entity", {}).get("urn")
            )
            statement = query["properties"]["statement"]
            return QueryContext(
                query_urn=query["urn"],
                dataset_urn=dataset_urn,
                sql=statement["value"],
                dialect="postgres",
                glossary=tuple(glossary_items),
                owner=OwnerContext(
                    owner_urn=owner["urn"],
                    display_name=(
                        (owner.get("properties") or {}).get("displayName")
                        or owner.get("name")
                        or owner["urn"]
                    ),
                    authorized_confirmers=authorized,
                ),
                impact=ImpactContext(
                    downstream_count=int(downstream.get("total") or 0),
                    critical_assets=critical_assets,
                    usage_criticality=float(
                        custom_properties.get("rationaleops.usage_criticality", "0.5")
                    ),
                    documentation_gap=0.9,
                    owner_bus_factor=0.7,
                    age_or_staleness=0.55,
                ),
            )

        try:
            return await asyncio.wait_for(_collect_and_map(), timeout=total_timeout)
        except TimeoutError:
            raise DataHubMcpError(
                f"DataHub MCP read timed out after "
                f"{total_timeout:.0f}s for {dataset_urn}"
            ) from None
