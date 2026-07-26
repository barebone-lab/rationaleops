# RationaleOps Dashboard

Production: <https://barebone-lab.github.io/rationaleops/>

The interactive hero workspace presents the complete trust chain in three panes:

1. DataHub impact graph, owner, glossary, and usage context.
2. Deterministically mined and ranked SQL decision points.
3. CTA interview, Decision Contract, verified artifact, approval, and write-back.

## GitHub Pages

The production source lives in `gh-pages/` and is deployed by
`.github/workflows/deploy.yml` whenever that directory changes on `main`.

```bash
cd gh-pages
npm ci
npm run dev
```

## Run the full-stack dashboard locally

```bash
npm install
npm run dev
```

The recorded workflow is embedded so the site remains usable without services.
To persist actions through the Python API and enable live DeepSeek interview
turns, start `uv run rationaleops-api` at the repository root, then run:

```bash
NEXT_PUBLIC_RATIONALEOPS_API_URL=http://127.0.0.1:8000 npm run dev
```

## Verify

```bash
npm run lint
npm test
npm audit --omit=dev
```

`npm test` builds the vinext output and verifies the
server-rendered hero story, all three outcomes, approval flow, and production
metadata.
