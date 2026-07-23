import type { CSSProperties, ReactNode } from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const COLORS = {
  ink: "#101612",
  ink2: "#182019",
  paper: "#eef0e9",
  muted: "#929c93",
  line: "#364137",
  acid: "#b8f34a",
  coral: "#ff7657",
  cyan: "#64d8dc",
  gold: "#f4c95d",
};

const ease = Easing.bezier(0.16, 1, 0.3, 1);

const labelStyle: CSSProperties = {
  fontFamily: "Inter, Arial, sans-serif",
  fontSize: 25,
  fontWeight: 700,
  letterSpacing: 5,
  color: COLORS.acid,
  textTransform: "uppercase",
};

const headlineStyle: CSSProperties = {
  fontFamily: "Inter, Arial, sans-serif",
  color: COLORS.paper,
  fontSize: 94,
  lineHeight: 1.02,
  letterSpacing: -5,
  fontWeight: 650,
  margin: 0,
};

const bodyStyle: CSSProperties = {
  fontFamily: "Inter, Arial, sans-serif",
  color: COLORS.muted,
  fontSize: 39,
  lineHeight: 1.35,
  margin: 0,
};

const monoStyle: CSSProperties = {
  fontFamily: "SFMono-Regular, Menlo, Consolas, monospace",
};

const enter = (frame: number, delay = 0) => ({
  opacity: interpolate(frame, [delay, delay + 24], [0, 1], {
    extrapolateLeft: "clamp" as const,
    extrapolateRight: "clamp" as const,
    easing: ease,
  }),
  translate: `0 ${interpolate(frame, [delay, delay + 28], [34, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  })}px`,
});

const Scene = ({ children, duration }: { children: ReactNode; duration: number }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.ink,
        color: COLORS.paper,
        padding: "100px 118px",
        opacity: interpolate(frame, [0, 16, duration - 18, duration], [0, 1, 1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
      }}
    >
      <div className="frame-rule frame-rule-top" />
      <div className="frame-rule frame-rule-bottom" />
      <div className="frame-index">RATIONALEOPS / BUILD WITH DATAHUB</div>
      {children}
    </AbsoluteFill>
  );
};

const Brand = ({ compact = false }: { compact?: boolean }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
    <div
      style={{
        width: compact ? 54 : 72,
        height: compact ? 54 : 72,
        border: `2px solid ${COLORS.acid}`,
        display: "grid",
        placeItems: "center",
        color: COLORS.acid,
        fontSize: compact ? 26 : 34,
        fontWeight: 800,
        ...monoStyle,
      }}
    >
      R
    </div>
    <div>
      <div style={{ fontFamily: "Inter, Arial", fontSize: compact ? 29 : 42, fontWeight: 720 }}>RationaleOps</div>
      <div style={{ ...monoStyle, color: COLORS.muted, fontSize: compact ? 13 : 17, letterSpacing: 2.5, marginTop: 5 }}>DECISION INTELLIGENCE FOR DATAHUB</div>
    </div>
  </div>
);

