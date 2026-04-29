import React from "react";

export default function StatCard({ label, value, sub, color }) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "20px 24px",
        flex: 1,
        minWidth: 160,
      }}
    >
      <div
        style={{
          fontSize: 12,
          color: "var(--text-muted)",
          marginBottom: 6,
          letterSpacing: "0.04em",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
          color: color || "var(--text)",
          lineHeight: 1.1,
        }}
      >
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>
          {sub}
        </div>
      )}
    </div>
  );
}
