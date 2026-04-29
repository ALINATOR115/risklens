import React from "react";

export default function Header({ isConnected }) {
  return (
    <header
      style={{
        borderBottom: "1px solid var(--border)",
        padding: "14px 32px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 7,
            background: "linear-gradient(135deg, var(--accent), #8B5CF6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
            fontWeight: 800,
            color: "#fff",
          }}
        >
          R
        </div>
        <span style={{ fontWeight: 600, fontSize: 15, letterSpacing: "-0.01em" }}>
          RiskLens
        </span>
        <span
          style={{
            fontSize: 10,
            color: "var(--text-dim)",
            padding: "2px 6px",
            border: "1px solid var(--border)",
            borderRadius: 4,
            marginLeft: 4,
          }}
        >
          v0.1.0
        </span>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <div
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: isConnected ? "var(--low)" : "var(--text-dim)",
            boxShadow: isConnected ? "0 0 6px var(--low)" : "none",
          }}
        />
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
          {isConnected ? "Model active" : "Awaiting data"}
        </span>
      </div>
    </header>
  );
}