const HookScene = ({ duration }: { duration: number }) => {
  const frame = useCurrentFrame();
  const filters = [
    ["activity_at >= current_date - interval", "'37 days'"],
    ["country_code <>", "'DE'"],
    ["account_status NOT IN", "('trial', 'refunded')"],
  ];
  return (
    <Scene duration={duration}>
      <div style={{ ...enter(frame, 4), display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Brand compact />
        <span style={{ ...labelStyle, color: COLORS.coral }}>THE HIDDEN DECISION PROBLEM</span>
      </div>
      <div style={{ marginTop: 95, maxWidth: 1460 }}>
        <h1 style={{ ...headlineStyle, ...enter(frame, 20), fontSize: 108 }}>
          Every strange filter is a <span style={{ color: COLORS.acid }}>rule</span>, a <span style={{ color: COLORS.coral }}>workaround</span>, or a bug.
        </h1>
        <p style={{ ...bodyStyle, ...enter(frame, 45), marginTop: 35 }}>The code alone cannot tell you which.</p>
      </div>
      <div style={{ display: "grid", gap: 14, marginTop: 74, ...monoStyle }}>
        {filters.map(([left, value], index) => (
          <div
            key={value}
            style={{
              ...enter(frame, 70 + index * 18),
              borderLeft: `4px solid ${index === 1 ? COLORS.coral : index === 2 ? COLORS.cyan : COLORS.acid}`,
              backgroundColor: COLORS.ink2,
              padding: "19px 24px",
              fontSize: 31,
              color: "#bbc2bb",
            }}
          >
            {left} <span style={{ color: index === 1 ? COLORS.coral : index === 2 ? COLORS.cyan : COLORS.acid }}>{value}</span>
          </div>
        ))}
      </div>
    </Scene>
  );
};

const ContextScene = ({ duration }: { duration: number }) => {
  const frame = useCurrentFrame();
  const consumers = ["Executive Revenue", "Monthly Close", "Active KPI", "Board Pack", "+43 more"];
  return (
    <Scene duration={duration}>
      <div style={{ ...labelStyle, ...enter(frame, 4) }}>01 · DATAHUB IS THE EVIDENCE LAYER</div>
      <div style={{ display: "grid", gridTemplateColumns: ".9fr 1.1fr", gap: 80, alignItems: "center", flex: 1 }}>
        <div>
          <h2 style={{ ...headlineStyle, ...enter(frame, 18) }}>Find the decision with the biggest blast radius.</h2>
          <div style={{ display: "flex", alignItems: "baseline", gap: 25, marginTop: 55, ...enter(frame, 50) }}>
            <strong style={{ ...monoStyle, fontSize: 170, lineHeight: 1, color: COLORS.acid, letterSpacing: -15 }}>47</strong>
            <span style={{ ...bodyStyle, fontSize: 35 }}>downstream assets<br />share the same hidden logic</span>
          </div>
          <div style={{ ...monoStyle, marginTop: 46, fontSize: 23, color: COLORS.cyan, letterSpacing: 2, ...enter(frame, 74) }}>QUERY · LINEAGE · SCHEMA · OWNER · GLOSSARY</div>
        </div>
        <div style={{ position: "relative", height: 650 }}>
          <svg viewBox="0 0 760 650" style={{ width: "100%", height: "100%" }}>
            {consumers.map((_, index) => {
              const y = 74 + index * 126;
              return <line key={y} x1="220" y1="325" x2="500" y2={y} stroke={COLORS.line} strokeWidth="3" strokeDasharray="9 10" />;
            })}
            <circle cx="195" cy="325" r="96" fill={COLORS.acid} />
            <circle cx="195" cy="325" r="112" fill="none" stroke={COLORS.acid} strokeOpacity=".25" strokeWidth="3" strokeDasharray="7 10" />
            <text x="195" y="320" textAnchor="middle" fill={COLORS.ink} fontFamily="monospace" fontSize="30" fontWeight="800">RD</text>
            <text x="195" y="360" textAnchor="middle" fill={COLORS.ink} fontFamily="monospace" fontSize="17" fontWeight="700">revenue_daily</text>
            {consumers.map((name, index) => {
              const y = 74 + index * 126;
              return (
                <g key={name} style={{ opacity: interpolate(frame, [36 + index * 12, 58 + index * 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
                  <circle cx="520" cy={y} r="35" fill={COLORS.ink2} stroke={index < 4 ? COLORS.coral : COLORS.cyan} strokeWidth="3" />
                  <text x="575" y={y + 9} fill={COLORS.paper} fontFamily="Inter, Arial" fontSize="27">{name}</text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    </Scene>
  );
};

const ScreenshotScene = ({ duration, file, label, title, accent, zoom = 1 }: { duration: number; file: string; label: string; title: string; accent: string; zoom?: number }) => {
  const frame = useCurrentFrame();
  return (
    <Scene duration={duration}>
      <div style={{ marginBottom: 32 }}>
        <div>
          <div style={{ ...labelStyle, color: accent, ...enter(frame, 4) }}>{label}</div>
          <h2 style={{ ...headlineStyle, fontSize: 72, marginTop: 15, ...enter(frame, 16) }}>{title}</h2>
        </div>
      </div>
      <div style={{ flex: 1, overflow: "hidden", border: `2px solid ${COLORS.line}`, backgroundColor: "#0b100c", ...enter(frame, 30) }}>
        <Img
          src={staticFile(file)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "center top",
            scale: interpolate(frame, [30, duration - 25], [zoom, zoom + 0.035], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }),
          }}
        />
      </div>
    </Scene>
  );
};

const InterviewScene = ({ duration }: { duration: number }) => {
  const frame = useCurrentFrame();
  return (
    <Scene duration={duration}>
      <div style={{ ...labelStyle, ...enter(frame, 4) }}>03 · COGNITIVE TASK ANALYSIS</div>
      <h2 style={{ ...headlineStyle, fontSize: 79, marginTop: 18, ...enter(frame, 14) }}>Ask for the boundary the first answer leaves out.</h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 34, marginTop: 54, alignItems: "stretch" }}>
        <div style={{ border: `2px solid ${COLORS.line}`, backgroundColor: COLORS.ink2, padding: 35, ...enter(frame, 35) }}>
          <div style={{ ...labelStyle, fontSize: 18 }}>OWNER · TURN 2</div>
          <p style={{ ...bodyStyle, color: COLORS.paper, fontSize: 37, marginTop: 27 }}>
            “Finance added a seven-day settlement grace period after late card captures caused under-reporting.”
          </p>
        </div>
        <div style={{ border: `2px solid ${COLORS.acid}`, backgroundColor: "#121a13", padding: 35, ...enter(frame, 74) }}>
          <div style={{ ...labelStyle, fontSize: 18 }}>ADAPTIVE COUNTERFACTUAL</div>
          <p style={{ ...bodyStyle, color: COLORS.paper, fontSize: 37, marginTop: 27 }}>
            “Does that grace period also apply to prepaid accounts? Which field identifies them?”
          </p>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 25, marginTop: 45, ...enter(frame, 110) }}>
        <span style={{ width: 62, height: 62, display: "grid", placeItems: "center", border: `2px solid ${COLORS.cyan}`, color: COLORS.cyan, fontSize: 30 }}>✓</span>
        <p style={{ ...bodyStyle, fontSize: 32, color: COLORS.cyan }}>New executable exception discovered: <span style={{ ...monoStyle, color: COLORS.paper }}>billing_type = &apos;prepaid&apos; → 30 days</span></p>
      </div>
    </Scene>
  );
};

const OutcomesScene = ({ duration }: { duration: number }) => {
  const frame = useCurrentFrame();
  const outcomes = [
    { index: "01", title: "CONFIRMED RULE", color: COLORS.acid, text: "37 days is deliberate. Preserve the prepaid boundary as a test.", icon: "✓" },
    { index: "02", title: "EXPIRED WORKAROUND", color: COLORS.coral, text: "The EU migration ended. Remove the Germany exclusion safely.", icon: "!" },
    { index: "03", title: "DOCUMENTATION DRIFT", color: COLORS.cyan, text: "The SQL is right. Update the stale Active Customer definition.", icon: "↻" },
  ];
  return (
    <Scene duration={duration}>
      <div style={{ ...labelStyle, ...enter(frame, 4) }}>THE WOW MOMENT</div>
      <h2 style={{ ...headlineStyle, marginTop: 18, ...enter(frame, 15) }}>Three similar filters. Three different actions.</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 25, marginTop: 72 }}>
        {outcomes.map((item, index) => (
          <div key={item.title} style={{ borderTop: `7px solid ${item.color}`, borderLeft: `2px solid ${COLORS.line}`, borderRight: `2px solid ${COLORS.line}`, borderBottom: `2px solid ${COLORS.line}`, backgroundColor: COLORS.ink2, minHeight: 470, padding: 35, ...enter(frame, 40 + index * 38) }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ ...monoStyle, color: COLORS.muted, fontSize: 24 }}>{item.index}</span>
              <span style={{ width: 68, height: 68, display: "grid", placeItems: "center", border: `2px solid ${item.color}`, color: item.color, fontSize: 34 }}>{item.icon}</span>
            </div>
            <h3 style={{ ...monoStyle, color: item.color, fontSize: 34, lineHeight: 1.2, margin: "68px 0 28px" }}>{item.title}</h3>
            <p style={{ ...bodyStyle, color: COLORS.paper, fontSize: 31 }}>{item.text}</p>
          </div>
        ))}
      </div>
    </Scene>
  );
};

const ArtifactsScene = ({ duration }: { duration: number }) => {
  const frame = useCurrentFrame();
  const rows = [
    ["SQL TEST", "4 boundary cases · 0 failing rows", COLORS.acid],
    ["SQL PATCH", "+1 expected German record · 0 regressions", COLORS.coral],
    ["CONTEXT DIFF", "trial · refunded · account_status present", COLORS.cyan],
  ] as const;
  return (
    <Scene duration={duration}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr .95fr", gap: 65, flex: 1, alignItems: "center" }}>
        <div>
          <div style={{ ...labelStyle, ...enter(frame, 4) }}>04 · OPERATIONALIZE</div>
          <h2 style={{ ...headlineStyle, marginTop: 20, ...enter(frame, 16) }}>Every confirmed decision produces something executable.</h2>
          <p style={{ ...bodyStyle, marginTop: 35, ...enter(frame, 38) }}>The model may draft. Deterministic code decides whether the artifact passes.</p>
        </div>
        <div style={{ display: "grid", gap: 22 }}>
          {rows.map(([kind, check, color], index) => (
            <div key={kind} style={{ border: `2px solid ${COLORS.line}`, backgroundColor: COLORS.ink2, padding: "28px 30px", ...enter(frame, 45 + index * 34) }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ ...monoStyle, fontSize: 27, color }}>{kind}</strong>
                <span style={{ color, fontSize: 31 }}>✓</span>
              </div>
              <p style={{ ...bodyStyle, color: COLORS.paper, fontSize: 28, marginTop: 22 }}>{check}</p>
              <div style={{ ...monoStyle, color: COLORS.muted, fontSize: 17, marginTop: 18 }}>DETERMINISTIC CHECK PASSED</div>
            </div>
          ))}
        </div>
      </div>
    </Scene>
  );
};

