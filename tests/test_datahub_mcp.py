from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from rationaleops.datahub_mcp import DataHubMcpReader


def test_mcp_evidence_maps_to_typed_query_context() -> None:
    dataset_urn = (
        "urn:li:dataset:(urn:li:dataPlatform:postgres,analytics.revenue_daily,PROD)"
    )
    reader = DataHubMcpReader(server="http://datahub.invalid")
    reader.collect_evidence = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "get_dataset_queries": {
                "queries": [
                    {
                        "urn": "urn:li:query:revenue",
                        "properties": {"statement": {"value": "SELECT * FROM revenue"}},
                    }
                ]
            },
            "get_lineage": {
                "downstreams": {
                    "total": 47,
                    "searchResults": [{"entity": {"urn": "urn:li:dataset:downstream"}}],
                }
            },
            "get_entities": [
                {
                    "urn": dataset_urn,
                    "ownership": {
                        "owners": [
                            {
                                "owner": {
                                    "urn": "urn:li:corpGroup:finance-data",
                                    "name": "Finance Data",
                                    "info": {
                                        "admins": [{"urn": "urn:li:corpuser:owner"}],
                                        "members": [],
                                    },
                                }
                            }
                        ]
                    },
                    "glossaryTerms": {
                        "terms": [
                            {
                                "term": {
                                    "urn": "urn:li:glossaryTerm:activeCustomer",
                                    "hierarchicalName": "Active Customer",
                                    "properties": {
                                        "name": "Active Customer",
                                        "description": "Activity within 30 days.",
                                    },
                                }
                            }
                        ]
                    },
                    "properties": {
                        "customProperties": [
                            {
                                "key": "rationaleops.usage_criticality",
                                "value": "0.96",
                            }
                        ]
                    },
                }
            ],
            "list_schema_fields": {"fields": []},
        }
    )

    context = asyncio.run(reader.get_query_context(dataset_urn))

    assert context.query_urn == "urn:li:query:revenue"
    assert context.impact.downstream_count == 47
    assert context.impact.usage_criticality == 0.96
    assert context.owner.authorized_confirmers == ("urn:li:corpuser:owner",)
    assert context.glossary[0].term == "Active Customer"
