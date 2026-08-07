/// <reference types="vite/client" />

import { useMemo, useState } from "react";
import {
  DEMO_ACTOR,
  decisions,
  graphNodes,
  type DemoDecision,
} from "./demo-data";

type Stage = {
  revealed: number;
  confirmed: boolean;
  approved: boolean;
  published: boolean;
};

type StageMap = Record<string, Stage>;
type Panel = "contract" | "action" | "evidence";

const apiBase = import.meta.env.VITE_RATIONALEOPS_API_URL?.replace(/\/$/, "");

function initialStages(): StageMap {
  return Object.fromEntries(
    decisions.map((decision) => [
      decision.id,
      { revealed: 1, confirmed: false, approved: false, published: false },
    ]),
  );
}

function Icon({ name }: { name: "graph" | "check" | "reset" | "arrow" | "shield" }) {
  const paths = {
    graph: <path d="M5 16.5 9.3 12l3.1 2.8L19 7.5M16 7.5h3v3" />,
    check: <path d="m5 12 4 4L19 6" />,
    reset: <path d="M4 8V4m0 0h4M4 4l3.2 3.2A7 7 0 1 1 5 16" />,
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    shield: <path d="M12 3 5.5 5.8v5.4c0 4.1 2.7 7.6 6.5 8.8 3.8-1.2 6.5-4.7 6.5-8.8V5.8L12 3Zm-3 9 2 2 4-5" />,
  };
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {paths[name]}
    </svg>
  );
}

function outcomeLabel(decision: Pick<DemoDecision, "outcome">) {
  return (decision.outcome as string).replaceAll("_", " ");
}

async function callApi(path: string, body?: Record<string, string>) {
  if (!apiBase) return null;
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail ?? `Request failed (${response.status})`);
  }
  return payload;
}

