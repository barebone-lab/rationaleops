# Build with DataHub: The Agent Hackathon — Local Brief

> Verified: July 23, 2026 (Asia/Shanghai)
>
> Official site: [Devpost overview](https://datahub.devpost.com/)
>
> Full rules: [Official Rules](https://datahub.devpost.com/rules)
>
> Announcement: [DataHub announcement](https://datahub.com/blog/build-with-datahub-agent-hackathon/)

## 1. Timeline and Prizes

- Submission period: July 6, 2026 at 9:00 a.m. EDT through August 10, 2026 at 5:00 p.m. EDT.
- Deadline in Hong Kong/Shanghai: **August 11, 2026 at 5:00 a.m. GMT+8**.
- Judging: August 17–31, 2026.
- Winners announced: September 8, 2026.
- Total prize pool: USD 20,500.
- Grand Prize: USD 6,000.
- Four challenge winners: USD 3,000 each.
- Two honorable mentions: USD 1,000 each.

## 2. Build Requirements

The submission must be a working software application that:

1. Uses the **DataHub open-source platform**.
2. Uses at least one of the following:
   - DataHub MCP Server
   - Agent Context Kit
   - DataHub Skills
   - Analytics Agent
3. Is newly built during the submission period. Libraries, starter templates, and AI coding assistants may be used, but pre-existing work must be disclosed.
4. Runs reliably as described in the video and written submission.

## 3. Challenge Categories

1. **Agents That Do Real Work**: agents that read DataHub context, take meaningful action, and write back to the graph when appropriate.
2. **Metadata-Aware Code Generation & Development**: use real schemas, lineage, and rules to generate mergeable dbt, DAG, SQL, ingestion configuration, or related artifacts.
3. **Production ML Agents**: protect production ML using lineage across training data, features, models, and deployments.
4. **Open / Wildcard**: any creative application built on DataHub.

## 4. Submission Materials

- A project URL: live demo, hosted application, or repository with clear setup instructions.
- A **public source-code repository**.
- Complete source, assets, setup instructions, and test instructions.
- An **Apache License 2.0** file visible at the repository root.
- An English project description.
- A public demo video **under three minutes**. Judges are not required to watch beyond three minutes.
- All submission materials must be in English, or accompanied by an English translation.
- An `examples/` directory with sample outputs is recommended so judges can assess output quality without installing the project.

## 5. Judging Criteria

Devpost lists five criteria without publishing different weights, so planning assumes equal importance:

1. **Use of DataHub**: depth of Context Graph, MCP, Agent Context Kit, Skills, or Analytics Agent usage. Strong projects do more than read metadata and write useful results back when appropriate.
2. **Technical Execution**: implementation quality, robustness, and a genuinely working end-to-end flow.
3. **Originality**: a meaningful extension beyond DataHub's out-of-the-box behavior, not a recreation of an existing feature.
4. **Real-World Usefulness**: whether a real data, ML, or AI platform team would use the product.
5. **Submission Quality**: clarity of the demo video, description, README, and setup instructions.

Bonus consideration is available for meaningful DataHub open-source contributions such as a connector, skill, fix, RFC, or documentation improvement.

## 6. LLM and Runtime Assumptions

- Official architecture material presents Claude, Gemini, and local models as possible runtimes; the rules do not require a particular LLM.
- Official materials do not promise a dedicated LLM quota or API key for participants. Development should therefore assume **bring your own LLM** and include a deterministic mock or recorded mode so judges can run the project without a key.
- The normal workflow is to build and test locally, then submit the public repository, demo URL or test method, and video through Devpost.

## 7. Project Scoring Checklist

- [ ] The hero workflow performs at least one DataHub read, one meaningful action, and one DataHub write-back.
- [ ] The product is neither a metadata chatbot nor a lineage-only visualization.
- [ ] The first visible wow moment occurs within 90 seconds.
- [ ] The failure case is reproducible and verifiable rather than judged only by an LLM.
- [ ] Human approval or dry-run protection prevents destructive metadata changes.
- [ ] The repository includes one-command setup, seeded data, a recorded demo mode, and sample outputs.
- [ ] The README maps evidence to each judging criterion.
- [ ] The project proposes at least one upstreamable DataHub Skill, bug fix, or RFC.
