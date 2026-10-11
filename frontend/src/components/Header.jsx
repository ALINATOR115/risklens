import React from "react";

export default function Header({ isConnected }) {
  return (
   <header
        style={{
            background: "#0f172a",
            padding: "14px 32px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            boxShadow: "0 1px 0 rgba(255,255,255,0.06)",
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
        <span style={{ fontWeight: 600, fontSize: 15, letterSpacing: "-0.01em", color: "#ffffff" }}>
          RiskLens
        </span>

      </div>
    </header>
  );
}
