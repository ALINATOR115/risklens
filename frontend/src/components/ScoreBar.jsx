import React from "react";
import { fmtScore } from "../utils";

export default function ScoreBar({ score, label, color }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{label}</span>
        <span
          className="mono"
          style={{ fontSize: 11, color: "var(--text)" }}
        >
          {fmtScore(score)}
        </span>
      </div>
      <div
        style={{
          height: 6,
          background: "var(--white-08)",
          borderRadius: 3,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${Math.min(score * 100, 100)}%`,
            background: color || "var(--accent)",
            borderRadius: 3,
            transition: "width 0.6s ease",
          }}
        />
      </div>
    </div>
  );
}
