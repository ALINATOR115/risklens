import React, { useState } from "react";

const REQUIRED = [
  { key: "user_id", label: "User ID", hint: "Who made the transaction?" },
  { key: "amount", label: "Amount", hint: "Transaction sum (numeric)" },
  { key: "transaction_time", label: "Timestamp", hint: "When it happened" },
];

export default function ColumnMapper({ columns, sample, guess, onConfirm, onCancel }) {
  const [mapping, setMapping] = useState({
    user_id: guess?.user_id || "",
    amount: guess?.amount || "",
    transaction_time: guess?.transaction_time || "",
  });

  const isReady = REQUIRED.every((f) => mapping[f.key]);
  const hasDuplicates = new Set(Object.values(mapping).filter(Boolean)).size < 3;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.6)",
        zIndex: 200,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 14,
          width: 480,
          boxShadow: "0 24px 64px rgba(0,0,0,0.5)",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "22px 28px 18px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>
            Map your columns
          </div>
          <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
            Your CSV has {columns.length} columns. Tell us which ones to use.
          </div>
        </div>

        {/* Mapping selectors */}
        <div style={{ padding: "22px 28px", display: "flex", flexDirection: "column", gap: 18 }}>
          {REQUIRED.map(({ key, label, hint }) => {
            const selected = mapping[key];
            const sampleVal = selected && sample[selected] ? sample[selected] : null;

            return (
              <div key={key}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <div>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{label}</span>
                    <span style={{ fontSize: 11, color: "var(--text-dim)", marginLeft: 8 }}>
                      {hint}
                    </span>
                  </div>
                  {sampleVal && (
                    <span
                      className="mono"
                      style={{
                        fontSize: 11,
                        color: "var(--text-muted)",
                        background: "var(--white-08)",
                        padding: "1px 6px",
                        borderRadius: 3,
                      }}
                    >
                      e.g. {sampleVal.length > 20 ? sampleVal.slice(0, 20) + "…" : sampleVal}
                    </span>
                  )}
                </div>
                <select
                  value={selected}
                  onChange={(e) => setMapping({ ...mapping, [key]: e.target.value })}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: "var(--bg)",
                    border: `1px solid ${selected ? "var(--accent)" : "var(--border)"}`,
                    borderRadius: "var(--radius-sm)",
                    color: selected ? "var(--text)" : "var(--text-dim)",
                    fontSize: 13,
                    cursor: "pointer",
                    outline: "none",
                  }}
                >
                  <option value="">— select column —</option>
                  {columns.map((col) => (
                    <option key={col} value={col}>
                      {col}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}

          {/* Warning if duplicate mapping */}
          {hasDuplicates && isReady && (
            <div
              style={{
                fontSize: 12,
                color: "var(--medium)",
                background: "var(--medium-bg)",
                border: "1px solid var(--medium-border)",
                borderRadius: "var(--radius-sm)",
                padding: "8px 12px",
              }}
            >
              Each field must map to a different column.
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "16px 28px",
            borderTop: "1px solid var(--border)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 10,
          }}
        >
          <button
            onClick={onCancel}
            style={{
              padding: "8px 20px",
              background: "transparent",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--text-muted)",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(mapping)}
            disabled={!isReady || hasDuplicates}
            style={{
              padding: "8px 24px",
              background: isReady && !hasDuplicates ? "var(--accent)" : "var(--surface-hover)",
              border: "none",
              borderRadius: "var(--radius-sm)",
              color: isReady && !hasDuplicates ? "#fff" : "var(--text-dim)",
              fontSize: 13,
              fontWeight: 600,
              cursor: isReady && !hasDuplicates ? "pointer" : "not-allowed",
            }}
          >
            Analyze →
          </button>
        </div>
      </div>
    </div>
  );
}
