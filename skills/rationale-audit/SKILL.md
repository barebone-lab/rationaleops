---
name: rationale-audit
description: Audit high-impact SQL business logic with DataHub query, lineage, owner, glossary, and schema evidence. Use when asked to investigate magic numbers, hard-coded filters, temporary workarounds, stale definitions, unexplained CASE or join logic, or to turn owner-confirmed rationale into a Decision Contract, test, documentation proposal, or safe repair.
---

# Rationale Audit

Find the decisions an organization can execute but can no longer explain. Use
DataHub as evidence and routing context; never infer business intent from syntax.

## Trust boundary

Apply this invariant throughout the task:

> The model discovers questions and structures answers. Humans authorize intent.
> Deterministic code verifies implementation.

- Keep inferred explanations in `HYPOTHESIS`.
- Promote owner statements only to `OWNER_STATED`.
- Require an authorized confirmer for `CONFIRMED`.
- Preserve `unknown`, `CONTRADICTED`, `EXPIRED`, and `ORPHANED` instead of
  resolving gaps with plausible prose.
- Link every material claim to an owner turn or an existing DataHub source.
- Require separate, item-by-item approval for every artifact and DataHub write.

## Workflow

### 1. Collect DataHub evidence

Read the exact production query and affected dataset. Collect:

- query text and query URN;
- downstream lineage and critical consumers;
- schema fields;
- owner and authorized confirmer identities;
- glossary terms, descriptions, tags, and custom properties.

Prefer the official DataHub MCP server for reads. In the RationaleOps repository,
run:

```bash
uv run rationaleops inspect-datahub
```

Do not treat a fixture as a live integration result. Label recorded evidence.

### 2. Mine candidate decisions deterministically

Parse SQL before using an LLM. Flag date or numeric literals, hard-coded
exclusions, materially different `CASE` branches, literal-bearing join
predicates, and temporary-workaround comments. Preserve the exact fragment,
normalized expression, fields, literal values, and stable fingerprint.

In the RationaleOps repository, run:

```bash
uv run rationaleops mine
```

Treat each candidate as a question, not a finding of intent.

### 3. Rank knowledge risk transparently

Calculate a visible score from downstream impact, usage criticality,
documentation gap, owner bus factor, and staleness. Add explicit boosts only for
observable conflicts or temporary markers. Never let an LLM invent the score.

Prioritize the smallest set of owner interviews that reduces the largest risk.

### 4. Conduct a Cognitive Task Analysis interview

Show the owner the exact fragment and relevant DataHub evidence. Ask one adaptive
question at a time:

1. Reconstruct the incident or signal that created the logic.
2. Establish the goal and rejected alternatives.
3. Probe record, region, customer-type, and counterfactual boundaries.
4. Convert exceptions into executable fields and values.
5. Establish effective dates, expiry conditions, review triggers, and authority.
6. Present a structured summary for correction or confirmation.

Ask for a specific trigger when the owner says “temporary.” Ask for a field and
value when the owner names an exception. Do not force an answer when the owner
does not know.

### 5. Draft the Decision Contract

Attach the draft to the exact dataset, query, SQL fingerprint, and fragment.
Include:

- status, finding type, and outcome;
- goal and canonical rule;
- includes, excludes, and evidence-linked exceptions;
- owner, authorized confirmers, and confirmation metadata;
- effective date, expiry, and review triggers;
- interview and DataHub evidence references;
- deterministic verification artifacts and results.

Keep the generated draft `OWNER_STATED` until the designated authority confirms
it. Mark material disagreements `CONTRADICTED`.

### 6. Operationalize and verify

Generate the action appropriate to the confirmed outcome:

- confirmed rule → SQL/dbt acceptance test;
- expired workaround → minimal fingerprint-targeted removal patch;
- documentation drift → glossary or Context Document diff.

Run the artifact in isolation. For patches, compare before-and-after sample
results and fail on unrelated changes. Block approval when checks fail.

### 7. Approve and preserve

Request explicit approval for one artifact. Then request a separate explicit
approval for one DataHub mutation. In the RationaleOps repository, write one
verified contract with:

```bash
uv run rationaleops writeback-datahub \
  --approve-contract <exact-contract-id> \
  --approved-by <authorized-user-urn>
```

Read the dataset back after the mutation and verify the contract-specific status,
intent, fingerprint, owner, lifecycle, and verification evidence are retrievable.

## Completion checks

Report completion only when all applicable checks hold:

- exact SQL decision point and DataHub source are linked;
- blast radius and owner come from DataHub;
- at least one adaptive probe changed because of an owner answer;
- every rationale claim has evidence;
- no unconfirmed rationale was published;
- the generated test, patch, or context check passed;
- each action and mutation has its own approval;
- the DataHub write is visible after read-back.