const TrustScene = ({ duration }: { duration: number }) => {
  const frame = useCurrentFrame();
  const steps = [
    ["1", "OWNER CONFIRMS", "Only the authorized Finance owner can cross the truth boundary.", COLORS.acid],
    ["2", "CODE VERIFIES", "Tests and sample regressions must pass before action approval.", COLORS.cyan],
    ["3", "DATAHUB PRESERVES", "Each write has its own explicit approval and read-back proof.", COLORS.coral],
  ] as const;
  return (
    <Scene duration={duration}>
      <div style={{ ...labelStyle, ...enter(frame, 4) }}>THE SAFETY MODEL</div>
      <h2 style={{ ...headlineStyle, marginTop: 20, ...enter(frame, 15) }}>No plausible story silently becomes policy.</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 38, marginTop: 105 }}>
        {steps.map(([number, title, text, color], index) => (
          <div key={title} style={{ position: "relative", ...enter(frame, 45 + index * 38) }}>
            <div style={{ width: 86, height: 86, display: "grid", placeItems: "center", backgroundColor: color, color: COLORS.ink, fontSize: 38, fontWeight: 800, ...monoStyle }}>{number}</div>
            <h3 style={{ ...monoStyle, color, fontSize: 31, margin: "35px 0 20px" }}>{title}</h3>
            <p style={{ ...bodyStyle, color: COLORS.paper, fontSize: 30 }}>{text}</p>
            {index < 2 && <div style={{ position: "absolute", width: 48, height: 2, backgroundColor: COLORS.line, right: -43, top: 42 }} />}
          </div>
        ))}
      </div>
      <div style={{ marginTop: 100, border: `2px solid ${COLORS.line}`, padding: "25px 32px", display: "flex", justifyContent: "space-between", ...monoStyle, fontSize: 22, ...enter(frame, 120) }}>
        <span style={{ color: COLORS.acid }}>3 DECISIONS</span>
        <span style={{ color: COLORS.acid }}>ALL CHECKS PASS</span>
        <span style={{ color: COLORS.acid }}>0 UNCONFIRMED PUBLISHED</span>
      </div>
    </Scene>
  );
};