export function Dashboard() {
  const [selectedId, setSelectedId] = useState(decisions[0].id);
  const [stages, setStages] = useState<StageMap>(initialStages);
  const [panel, setPanel] = useState<Panel>("contract");
  const [notice, setNotice] = useState("Recorded evidence loaded. No API key required.");
  const [busy, setBusy] = useState(false);

  const selected = useMemo(
    () => decisions.find((decision) => decision.id === selectedId) ?? decisions[0],
    [selectedId],
  );
  const stage = stages[selected.id];
  const visibleTurns = selected.turns.slice(0, stage.revealed);

  function updateStage(id: string, change: Partial<Stage>) {
    setStages((current) => ({
      ...current,
      [id]: { ...current[id], ...change },
    }));
  }

  function selectDecision(id: string) {
    setSelectedId(id);
    setPanel("contract");
    if (apiBase) {
      void callApi(`/api/decisions/${id}/select`).catch(() => undefined);
    }
  }

  function revealNext() {
    const next = Math.min(stage.revealed + 1, selected.turns.length);
    updateStage(selected.id, { revealed: next });
    setNotice(
      next === selected.turns.length
        ? "Evidence boundary complete. The owner can now confirm the structured draft."
        : "Answer recorded with a stable evidence reference.",
    );
  }

  async function confirmContract() {
    if (stage.revealed < selected.turns.length) {
      setNotice("Finish the evidence-backed interview before confirmation.");
      return;
    }
    setBusy(true);
    try {
      await callApi(`/api/contracts/${selected.contractId}/confirm`, {
        actor: DEMO_ACTOR,
      });
      updateStage(selected.id, { confirmed: true });
      setNotice(
        selected.targetStatus === "EXPIRED"
          ? "Owner confirmed the original intent; the elapsed expiry now marks it EXPIRED."
          : "Authorized owner confirmation recorded. The contract is now authoritative.",
      );
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Confirmation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function approveAction() {
    if (!stage.confirmed) {
      setNotice("Confirm the Decision Contract before approving an action.");
      return;
    }
    setBusy(true);
    try {
      await callApi(`/api/artifacts/${selected.artifactId}/approve`, {
        actor: DEMO_ACTOR,
      });
      updateStage(selected.id, { approved: true });
      setNotice("Action approved item-by-item after its deterministic check passed.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Approval failed.");
    } finally {
      setBusy(false);
    }
  }

  async function publishContract() {
    if (!stage.approved) {
      setNotice("Approve the validated action before DataHub write-back.");
      return;
    }
    setBusy(true);
    try {
      await callApi(`/api/contracts/${selected.contractId}/writeback`, {
        actor: DEMO_ACTOR,
        mode: "fixture",
      });
      updateStage(selected.id, { published: true });
      setNotice("Write-back verified by reading the stored contract from DataHub context.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Write-back failed.");
    } finally {
      setBusy(false);
    }
  }

  function resetDemo() {
    setStages(initialStages());
    setSelectedId(decisions[0].id);
    setPanel("contract");
    setNotice("Demo reset to owner-stated drafts. No authoritative context published.");
    if (apiBase) {
      void callApi("/api/demo/reset").catch(() => undefined);
    }
  }

  const completedCount = Object.values(stages).filter((item) => item.published).length;
  const contractStatus = stage.confirmed ? selected.targetStatus : "OWNER_STATED";
  const actionStatus = stage.published
    ? "APPLIED"
    : stage.approved
      ? "APPROVED"
      : "VALIDATED";

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true"><span>R</span><i /></div>
          <div>
            <p className="brand-name">RationaleOps</p>
            <p className="brand-subtitle">Decision intelligence for DataHub</p>
          </div>
        </div>
        <div className="dataset-crumb" aria-label="Current DataHub dataset">
          <span>POSTGRES</span>
          <b>/</b>
          <span>ANALYTICS</span>
          <b>/</b>
          <strong>REVENUE_DAILY</strong>
        </div>
        <div className="header-actions">
          <div className="system-pill">
            <i />
            RECORDED GRAPH
          </div>
          <button className="icon-button" onClick={resetDemo} aria-label="Reset demo" title="Reset demo">
            <Icon name="reset" />
          </button>
          <div className="avatar" title="Demo Finance Owner">DF</div>
        </div>
      </header>

      <section className="story-strip">
        <div>
          <span className="story-index">THE QUESTION</span>
          <h1>Three filters. <em>Three different truths.</em></h1>
        </div>
        <p>The code shows what. DataHub finds who and where. The interview preserves why.</p>
        <div className="story-metric"><strong>47</strong><span>downstream<br />assets at risk</span></div>
      </section>

      <section className="workspace-grid">
        <aside className="pane impact-pane" aria-label="DataHub impact graph">
          <div className="pane-heading">
            <div><span className="eyebrow">01 · DATAHUB CONTEXT</span><h2>Impact graph</h2></div>
            <span className="source-badge"><Icon name="graph" /> MCP READ</span>
          </div>
          <div className="graph-wrap">
            <svg className="impact-graph" viewBox="0 0 560 520" role="img" aria-label="Revenue daily has 47 downstream assets">
              <defs>
                <marker id="arrowhead" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
                  <path d="M0,0 L7,3.5 L0,7 Z" fill="currentColor" />
                </marker>
              </defs>
              <g className="graph-lines">
                <line x1="80" y1="237" x2="166" y2="237" />
                {graphNodes.slice(2).map((node) => (
                  <line key={node.id} x1="250" y1="237" x2={node.x - 28} y2={node.y} />
                ))}
              </g>
              {graphNodes.map((node) => (
                <g key={node.id} className={`graph-node ${node.kind}`} transform={`translate(${node.x} ${node.y})`}>
                  <circle r={node.kind === "root" ? 43 : node.kind === "source" ? 28 : 25} />
                  {node.kind === "root" && <circle className="pulse-ring" r="52" />}
                  <text y={node.kind === "root" ? 4 : 3} textAnchor="middle">{node.kind === "root" ? "RD" : node.kind === "source" ? "RAW" : node.kind === "summary" ? "+42" : "◆"}</text>
                  <text className="node-label" y={node.kind === "root" ? 66 : 44} textAnchor="middle">{node.label}</text>
                </g>
              ))}
            </svg>
            <div className="graph-legend"><span><i className="critical-dot" /> Critical consumer</span><span><i /> Downstream</span></div>
          </div>
          <div className="context-list">
            <div><span>OWNER</span><strong>Finance Data</strong><small>1 authorized confirmer</small></div>
            <div><span>GLOSSARY</span><strong>Active Customer</strong><small>&ldquo;activity within 30 days&rdquo;</small></div>
            <div><span>USAGE</span><strong>0.96 criticality</strong><small>Executive + monthly close</small></div>
          </div>
          <div className="trust-note"><Icon name="shield" /><p><strong>Graph facts are evidence, not rationale.</strong><br />The agent may ask; only the owner may authorize intent.</p></div>
        </aside>

        <section className="pane decision-pane" aria-label="SQL decision points">
          <div className="pane-heading">
            <div><span className="eyebrow">02 · RISK RADAR</span><h2>Decision points</h2></div>
            <span className="count-badge">3 FOUND</span>
          </div>
          <div className="sql-file">
            <div className="sql-filebar"><span><i /> revenue_daily.sql</span><b>POSTGRES</b></div>
            <pre aria-label="Source SQL"><code><span className="line-no">07</span> WHERE activity_at &gt;= current_date - interval <mark>&apos;37 days&apos;</mark>{"\n"}<span className="line-no">08</span>   AND country_code &lt;&gt; <mark>&apos;DE&apos;</mark>{"\n"}<span className="line-no">09</span>   AND account_status NOT IN (<mark>&apos;trial&apos;</mark>, <mark>&apos;refunded&apos;</mark>);</code></pre>
          </div>
          <div className="decision-list">
            {decisions.map((decision) => {
              const itemStage = stages[decision.id];
              return (
                <button key={decision.id} className={`decision-card ${selectedId === decision.id ? "selected" : ""}`} onClick={() => selectDecision(decision.id)} aria-pressed={selectedId === decision.id}>
                  <span className="decision-number">{decision.number}</span>
                  <span className="decision-body">
                    <span className="decision-topline"><b>{decision.label}</b><i className={`outcome-dot ${decision.outcome.toLowerCase()}`} /></span>
                    <code>{decision.fragment}</code>
                    <span className="risk-row"><span><i style={{ width: `${decision.risk}%` }} /></span><b>{decision.risk.toFixed(1)}</b><small>KNOWLEDGE RISK</small></span>
                    <span className="decision-reason">{decision.riskReason}</span>
                    <span className={`decision-outcome ${decision.outcome.toLowerCase()}`}>{outcomeLabel(decision)}</span>
                  </span>
                  <span className="decision-state">{itemStage.published ? "WRITTEN" : itemStage.confirmed ? decision.targetStatus : "REVIEW"}</span>
                </button>
              );
            })}
          </div>
          <div className="risk-formula"><span>RISK</span><code>.30 impact + .25 usage + .20 gap + .15 bus factor + .10 age</code><strong>DETERMINISTIC</strong></div>
        </section>

        <section className="pane investigation-pane" aria-label="Interview and decision contract">
          <div className="investigation-header">
            <div>
              <span className="eyebrow">03 · COGNITIVE INVESTIGATION</span>
              <h2>{selected.label}</h2>
            </div>
            <span className="recorded-badge">RECORDED DEMO</span>
          </div>
          <div className="outcome-banner">
            <span className={`outcome-icon ${selected.outcome.toLowerCase()}`}>{selected.outcome === "CONFIRMED_RULE" ? "✓" : selected.outcome === "EXPIRED_WORKAROUND" ? "!" : "↻"}</span>
            <div><span>FINDING</span><strong>{outcomeLabel(selected)}</strong><p>{selected.summary}</p></div>
            <span className="finding-type">{selected.finding}</span>
          </div>
          <div className="interview-section">
            <div className="section-label"><span>CTA INTERVIEW</span><small>{visibleTurns.length} evidence-linked turns</small></div>
            <div className="transcript" aria-live="polite">
              {visibleTurns.map((turn, index) => (
                <article key={`${selected.id}-${index}`} className={`turn ${turn.role}`}>
                  <span className="turn-author">{turn.role === "agent" ? "RO" : "DF"}</span>
                  <div><span>{turn.role === "agent" ? "RATIONALEOPS · CTA AGENT" : "DEMO FINANCE OWNER"}</span><p>{turn.content}</p><small>↳ {turn.evidence}</small></div>
                </article>
              ))}
            </div>
            {stage.revealed < selected.turns.length && (
              <button className="continue-button" onClick={revealNext}>Continue recorded interview <Icon name="arrow" /></button>
            )}
          </div>

          <div className="artifact-workbench">
            <div className="workbench-tabs" role="tablist">
              {(["contract", "action", "evidence"] as Panel[]).map((item) => (
                <button key={item} role="tab" aria-selected={panel === item} className={panel === item ? "active" : ""} onClick={() => setPanel(item)}>{item.toUpperCase()}</button>
              ))}
              <span className={`contract-status ${contractStatus.toLowerCase()}`}>{contractStatus}</span>
            </div>
            {panel === "contract" && (
              <div className="contract-grid">
                <div><span>AUTHORIZED WHY</span><p>{selected.rationale}</p></div>
                <div><span>EXECUTABLE BOUNDARY</span><p>{selected.boundary}</p></div>
                <div><span>LIFECYCLE</span><p>{selected.lifecycle}</p></div>
                <div><span>AUTHORITY</span><p>Finance Data · Demo Finance Owner</p></div>
              </div>
            )}
            {panel === "action" && (
              <div className="action-panel">
                <div className="action-title"><span className="artifact-kind">{selected.artifactKind}</span><div><strong>{selected.artifactTitle}</strong><small>{selected.artifactPath}</small></div><b className={actionStatus.toLowerCase()}>{actionStatus}</b></div>
                <pre><code>{selected.artifactPreview}</code></pre>
                <div className="check-result"><Icon name="check" /><span><strong>DETERMINISTIC CHECK PASSED</strong>{selected.checkLabel}</span></div>
              </div>
            )}
            {panel === "evidence" && (
              <div className="evidence-list">
                {selected.evidence.map((item, index) => <div key={item}><span>{String(index + 1).padStart(2, "0")}</span><code>{item}</code><b>LINKED</b></div>)}
                <div><span>04</span><code>{selected.normalized}</code><b>FINGERPRINTED</b></div>
              </div>
            )}
            <div className="approval-flow">
              <button className={stage.confirmed ? "done" : ""} disabled={busy || stage.confirmed || stage.revealed < selected.turns.length} onClick={confirmContract}>{stage.confirmed ? <><Icon name="check" /> CONTRACT {contractStatus}</> : "1 · CONFIRM CONTRACT"}</button>
              <button className={stage.approved ? "done" : ""} disabled={busy || !stage.confirmed || stage.approved} onClick={approveAction}>{stage.approved ? <><Icon name="check" /> ACTION APPROVED</> : "2 · APPROVE ACTION"}</button>
              <button className={stage.published ? "done published" : "publish"} disabled={busy || !stage.approved || stage.published} onClick={publishContract}>{stage.published ? <><Icon name="check" /> DATAHUB VERIFIED</> : "3 · WRITE TO DATAHUB"}</button>
            </div>
          </div>
        </section>
      </section>

      <footer className="statusbar">
        <div className="status-message"><span>EVENT</span><p>{notice}</p></div>
        <div className="golden-checks"><span><Icon name="check" /> 3 DECISIONS</span><span><Icon name="check" /> ALL CHECKS PASS</span><span><Icon name="check" /> 0 UNCONFIRMED PUBLISHED</span><strong>{completedCount}/3 WRITTEN BACK</strong></div>
      </footer>
    </main>
  );
}
