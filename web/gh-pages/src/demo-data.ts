export type Outcome =
  | "CONFIRMED_RULE"
  | "EXPIRED_WORKAROUND"
  | "DOCUMENTATION_DRIFT";

export type Turn = {
  role: "agent" | "owner";
  content: string;
  evidence: string;
};

export type DemoDecision = {
  id: string;
  contractId: string;
  artifactId: string;
  number: string;
  label: string;
  fragment: string;
  normalized: string;
  kind: string;
  risk: number;
  riskReason: string;
  outcome: Outcome;
  finding: string;
  summary: string;
  rationale: string;
  boundary: string;
  lifecycle: string;
  evidence: string[];
  artifactKind: "SQL TEST" | "SQL PATCH" | "CONTEXT UPDATE";
  artifactTitle: string;
  artifactPath: string;
  artifactPreview: string;
  checkLabel: string;
  targetStatus: "CONFIRMED" | "EXPIRED";
  turns: Turn[];
};

export const DEMO_ACTOR = "urn:li:corpuser:demo-owner";

export const decisions: DemoDecision[] = [
  {
    id: "decision-6012568173d2",
    contractId: "decision-active-window-v1",
    artifactId: "artifact-active-window-test",
    number: "01",
    label: "Activity window",
    fragment: "activity_at >= current_date - interval '37 days'",
    normalized: "activity_at >= CURRENT_DATE - INTERVAL '37 DAY'",
    kind: "DATE WINDOW",
    risk: 96.2,
    riskReason: "30-day glossary conflict",
    outcome: "CONFIRMED_RULE",
    finding: "Contradictory decision",
    summary: "A deliberate seven-day settlement grace period.",
    rationale:
      "Finance introduced the extension after late card captures caused monthly under-reporting.",
    boundary:
      "Prepaid accounts are identified by billing_type = 'prepaid' and stay on 30 days.",
    lifecycle: "Review on settlement-provider or glossary-definition change.",
    evidence: [
      "interview-active-window:turn-2",
      "interview-active-window:turn-4",
      "urn:li:glossaryTerm:activeCustomer",
    ],
    artifactKind: "SQL TEST",
    artifactTitle: "Prepaid activity-window acceptance test",
    artifactPath: "active_window/test_active_window.sql",
    artifactPreview:
      "postpaid_day_37 → TRUE\npostpaid_day_38 → FALSE\nprepaid_day_30  → TRUE\nprepaid_day_31  → FALSE",
    checkLabel: "4 boundary cases · 0 failing rows",
    targetStatus: "CONFIRMED",
    turns: [
      {
        role: "agent",
        content:
          "The glossary says active within 30 days, but production uses 37 across 47 downstream assets. Was that deliberate? What event led to it?",
        evidence: "DataHub query + glossary",
      },
      {
        role: "owner",
        content:
          "Finance added a seven-day settlement grace period after late card captures caused monthly under-reporting.",
        evidence: "turn-2",
      },
      {
        role: "agent",
        content:
          "Does that grace period also apply to prepaid accounts? If not, which field and value identify them?",
        evidence: "adaptive boundary probe",
      },
      {
        role: "owner",
        content:
          "No. Prepaid accounts use billing_type = 'prepaid' and remain on a 30-day window.",
        evidence: "turn-4",
      },
    ],
  },
  {
    id: "decision-5a2135493239",
    contractId: "decision-germany-hold-v1",
    artifactId: "artifact-germany-patch",
    number: "02",
    label: "Germany exclusion",
    fragment: "country_code <> 'DE'",
    normalized: "country_code <> 'DE'",
    kind: "HARD-CODED EXCLUSION",
    risk: 94.2,
    riskReason: "Temporary marker, no current policy",
    outcome: "EXPIRED_WORKAROUND",
    finding: "Expired decision",
    summary: "A temporary legal hold that outlived its trigger.",
    rationale:
      "Germany was excluded only while the EU billing migration was incomplete.",
    boundary: "The migration completed; German active revenue should be restored.",
    lifecycle: "Expired on 2026-06-30.",
    evidence: [
      "interview-germany-hold:turn-2",
      "interview-germany-hold:turn-4",
      "migration completion date",
    ],
    artifactKind: "SQL PATCH",
    artifactTitle: "Remove expired Germany filter",
    artifactPath: "germany/remove_germany_filter.patch",
    artifactPreview:
      "- AND country_code <> 'DE'\n\nSample regression\n+ de-active\n  de-trial excluded",
    checkLabel: "Expected +1 German active record · 0 regressions",
    targetStatus: "EXPIRED",
    turns: [
      {
        role: "agent",
        content:
          "I found no current glossary rule for excluding Germany. Was this temporary, and what event made it necessary?",
        evidence: "DataHub glossary gap",
      },
      {
        role: "owner",
        content:
          "It was a temporary legal hold during the EU billing migration.",
        evidence: "turn-2",
      },
      {
        role: "agent",
        content:
          "What exact date or observable migration signal makes the filter safe to remove?",
        evidence: "adaptive lifecycle probe",
      },
      {
        role: "owner",
        content:
          "The migration completed on 2026-06-30, so the hold ended that day.",
        evidence: "turn-4",
      },
    ],
  },
  {
    id: "decision-481531201bbd",
    contractId: "decision-active-status-v1",
    artifactId: "artifact-glossary-update",
    number: "03",
    label: "Status exclusions",
    fragment: "account_status NOT IN ('trial', 'refunded')",
    normalized: "NOT account_status IN ('trial', 'refunded')",
    kind: "HARD-CODED EXCLUSION",
    risk: 96.2,
    riskReason: "Dashboard definition drift",
    outcome: "DOCUMENTATION_DRIFT",
    finding: "Contradictory decision",
    summary: "The SQL is right; the shared definition is stale.",
    rationale:
      "Trial and refunded accounts are officially outside active-revenue reporting.",
    boundary:
      "account_status identifies both values; there are no customer-type exceptions.",
    lifecycle: "Review when the account-status taxonomy changes.",
    evidence: [
      "interview-status-rule:turn-2",
      "interview-status-rule:turn-4",
      "dashboard description",
    ],
    artifactKind: "CONTEXT UPDATE",
    artifactTitle: "Update Active Customer definition",
    artifactPath: "status/glossary_update.diff",
    artifactPreview:
      "- Activity within the last 30 days.\n+ Activity within the applicable window.\n+ Trial and refunded accounts are excluded.",
    checkLabel: "Required terms present · context diff valid",
    targetStatus: "CONFIRMED",
    turns: [
      {
        role: "agent",
        content:
          "The dashboard description does not mention status exclusions. Is this filter part of the official active-customer definition?",
        evidence: "DataHub description + SQL",
      },
      {
        role: "owner",
        content:
          "Yes. It is official: trial and refunded accounts are not active revenue customers.",
        evidence: "turn-2",
      },
      {
        role: "agent",
        content:
          "Which field identifies those records, and is there any customer type for which the exclusion should not apply?",
        evidence: "adaptive exception probe",
      },
      {
        role: "owner",
        content:
          "account_status identifies both values and there are no customer-type exceptions.",
        evidence: "turn-4",
      },
    ],
  },
];

export const graphNodes = [
  { id: "raw", label: "raw_activity", x: 48, y: 237, kind: "source" },
  { id: "root", label: "revenue_daily", x: 210, y: 237, kind: "root" },
  { id: "exec", label: "Executive Revenue", x: 420, y: 52, kind: "critical" },
  { id: "close", label: "Monthly Close", x: 485, y: 142, kind: "critical" },
  { id: "kpi", label: "Active KPI", x: 500, y: 237, kind: "critical" },
  { id: "board", label: "Board Pack", x: 485, y: 332, kind: "critical" },
  { id: "region", label: "Regional Revenue", x: 420, y: 422, kind: "normal" },
  { id: "more", label: "+42 more", x: 300, y: 474, kind: "summary" },
];
