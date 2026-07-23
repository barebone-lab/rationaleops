import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const templateRoot = new URL("../", import.meta.url);

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the complete RationaleOps decision workspace", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>RationaleOps · The code remembers what\./i);
  assert.match(html, /Three filters\./);
  assert.match(html, /Three different truths\./);
  assert.match(html, /47/);
  assert.match(html, /CONFIRMED RULE/);
  assert.match(html, /EXPIRED WORKAROUND/);
  assert.match(html, /DOCUMENTATION DRIFT/);
  assert.match(html, /Impact graph/);
  assert.match(html, /CTA INTERVIEW/);
  assert.match(html, /WRITE TO DATAHUB/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/);
});

test("starter preview is removed and production metadata is present", async () => {
  const [page, layout, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(page, /rationaleops-og\.png/);
  assert.match(layout, /themeColor: "#101612"/);
  assert.match(packageJson, /"name": "rationaleops-dashboard"/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  await assert.rejects(readFile(new URL("../app/_sites-preview/SkeletonPreview.tsx", templateRoot)));
});