const ProofScene = ({ duration }: { duration: number }) => {
  const frame = useCurrentFrame();
  return (
    <Scene duration={duration}>
      <div style={{ display: "grid", gridTemplateColumns: "1.1fr .9fr", gap: 90, flex: 1, alignItems: "center" }}>
        <div>
          <div style={{ ...labelStyle, ...enter(frame, 4) }}>REAL DATAHUB READ + WRITE</div>
          <h2 style={{ ...headlineStyle, marginTop: 20, ...enter(frame, 16) }}>The why is now retrievable where the data lives.</h2>
          <p style={{ ...bodyStyle, marginTop: 38, ...enter(frame, 40) }}>Official MCP read: query, schema, owner, glossary, and exactly 47 downstream assets.</p>
        </div>
        <div style={{ ...monoStyle, backgroundColor: "#0b100c", border: `2px solid ${COLORS.line}`, padding: 38, fontSize: 24, lineHeight: 1.7, ...enter(frame, 55) }}>
          <div style={{ color: COLORS.muted }}>{"{"}</div>
          <div>  <span style={{ color: COLORS.cyan }}>&quot;contract_id&quot;</span>: &quot;decision-active-window-v1&quot;,</div>
          <div>  <span style={{ color: COLORS.cyan }}>&quot;status&quot;</span>: <span style={{ color: COLORS.acid }}>&quot;CONFIRMED&quot;</span>,</div>
          <div>  <span style={{ color: COLORS.cyan }}>&quot;outcome&quot;</span>: &quot;CONFIRMED_RULE&quot;,</div>
          <div>  <span style={{ color: COLORS.cyan }}>&quot;retrievable&quot;</span>: <span style={{ color: COLORS.acid }}>true</span>,</div>
          <div>  <span style={{ color: COLORS.cyan }}>&quot;stored_fields&quot;</span>: 21</div>
          <div style={{ color: COLORS.muted }}>{"}"}</div>
          <div style={{ marginTop: 28, borderTop: `1px solid ${COLORS.line}`, paddingTop: 24, color: COLORS.acid }}>✓ WRITE-BACK VERIFIED</div>
        </div>
      </div>
    </Scene>
  );
};

