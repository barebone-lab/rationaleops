"""Idempotent DataHub OSS demo-graph seeding."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.metadata.schema_classes import (
    AuditStampClass,
    CorpGroupInfoClass,
    CorpUserInfoClass,
    QueryLanguageClass,
    QueryPropertiesClass,
    QuerySourceClass,
    QueryStatementClass,
    QuerySubjectClass,
    QuerySubjectsClass,
)
from datahub.metadata.urns import CorpGroupUrn
from datahub.sdk import Dashboard, Dataset, GlossaryTerm, Tag
from datahub.sdk.main_client import DataHubClient

from rationaleops.datahub_gateway import load_demo_context

DEMO_OWNER = "urn:li:corpGroup:finance-data"
DEMO_CONFIRMER = "urn:li:corpuser:demo-owner"
NEEDS_REVIEW_TAG = "urn:li:tag:RationaleNeedsReview"
VERIFIED_TAG = "urn:li:tag:RationaleVerified"


class DataHubSeedError(RuntimeError):
    """Raised when the local DataHub graph cannot be seeded or verified."""


def _downstream_dataset_names() -> tuple[str, ...]:
    named = (
        "finance.monthly_close",
        "finance.forecast_inputs",
        "finance.regional_revenue",
        "finance.board_pack_extract",
        "growth.active_customer_segments",
        "sales.revenue_targets",
        "operations.billing_health",
    )
    synthetic = tuple(f"demo.downstream_asset_{number:02d}" for number in range(1, 36))
    return named + synthetic


class DataHubDemoSeeder:
    """Seed the complete reproducible graph without deleting unrelated data."""

    def __init__(self, *, server: str, token: str | None = None) -> None:
        self.server = server
        self._client = DataHubClient(server=server, token=token)

    def test_connection(self) -> None:
        self._client.test_connection()

    def _upsert_identity_entities(self) -> None:
        graph = self._client._graph
        graph.emit_mcps(
            [
                MetadataChangeProposalWrapper(
                    entityUrn=DEMO_CONFIRMER,
                    aspect=CorpUserInfoClass(
                        active=True,
                        displayName="Demo Finance Owner",
                        email="demo-owner@rationaleops.local",
                        title="Finance Data Steward",
                        fullName="Demo Finance Owner",
                    ),
                ),
                MetadataChangeProposalWrapper(
                    entityUrn=DEMO_OWNER,
                    aspect=CorpGroupInfoClass(
                        admins=[DEMO_CONFIRMER],
                        members=[DEMO_CONFIRMER],
                        groups=[],
                        displayName="Finance Data",
                        email="finance-data@rationaleops.local",
                        description="Owner of the RationaleOps revenue demo.",
                    ),
                ),
            ]
        )

    def _upsert_query(self, *, query_urn: str, dataset_urn: str, sql: str) -> None:
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        stamp = AuditStampClass(time=now_ms, actor=DEMO_CONFIRMER)
        self._client._graph.emit_mcps(
            MetadataChangeProposalWrapper.construct_many(
                query_urn,
                aspects=[
                    QueryPropertiesClass(
                        statement=QueryStatementClass(
                            value=sql,
                            language=QueryLanguageClass.SQL,
                        ),
                        source=QuerySourceClass.SYSTEM,
                        created=stamp,
                        lastModified=stamp,
                        name="Executive active revenue production query",
                        description=(
                            "Seeded query containing three RationaleOps "
                            "decision points."
                        ),
                        origin="urn:li:dataPlatform:postgres",
                    ),
                    QuerySubjectsClass(
                        subjects=[QuerySubjectClass(entity=dataset_urn)]
                    ),
                ],
            )
        )

    def seed(self) -> dict[str, Any]:
        self.test_connection()
        context = load_demo_context()
        self._upsert_identity_entities()

        for tag in (
            Tag(
                name="RationaleNeedsReview",
                display_name="Rationale needs review",
                description="A hidden decision still needs owner confirmation.",
                color="#F59E0B",
            ),
            Tag(
                name="RationaleVerified",
                display_name="Rationale verified",
                description="Rationale confirmed by an authorized owner.",
                color="#10B981",
            ),
        ):
            self._client.entities.upsert(tag)

        glossary = GlossaryTerm(
            id="activeCustomer",
            display_name="Active Customer",
            definition=context.glossary[0].definition,
            owners=[CorpGroupUrn.from_string(DEMO_OWNER)],
            custom_properties={
                "rationaleops.demo": "true",
                "last_reviewed": "2026-01-15",
            },
        )
        self._client.entities.upsert(glossary)

        raw = Dataset(
            platform="postgres",
            name="raw.customer_activity",
            env="PROD",
            display_name="Raw Customer Activity",
            description="Seed source for the RationaleOps revenue demo.",
            schema=[
                ("customer_id", "varchar", "Stable customer identifier"),
                ("activity_at", "timestamp", "Latest qualifying activity"),
                ("billing_type", "varchar", "prepaid or postpaid"),
                ("country_code", "varchar", "ISO country code"),
                ("account_status", "varchar", "Customer account state"),
            ],
            owners=[CorpGroupUrn.from_string(DEMO_OWNER)],
            tags=[NEEDS_REVIEW_TAG],
        )
        self._client.entities.upsert(raw)

        revenue = Dataset(
            platform="postgres",
            name="analytics.revenue_daily",
            env="PROD",
            display_name="Revenue Daily",
            description=(
                "Executive active-revenue model. It contains three hidden "
                "business decisions selected for the RationaleOps demo."
            ),
            custom_properties={
                "rationaleops.demo": "true",
                "rationaleops.query_urn": context.query_urn,
                "rationaleops.downstream_count": "47",
                "rationaleops.usage_criticality": "0.96",
            },
            schema=[
                ("customer_id", "varchar", "Stable customer identifier"),
                ("activity_at", "timestamp", "Latest qualifying activity"),
                ("billing_type", "varchar", "prepaid or postpaid"),
                ("country_code", "varchar", "ISO country code"),
                ("account_status", "varchar", "Customer account state"),
            ],
            owners=[CorpGroupUrn.from_string(DEMO_OWNER)],
            tags=[NEEDS_REVIEW_TAG],
            terms=["urn:li:glossaryTerm:activeCustomer"],
        )
        revenue.set_upstreams([str(raw.urn)])
        self._client.entities.upsert(revenue)

        seeded_downstreams: list[str] = []
        for name in _downstream_dataset_names():
            downstream = Dataset(
                platform="postgres",
                name=name,
                env="PROD",
                display_name=name.replace(".", " / ").replace("_", " ").title(),
                description="Seeded downstream consumer of revenue_daily.",
                custom_properties={"rationaleops.demo": "true"},
                owners=[CorpGroupUrn.from_string(DEMO_OWNER)],
            )
            downstream.set_upstreams([str(revenue.urn)])
            self._client.entities.upsert(downstream)
            seeded_downstreams.append(str(downstream.urn))

        dashboard_names = (
            "executive-active-revenue",
            "active-revenue-kpi",
            "growth-scorecard",
            "board-revenue-pack",
            "regional-revenue-overview",
        )
        for name in dashboard_names:
            dashboard = Dashboard(
                platform="looker",
                name=name,
                display_name=name.replace("-", " ").title(),
                description="Critical seeded consumer of revenue_daily.",
                input_datasets=[str(revenue.urn)],
                owners=[CorpGroupUrn.from_string(DEMO_OWNER)],
                tags=[NEEDS_REVIEW_TAG],
                custom_properties={"rationaleops.demo": "true"},
            )
            self._client.entities.upsert(dashboard)
            seeded_downstreams.append(str(dashboard.urn))

        self._upsert_query(
            query_urn=context.query_urn,
            dataset_urn=str(revenue.urn),
            sql=context.sql,
        )
        return {
            "server": self.server,
            "dataset_urn": str(revenue.urn),
            "query_urn": context.query_urn,
            "downstream_entities_seeded": len(seeded_downstreams),
            "expected_downstream_count": 47,
            "query_seeded": self._client._graph.exists(context.query_urn),
        }

    def verify(self) -> dict[str, Any]:
        context = load_demo_context()
        self.test_connection()
        exists = self._client._graph.exists(context.dataset_urn)
        lineage = self._client.lineage.get_lineage(
            source_urn=context.dataset_urn,
            direction="downstream",
            max_hops=1,
            count=100,
        )
        query_exists = self._client._graph.exists(context.query_urn)
        return {
            "dataset_exists": exists,
            "query_exists": query_exists,
            "downstream_count": len(lineage),
            "expected_downstream_count": 47,
            "verified": exists and query_exists and len(lineage) == 47,
        }
