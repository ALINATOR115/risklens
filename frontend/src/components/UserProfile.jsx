import React, { useState, useEffect } from "react";
import Badge from "./Badge";
import { riskColor, fmtScore, fmtAmount, fmtTime } from "../utils";

const BASE = "/api/v1";

export default function UserProfile({ userId, onClose }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    fetch(`${BASE}/users/${encodeURIComponent(userId)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setProfile)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [userId]);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.5)",
          zIndex: 90,
        }}
      />

      {/* Panel */}
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          width: 520,
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
              USER PROFILE
            </div>
            <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: "var(--text)" }}>
              {userId}
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
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
          {loading && (
            <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading...</div>
          )}
          {error && (
            <div style={{ color: "var(--high)", fontSize: 13 }}>{error}</div>
          )}

          {profile && (
            <>
              {/* Summary cards */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  gap: 10,
                  marginBottom: 24,
                }}
              >
                {[
                  ["TRANSACTIONS", profile.total_transactions, "var(--text)"],
                  ["MAX SCORE", fmtScore(profile.max_risk_score), riskColor(
                    profile.max_risk_score >= 0.7 ? "high_risk" :
                    profile.max_risk_score >= 0.4 ? "medium_risk" : "low_risk"
                  )],
                  ["AVG SCORE", fmtScore(profile.avg_risk_score), "var(--text-muted)"],
                ].map(([label, value, color]) => (
                  <div
                    key={label}
                    style={{
                      background: "var(--bg)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-sm)",
                      padding: "12px 14px",
                    }}
                  >
                    <div style={{ fontSize: 10, color: "var(--text-dim)", marginBottom: 4 }}>
                      {label}
                    </div>
                    <div className="mono" style={{ fontSize: 18, fontWeight: 700, color }}>
                      {value}
                    </div>
                  </div>
                ))}
              </div>

              {/* Risk breakdown */}
              <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
                {[
                  ["HIGH", profile.risk_counts.high_risk, "var(--high)"],
                  ["MEDIUM", profile.risk_counts.medium_risk, "var(--medium)"],
                  ["LOW", profile.risk_counts.low_risk, "var(--low)"],
                ].map(([label, count, color]) => (
                  <div
                    key={label}
                    style={{
                      flex: 1,
                      padding: "8px 12px",
                      background: "var(--bg)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-sm)",
                      textAlign: "center",
                    }}
                  >
                    <div style={{ fontSize: 10, color: "var(--text-dim)", marginBottom: 2 }}>
                      {label}
                    </div>
                    <div style={{ fontSize: 20, fontWeight: 700, color }}>{count}</div>
                  </div>
                ))}
              </div>

              {/* Transaction history */}
              <div
                style={{
                  fontSize: 11,
                  color: "var(--text-muted)",
                  letterSpacing: "0.06em",
                  marginBottom: 12,
                  textTransform: "uppercase",
                }}
              >
                Transaction history
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {profile.transactions.map((tx, i) => (
                  <div
                    key={i}
                    style={{
                      padding: "10px 14px",
                      background: "var(--bg)",
                      border: `1px solid ${
                        tx.risk_class === "high_risk"
                          ? "var(--high-border)"
                          : tx.risk_class === "medium_risk"
                          ? "var(--medium-border)"
                          : "var(--border)"
                      }`,
                      borderRadius: "var(--radius-sm)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 12,
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        className="mono"
                        style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 2 }}
                      >
                        {tx.transaction_id}
                      </div>
                      <div style={{ fontSize: 13, color: "var(--text)" }}>
                        ${fmtAmount(tx.amount)}
                        <span style={{ color: "var(--text-dim)", marginLeft: 8, fontSize: 11 }}>
                          {fmtTime(tx.transaction_time)}
                        </span>
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span
                        className="mono"
                        style={{
                          fontSize: 12,
                          fontWeight: 600,
                          color: riskColor(tx.risk_class),
                        }}
                      >
                        {fmtScore(tx.final_score)}
                      </span>
                      <Badge riskClass={tx.risk_class} />
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
