# Recorded Three-Outcome Example

`recorded/` contains the deterministic judge fallback. It produces the same
three outcomes without an LLM API key or DataHub instance:

- `CONFIRMED_RULE` → active-window SQL acceptance test;
- `EXPIRED_WORKAROUND` → Germany-filter removal patch and sample regression;
- `DOCUMENTATION_DRIFT` → Active Customer glossary diff.

Regenerate every contract, transcript, artifact, approval, graph, and fixture
write receipt with:

```bash
uv run rationaleops demo-all \
  --approve-actions \
  --approve-writeback \
  --output-dir examples/recorded
```

These outputs are deliberately labelled `recorded-fixture`. The write receipts
prove the approval boundary and read-after-write behavior of the fallback; live
DataHub verification uses `rationaleops inspect-datahub` and
`rationaleops writeback-datahub` separately.
