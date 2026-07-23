# RationaleOps

> The code remembers what. RationaleOps preserves why.

RationaleOps is a Cognitive Task Analysis agent for high-impact business logic hidden in enterprise data pipelines. It uses DataHub to locate risky SQL decision points, interviews the people who understand them, and turns human-confirmed rationale into living DataHub context, executable tests, and safe repair proposals.

## Hackathon

This project is being built for **Build with DataHub: The Agent Hackathon** in the **Agents That Do Real Work** category.

Current status: **development scaffold and implementation plan**. The end-to-end application is not complete yet. Progress is measured against the [Definition of Done](DEVELOPMENT.md#20-definition-of-done).

## The Problem

DataHub can show that a transformation affects 47 downstream assets. It cannot reliably infer whether a strange predicate is an approved business rule, an expired workaround, or a bug:

```sql
WHERE activity_at >= current_date - interval '37 days'
  AND country_code <> 'DE'
  AND account_status NOT IN ('trial', 'refunded')
```

RationaleOps uses DataHub as a risk radar, then conducts an evidence-grounded, adaptive interview with the responsible owner. It never promotes an inferred rationale to fact. Humans authorize intent; deterministic code verifies the resulting test or repair.

## Hero Workflow

```text
DataHub impact analysis
→ SQL decision-point mining
→ knowledge-risk ranking
→ adaptive Cognitive Task Analysis interview
→ human-confirmed Decision Contract
→ executable test or repair proposal
→ deterministic validation
→ DataHub write-back
```

The demo resolves three visually similar filters into three different outcomes:

- `CONFIRMED RULE`
- `EXPIRED WORKAROUND`
- `DOCUMENTATION DRIFT`

## Deep DataHub Usage

The planned application uses:

- Query history to locate production SQL and usage evidence.
- Table- and column-level lineage to calculate downstream blast radius.
- Schemas, owners, glossary terms, descriptions, tags, and structured properties to ground interviews.
- DataHub MCP Server or Agent Context Kit for agent reads.
- DataHub SDK or GraphQL for approved context write-back.

The lineage graph is an input, not the product. The new value is preserving the human-confirmed `WHY`, authority, exceptions, and lifecycle behind executable logic.

## Repository Layout

```text
.
├── DEVELOPMENT.md                 # Product, architecture, demo, and implementation plan
├── docs/
│   ├── HACKATHON_BRIEF.md         # Rules, deliverables, and judging criteria
│   └── USER_PAIN_RESEARCH.md      # Official and community evidence
├── .env.example                   # Safe local configuration template
├── main.py                        # Current development entry point
└── pyproject.toml                 # Python project metadata
```

## Prerequisites

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/)
- A local or reachable DataHub OSS instance for the future integration milestones
- A DeepSeek API key for live LLM calls

## Local Setup

```bash
git clone https://github.com/barebone-lab/rationaleops.git
cd rationaleops
uv sync
cp .env.example .env
```

Set `DEEPSEEK_API_KEY` in `.env`, then run the current scaffold:

```bash
uv run python main.py
```

Expected output:

```text
RationaleOps development scaffold
See DEVELOPMENT.md for the implementation plan and Definition of Done.
```

## LLM Configuration

RationaleOps uses DeepSeek V4-Pro through the OpenAI-compatible DeepSeek API:

```dotenv
DEEPSEEK_API_KEY=replace-with-your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_THINKING_ENABLED=true
DEEPSEEK_REASONING_EFFORT=high
```

`.env` is ignored by Git. Never commit API keys, interview transcripts, production metadata, or sensitive fixtures.

## Validation

Current scaffold check:

```bash
uv run python main.py
```

Planned automated checks are specified in [Test Strategy](DEVELOPMENT.md#16-test-strategy), including AST extraction, truth-state enforcement, citation completeness, agent evaluations, DataHub integration, and golden-demo invariants.

## Documentation

- [Development plan](DEVELOPMENT.md)
- [Hackathon brief](docs/HACKATHON_BRIEF.md)
- [User-pain research](docs/USER_PAIN_RESEARCH.md)

## Core Principle

> The LLM discovers questions and structures answers. Humans authorize intent. Code verifies implementation.

## License

Licensed under the [Apache License 2.0](LICENSE).
