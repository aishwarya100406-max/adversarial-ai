import React, { useState, useMemo, useCallback, useEffect, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

const CONFIDENCE_COLORS = {
  strong: "#3ddc97",
  moderate: "#e0c341",
  weak: "#e08a34",
  unverified: "#e0453f",
};

const SAMPLE_QUERIES = [
  "Did the 2023 Silicon Valley Bank collapse stem from interest rate risk mismanagement?",
  "Did the largest EV battery recall of 2023 stem from a known design flaw?",
  "Did Boeing's 737 MAX door-plug incident in 2024 stem from a known manufacturing defect?",
];

function buildGraphData(result) {
  const nodes = [];
  const links = [];

  result.sub_questions.forEach((sq, i) => {
    nodes.push({ id: `sq-${i}`, label: sq, type: "subquestion" });
  });

  result.claims.forEach((claim) => {
    nodes.push({ id: claim.id, label: claim.text, type: "claim", claim });
    const sqIndex = result.sub_questions.indexOf(claim.sub_question);
    if (sqIndex !== -1) {
      links.push({ source: `sq-${sqIndex}`, target: claim.id, type: "decomposes" });
    }
    claim.edges.forEach((edge) => {
      links.push({
        source: edge.source_id,
        target: claim.id,
        type: edge.stance,
        stance_confidence: edge.stance_confidence,
      });
    });
  });

  result.sources.forEach((src) => {
    nodes.push({ id: src.id, label: src.title || src.domain, type: "source", source: src });
  });

  return { nodes, links };
}

export default function App() {
  const [query, setQuery] = useState(SAMPLE_QUERIES[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [selected, setSelected] = useState(null);
  const [showLog, setShowLog] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [showIntro, setShowIntro] = useState(true);
  const timerRef = useRef(null);

  const graphData = useMemo(() => (result ? buildGraphData(result) : { nodes: [], links: [] }), [result]);

  useEffect(() => {
    if (loading) {
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => timerRef.current && clearInterval(timerRef.current);
  }, [loading]);

  const runInvestigation = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setSelected(null);
    try {
      const res = await fetch(`${API_BASE}/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text);
      }
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, [query]);

  const nodeColor = (node) => {
    if (node.type === "subquestion") return "#6c7a96";
    if (node.type === "source") {
      const tier = node.source?.reliability_tier;
      return tier === "primary" ? "#4f8ff7" : tier === "secondary" ? "#8badf0" : "#c9d3e3";
    }
    if (node.type === "claim") return CONFIDENCE_COLORS[node.claim?.confidence_label] || "#999";
    return "#999";
  };

  const linkColor = (link) => {
    if (link.type === "supports") return "#3ddc97aa";
    if (link.type === "contradicts") return "#e0453faa";
    if (link.type === "decomposes") return "#4b5568";
    return "#666";
  };

  return (
    <div className="avg-root">
      {showIntro && <IntroModal onClose={() => setShowIntro(false)} />}

      <header className="avg-header">
        <span className="avg-logo">🕵️ Adversarial Verification Graph</span>
        <input
          className="avg-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter an investigative question..."
          onKeyDown={(e) => e.key === "Enter" && !loading && runInvestigation()}
        />
        <button className="avg-btn" onClick={runInvestigation} disabled={loading}>
          {loading ? `Investigating (${elapsed}s)` : "Investigate"}
        </button>
        {result && (
          <button className="avg-btn-secondary" onClick={() => setShowLog((s) => !s)}>
            {showLog ? "Hide" : "Show"} Log
          </button>
        )}
        <button className="avg-intro-btn" onClick={() => setShowIntro(true)}>
          How it works
        </button>
      </header>

      <div className="avg-legend">
        <span><span className="avg-legend-dot" style={{ background: CONFIDENCE_COLORS.strong }} />Strong claim</span>
        <span><span className="avg-legend-dot" style={{ background: CONFIDENCE_COLORS.moderate }} />Moderate</span>
        <span><span className="avg-legend-dot" style={{ background: CONFIDENCE_COLORS.weak }} />Weak</span>
        <span><span className="avg-legend-dot" style={{ background: CONFIDENCE_COLORS.unverified }} />Unverified</span>
        <span style={{ marginLeft: 8 }}><span className="avg-legend-dot" style={{ background: "#4f8ff7" }} />Primary source</span>
        <span><span className="avg-legend-dot" style={{ background: "#8badf0" }} />Secondary source</span>
        <span><span className="avg-legend-dot" style={{ background: "#c9d3e3" }} />Tertiary source</span>
        <span style={{ marginLeft: 8 }}><span className="avg-legend-dot" style={{ background: "#6c7a96" }} />Sub-question</span>
      </div>

      {error && <div style={{ padding: 12, background: "#3a1a1a", color: "#ff9a9a" }}>{error}</div>}

      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        <div style={{ flex: 1, position: "relative" }}>
          {!result && !loading && (
            <div className="avg-empty-state">
              <div style={{ fontSize: 15 }}>Enter a question and click Investigate to build the claim graph.</div>
              <div style={{ fontSize: 12, opacity: 0.8 }}>Try one of these:</div>
              {SAMPLE_QUERIES.map((q, i) => (
                <button
                  key={i}
                  className="avg-btn-secondary"
                  style={{ fontSize: 12 }}
                  onClick={() => setQuery(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          )}
          {loading && (
            <div className="avg-loading-state">
              <div className="avg-spinner" />
              <div className="avg-dots"><span /><span /><span /></div>
              <div>Planner → Retrieval → Claim Extraction → Red-Team → Synthesis</div>
              <div style={{ fontSize: 12, maxWidth: 380 }}>
                This can take 60-150s — each claim gets its own adversarial check by a
                separate red-team agent before it's shown to you.
              </div>
            </div>
          )}
          {result && result.claims.length === 0 && !loading && (
            <div className="avg-empty-state">
              <div>No verifiable claims were extracted for this query.</div>
              <div style={{ fontSize: 12, maxWidth: 360 }}>
                This usually means web search found no relevant sources for the generated
                sub-questions. Try a more specific, factual question naming a specific event,
                company, or year. Click "Show Log" to see which sub-question searches returned nothing.
              </div>
            </div>
          )}
          {result && result.claims.length > 0 && (
            <div className="avg-graph-wrap">
              <ForceGraph2D
                graphData={graphData}
                nodeLabel={(n) => n.label}
                nodeColor={nodeColor}
                linkColor={linkColor}
                linkDirectionalArrowLength={4}
                linkWidth={(l) => (l.stance_confidence ? 1 + l.stance_confidence * 2 : 1)}
                nodeRelSize={5}
                onNodeClick={(node) => setSelected(node)}
                backgroundColor="#0b0e14"
                cooldownTime={4000}
              />
            </div>
          )}
          {showLog && result && (
            <div className="avg-pipelinelog">
              {result.pipeline_log.map((l, i) => (
                <div key={i}>{l}</div>
              ))}
            </div>
          )}
        </div>

        <div className="avg-panel">
          {!selected && <div style={{ color: "#6c7a96" }}>Click a node to inspect its evidence.</div>}
          {selected?.type === "claim" && <ClaimPanel claim={selected.claim} sources={result.sources} />}
          {selected?.type === "source" && <SourcePanel source={selected.source} />}
          {selected?.type === "subquestion" && (
            <div>
              <div style={{ fontSize: 12, color: "#6c7a96", marginBottom: 6 }}>SUB-QUESTION</div>
              <div>{selected.label}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function IntroModal({ onClose }) {
  return (
    <div className="avg-modal-backdrop" onClick={onClose}>
      <div className="avg-modal" onClick={(e) => e.stopPropagation()}>
        <h2>🕵️ Adversarial Verification Graph</h2>
        <p style={{ color: "#aab4c6", marginTop: -6 }}>
          An OSINT agent that doesn't just cite sources — it argues with itself before
          telling you anything.
        </p>

        <div className="avg-step">
          <div className="avg-step-num">1</div>
          <div><strong>Planner</strong> breaks your question into small, checkable sub-questions.</div>
        </div>
        <div className="avg-step">
          <div className="avg-step-num">2</div>
          <div><strong>Retrieval</strong> searches the web for real sources for each sub-question.</div>
        </div>
        <div className="avg-step">
          <div className="avg-step-num">3</div>
          <div><strong>Claim Extraction</strong> pulls out atomic claims and tags each source as
          supporting, contradicting, or neutral — while scoring source independence (so 5 reprints
          of one wire story don't count as 5 proofs).</div>
        </div>
        <div className="avg-step">
          <div className="avg-step-num">4</div>
          <div><strong>Red-Team Agent</strong> — a separate agent whose only job is to attack each
          claim: causal overreach, independence collapse, conflict of interest, weak methodology.</div>
        </div>
        <div className="avg-step">
          <div className="avg-step-num">5</div>
          <div><strong>Confidence Synthesis</strong> combines support, contradiction, and the
          red-team's rebuttal strength into one transparent, visible formula per claim.</div>
        </div>

        <p style={{ fontSize: 13, color: "#8892a6", marginTop: 20 }}>
          Click any node in the graph to see the full evidence trail. Green = strong claim,
          red = unverified/attacked. Nothing is a black box — every score can be clicked open.
        </p>
        <button className="avg-btn" onClick={onClose} style={{ marginTop: 8 }}>Got it — let's investigate</button>
      </div>
    </div>
  );
}

function ClaimPanel({ claim, sources }) {
  const bySource = Object.fromEntries(sources.map((s) => [s.id, s]));
  const color = CONFIDENCE_COLORS[claim.confidence_label];
  return (
    <div>
      <div style={{ fontSize: 12, color: "#6c7a96", marginBottom: 6 }}>CLAIM</div>
      <div style={{ marginBottom: 12 }}>{claim.text}</div>

      <div
        className={`avg-badge ${claim.confidence_label === "strong" ? "avg-badge-strong" : ""}`}
        style={{ background: color + "33", color, border: `1px solid ${color}` }}
      >
        {claim.confidence_label.toUpperCase()} · {(claim.confidence * 100).toFixed(0)}%
      </div>

      <div style={{ fontSize: 11, fontFamily: "monospace", color: "#8892a6", marginBottom: 14, wordBreak: "break-word" }}>
        {claim.confidence_formula}
      </div>

      <div style={{ fontSize: 12, color: "#6c7a96", marginBottom: 4 }}>RED-TEAM REBUTTAL</div>
      {claim.rebuttal ? (
        <div className="avg-rebuttal-box">
          <div style={{ fontSize: 11, color: "#e08a8a", marginBottom: 4 }}>
            {claim.rebuttal.rebuttal_type.replace(/_/g, " ")} · strength {(claim.rebuttal.strength * 100).toFixed(0)}%
          </div>
          <div>{claim.rebuttal.text}</div>
        </div>
      ) : (
        <div style={{ color: "#6c7a96", marginBottom: 14 }}>none</div>
      )}

      <div style={{ fontSize: 12, color: "#6c7a96", marginBottom: 4 }}>SOURCES ({claim.edges.length})</div>
      {claim.edges.map((e, i) => {
        const src = bySource[e.source_id];
        return (
          <div key={i} className="avg-source-card">
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: e.stance === "supports" ? "#3ddc97" : e.stance === "contradicts" ? "#e0453f" : "#999" }}>
                {e.stance}
              </span>
              <span style={{ color: "#6c7a96" }}>{src?.reliability_tier}</span>
            </div>
            <a href={src?.url} target="_blank" rel="noreferrer" style={{ color: "#8badf0" }}>
              {src?.title || src?.url}
            </a>
          </div>
        );
      })}
    </div>
  );
}

function SourcePanel({ source }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "#6c7a96", marginBottom: 6 }}>SOURCE</div>
      <div style={{ marginBottom: 8 }}>{source.title}</div>
      <a href={source.url} target="_blank" rel="noreferrer" style={{ color: "#8badf0" }}>
        {source.url}
      </a>
      <div style={{ marginTop: 10, fontSize: 13, color: "#aab4c6" }}>{source.snippet}</div>
      <div style={{ marginTop: 10, fontSize: 12 }}>
        Reliability: {source.reliability_tier} ({(source.reliability_score * 100).toFixed(0)}%)
        <br />
        Publisher cluster: {source.publisher_cluster}
      </div>
    </div>
  );
}
