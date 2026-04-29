import React from "react";
import Badge from "./Badge";
import ScoreBar from "./ScoreBar";
import { riskColor, fmtScore, fmtAmount, fmtTime } from "../utils";

export default function DetailPanel({ result, onClose }) {
  if (!result) return null;

  const { breakdown, triggered_rules } = result;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: 420,
        height: "100vh",
        background: "var(--surface)",
        borderLeft: "1px solid var(--border)",
        zIndex: 100,
        display: "flex",
        flexDirection: "column",
        boxShadow: "-8px 0 32px rgba(0,0,0,0.4)",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "20px 24px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>
            TRANSACTION
          </div>
          <div className="mono" style={{ fontSize: 15, color: "var(--text)" }}>
            {result.transaction_id}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "1px solid var(--border)",
            color: "var(--text-muted)",
            width: 32,
            height: 32,
            borderRadius: "var(--radius-sm)",
            cursor: "pointer",
            fontSize: 16,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          ✕
        </button>
      </div>

      {/* Body */}
      <div style={{ padding: 24, overflowY: "auto", flex: 1 }}>
        {/* Risk badge + final score */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
          <Badge riskClass={result.risk_class} />
          <span
            className="mono"
            style={{
              fontSize: 24,
              fontWeight: 700,
              color: riskColor(result.risk_class),
            }}
          >
            {fmtScore(result.final_score)}
          </span>
        </div>

        {/* Meta grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 12,
            marginBottom: 28,
          }}
        >
          {[
            ["User", result.user_id],
            ["Amount", `$${fmtAmount(result.amount)}`],
            ["Time", fmtTime(result.transaction_time)],
          ].map(([k, v]) => (
            <div key={k}>
              <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 2 }}>
                {k}
              </div>
              <div style={{ fontSize: 13, color: "var(--text)" }}>{v}</div>
            </div>
          ))}
        </div>

        {/* Score breakdown */}
        <div style={{ marginBottom: 28 }}>
          <div
            style={{
              fontSize: 11,
              color: "var(--text-muted)",
              letterSpacing: "0.06em",
              marginBottom: 14,
              textTransform: "uppercase",
            }}
          >
            Score breakdown
          </div>
          <ScoreBar score={breakdown.rule_score} label="Rule score" color="#8B5CF6" />
          <ScoreBar
            score={breakdown.behavioral_risk_score}
            label="Behavioral risk"
            color="#F59E0B"
          />
          <ScoreBar score={breakdown.model_score} label="ML model" color="#3B82F6" />
          <div
            style={{
              marginTop: 12,
              paddingTop: 12,
              borderTop: "1px solid var(--border)",
            }}
          >
            <ScoreBar
              score={result.final_score}
              label="Final score"
              color={riskColor(result.risk_class)}
            />
          </div>
        </div>

        {/* Explanations */}
        {result.explanations && result.explanations.length > 0 && (
          <div style={{ marginBottom: 28 }}>
            <div
              style={{
                fontSize: 11,
                color: "var(--text-muted)",
                letterSpacing: "0.06em",
                marginBottom: 10,
                textTransform: "uppercase",
              }}
            >
              Why is this suspicious?
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {result.explanations.map((exp, i) => (
                <div
                  key={i}
                  style={{
                    padding: "10px 12px",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--high-bg)",
                    border: "1px solid var(--high-border)",
                    fontSize: 12,
                    color: "var(--text)",
                    lineHeight: 1.5,
                  }}
                >
                  ⚠ {exp}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Triggered rules */}
        <div>
          <div
            style={{
              fontSize: 11,
              color: "var(--text-muted)",
              letterSpacing: "0.06em",
              marginBottom: 10,
              textTransform: "uppercase",
            }}
          >
            Triggered rules
          </div>
          {triggered_rules && triggered_rules.length > 0 ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {triggered_rules.map((r) => (
                <span
                  key={r}
                  className="mono"
                  style={{
                    padding: "4px 10px",
                    borderRadius: "var(--radius-xs)",
                    fontSize: 11,
                    background: "var(--white-08)",
                    color: "var(--text)",
                    border: "1px solid var(--border)",
                  }}
                >
                  {r}
                </span>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: 12, color: "var(--text-dim)" }}>
              No rules triggered
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
