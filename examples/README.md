# Recorded Example

`recorded/` is the deterministic first vertical slice described in
`DEVELOPMENT.md`. It is intentionally labelled as a fixture run and is not
evidence of a successful mutation against a live DataHub instance.

Regenerate it with:

```bash
uv run rationaleops demo \
  --approve-writeback \
  --output-dir examples/recorded
```

The explicit flag authorizes only the in-memory fixture write-back. The command
does not read live DataHub credentials or a DeepSeek API key.

Outputs:

- `summary.json`: risk breakdown and golden-path results.
- `interview.json`: evidence-linked owner transcript.
- `decision-contract.json`: confirmed typed contract and verification result.
- `test_active_window.sql`: executable boundary acceptance test.
