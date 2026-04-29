import React from "react";
import { riskColor, riskBg, riskBorder, riskLabel } from "../utils";

export default function Badge({ riskClass }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: "var(--radius-xs)",
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: "0.05em",
        color: riskColor(riskClass),
        background: riskBg(riskClass),
        border: `1px solid ${riskBorder(riskClass)}`,
      }}
    >
      {riskLabel(riskClass)}
    </span>
  );
}