const ClosingScene = ({ duration }: { duration: number }) => {
  const frame = useCurrentFrame();
  return (
    <Scene duration={duration}>
      <div style={{ flex: 1, display: "grid", placeItems: "center", textAlign: "center" }}>
        <div>
          <div style={{ display: "flex", justifyContent: "center", ...enter(frame, 4) }}><Brand /></div>
          <h2 style={{ ...headlineStyle, fontSize: 116, maxWidth: 1450, margin: "100px auto 0", ...enter(frame, 25) }}>
            The code remembers <span style={{ color: COLORS.muted }}>what.</span><br />RationaleOps preserves <span style={{ color: COLORS.acid }}>why.</span>
          </h2>
          <div style={{ display: "flex", justifyContent: "center", gap: 20, marginTop: 75, ...enter(frame, 58) }}>
            {["DATAHUB-GROUNDED", "HUMAN-CONFIRMED", "DETERMINISTICALLY-VERIFIED"].map((item) => (
              <span key={item} style={{ ...monoStyle, border: `2px solid ${COLORS.line}`, padding: "16px 21px", color: COLORS.cyan, fontSize: 18 }}>{item}</span>
            ))}
          </div>
        </div>
      </div>
    </Scene>
  );
};

export const RationaleOpsVideo = () => {
  const { fps } = useVideoConfig();
  const scenes = {
    hook: 12 * fps,
    context: 12 * fps,
    radar: 10 * fps,
    interview: 14 * fps,
    outcomes: 13 * fps,
    artifactScreenshot: 9 * fps,
    artifacts: 11 * fps,
    trust: 10 * fps,
    proof: 10 * fps,
    close: 9 * fps,
  };
  let from = 0;
  const place = (duration: number, child: ReactNode) => {
    const start = from;
    from += duration;
    return <Sequence key={start} from={start} durationInFrames={duration}>{child}</Sequence>;
  };
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.ink }}>
      {place(scenes.hook, <HookScene duration={scenes.hook} />)}
      {place(scenes.context, <ContextScene duration={scenes.context} />)}
      {place(scenes.radar, <ScreenshotScene duration={scenes.radar} file="dashboard-initial.png" label="02 · DETERMINISTIC RISK RADAR" title="Mine the exact SQL. Rank the knowledge risk." accent={COLORS.cyan} />)}
      {place(scenes.interview, <InterviewScene duration={scenes.interview} />)}
      {place(scenes.outcomes, <OutcomesScene duration={scenes.outcomes} />)}
      {place(scenes.artifactScreenshot, <ScreenshotScene duration={scenes.artifactScreenshot} file="dashboard-action.png" label="VALIDATED ACTION WORKBENCH" title="Owner-confirmed intent becomes a passing test." accent={COLORS.acid} zoom={1.01} />)}
      {place(scenes.artifacts, <ArtifactsScene duration={scenes.artifacts} />)}
      {place(scenes.trust, <TrustScene duration={scenes.trust} />)}
      {place(scenes.proof, <ProofScene duration={scenes.proof} />)}
      {place(scenes.close, <ClosingScene duration={scenes.close} />)}
    </AbsoluteFill>
  );
};

export const VIDEO_DURATION_FRAMES = 110 * 30;
