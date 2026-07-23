# RationaleOps User-Pain Research

> Verified: July 23, 2026
>
> Method: official product material and research are treated as primary evidence; GitHub and Reddit provide individual user signals, not statistical evidence.

## 1. Core Pain

DataHub, SQL parsers, and lineage systems can answer:

- Which table feeds a dashboard?
- Which filter, join, `CASE`, or constant appears in a query?
- Which assets could be affected by a column change?

They usually cannot answer:

> **Is this 37-day window, `country != 'DE'` exclusion, or unusual refund filter an official business rule, a temporary workaround, historical residue, or a bug?**

Code records what the system does. The human rationale, cues, alternatives, exceptions, and expiration conditions behind that behavior are often never recorded.

## 2. Official Evidence

### DataHub treats human knowledge as a distinct form of context

- DataHub says business context includes glossaries, policies, runbooks, decision logs, and organizational knowledge explaining why data is designed a certain way. That context must be authored or ingested from systems such as Notion and Confluence; it cannot be derived from schema alone: [Context Platform](https://datahub.com/products/context-platform/).
- DataHub describes join logic, filters, and `CASE` statements that handle edge cases as tacit understanding embedded in code: [AI-ready context](https://datahub.com/blog/ai-ready-context/).
- Official guidance still asks teams to place FAQs and tribal knowledge into Context Documents, assign owners, and review them at least quarterly or when a process changes: [AI-ready documentation best practices](https://support.datahub.com/hc/en-us/articles/52985040530715-Best-Practices-for-AI-Ready-Documentation-in-DataHub-AI-Doc-Generation-and-Context-Documents).
- DataHub estimates that manual context creation can take about 16 hours per table and that context decays as schemas, metric definitions, and business logic change: [Context Layer Components](https://datahub.com/blog/context-layer-components/). This is a vendor statement and should be treated as directional evidence rather than independent statistics.

### AI documentation still cannot reliably know why

DataHub AI Documentation analyzes schema, lineage, sample values, and related metadata to generate descriptions, and all generated content requires human review. It can infer purpose and behavior, but without evidence it cannot know whether an exception is a board-approved rule, a legal workaround, or an expired bug: [official best practices](https://support.datahub.com/hc/en-us/articles/52985040530715-Best-Practices-for-AI-Ready-Documentation-in-DataHub-AI-Doc-Generation-and-Context-Documents).

## 3. Community Pain Signals

- A team inherited an old Scala pipeline with no metadata after the original owner left and did not know whether to reconstruct knowledge from the UI or the code: [Reddit discussion](https://www.reddit.com/r/dataengineering/comments/1tqd0db).
- One organization accumulated ten years of metric sprawl, with teams maintaining conflicting definitions and no obvious place to begin cleanup: [Reddit discussion](https://www.reddit.com/r/BusinessIntelligence/comments/1ug9ujv).
- BI practitioners describe spending substantial time reconciling why the same metric has different truths in different systems rather than building dashboards: [Reddit discussion](https://www.reddit.com/r/BusinessIntelligence/comments/1to1d4s).
- Data-catalog adoption discussions warn that without stewards maintaining business context, the catalog becomes another maintenance burden: [Reddit discussion](https://www.reddit.com/r/dataengineering/comments/1q6w5sr).
- OpenAI's internal data agent reads Slack, Google Docs, and Notion in addition to schema and lineage because important definitions, launch context, and institutional knowledge live there: [OpenAI engineering article](https://openai.com/index/inside-our-in-house-data-agent/).

## 4. Why Existing Methods Are Expensive

### Method A: Ask engineers to write comments and documentation

- It depends on individual discipline.
- Teams do not know which rule should be documented first.
- Comments lack downstream impact, ownership, and usage priority from DataHub.
- Code changes without synchronized rationale updates.
- Comments do not reliably distinguish an expired workaround from a permanent policy.

### Method B: Run data-steward documentation workshops

- Stewards must interview each table, dashboard, and owner.
- Generic interviews capture the normal process but often miss edge cases, cues, and counterfactuals.
- High-impact and low-impact assets consume similar effort.
- The output is usually prose that cannot verify implementation drift.

### Method C: Generate documentation with AI

- AI can describe `WHAT`, but without human evidence it cannot safely claim to know `WHY`.
- It may rationalize accidental behavior as a business rule.
- It cannot infer the owner, approval, or expiry of a temporary exception.

### Method D: Use a semantic layer or data contract

- These systems enforce rules that have already been formalized.
- The initial legacy problem is that the rules have not been formalized and stakeholders may disagree about their meaning.
- RationaleOps is the discovery and elicitation front end for semantic layers and contracts, not a replacement for them.

## 5. Cross-Disciplinary Method

RationaleOps borrows **Cognitive Task Analysis (CTA)** and the **Critical Decision Method (CDM)**.

CDM uses multi-pass retrospective interviews and probe questions to elicit tacit expert knowledge. Its outputs can include timelines, decision requirements, and situation-assessment records: [Hoffman, Crandall & Shadbolt, Human Factors](https://journals.sagepub.com/doi/10.1518/001872098779480442).

Clinical research also uses semi-structured CDM probes to identify the cues, judgments, strategies, goals, and expectations experts use: [clinical CTA example](https://academic.oup.com/atsscholar/article/6/4/448/8444050).

### Data-engineering analogy

| High-risk-domain concept | RationaleOps equivalent |
|---|---|
| Flight or event recorder | DataHub lineage, query history, and SQL transformations |
| Critical incident | A high-impact, unexplained filter, `CASE`, join, or constant |
| Investigator | LLM agent |
| Expert interview | Adaptive conversation with the data owner |
| Cues, goals, and alternatives | Input signals, business objectives, and rejected logic |
| Counterfactual probe | “What happens for a prepaid customer or after Q4?” |
| Investigation finding | Human-confirmed Decision Contract |
| Safety recommendation | dbt test, glossary update, code patch, or expiry review |

## 6. Testable Product Hypotheses

RationaleOps is valuable only if these hypotheses hold:

1. Frequently used SQL contains undocumented, non-obvious decision points.
2. The DataHub graph can identify downstream impact and likely owners.
3. An owner's natural-language explanation provides rationale absent from code and metadata.
4. Adaptive probing reveals exceptions, expiry conditions, and counterfactuals better than a generic form.
5. The result can become an executable check rather than another static document.

The MVP must demonstrate all five. Otherwise, the idea collapses into an AI documentation chatbot.
