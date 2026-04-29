import React, { useState, useMemo } from "react";
import Badge from "./Badge";
import { riskColor, riskLabel, fmtScore, fmtAmount, fmtTime } from "../utils";

const COLUMNS = [
  { key: "transaction_id", label: "ID", sortable: true },
  { key: "user_id", label: "User", sortable: true },
  { key: "amount", label: "Amount", sortable: true },
  { key: "transaction_time", label: "Time", sortable: true },
  { key: "final_score", label: "Score", sortable: true },
  { key: "risk_class", label: "Risk", sortable: true },
  { key: "_rules", label: "Rules", sortable: false },
];

const FILTERS = ["all", "high_risk", "medium_risk", "low_risk"];

export default function TransactionsTable({ results, total, onSelect, onSelectUser }) {
  const [sortKey, setSortKey] = useState("final_score");
  const [sortAsc, setSortAsc] = useState(false);
  const [filter, setFilter] = useState("all");

  const toggleSort = (key) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(key === "user_id" || key === "transaction_id");
    }
  };

  const sorted = useMemo(() => {
    const filtered =
      filter === "all" ? [...results] : results.filter((r) => r.risk_class === filter);

    return filtered.sort((a, b) => {
      let av = a[sortKey],
        bv = b[sortKey];
      if (typeof av === "string") return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortAsc ? av - bv : bv - av;
    });
  }, [results, sortKey, sortAsc, filter]);

  return (
    <div>
      {/* Filter row */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
        <span style={{ fontSize: 12, color: "var(--text-muted)", marginRight: 4 }}>
          Filter:
        </span>
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: "4px 12px",
              borderRadius: "var(--radius-sm)",
              border: `1px solid ${filter === f ? "var(--accent)" : "var(--border)"}`,
              background: filter === f ? "var(--accent-glow)" : "transparent",
              color: filter === f ? "var(--accent)" : "var(--text-muted)",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            {f === "all" ? "All" : riskLabel(f)}
          </button>
        ))}
        <span style={{ fontSize: 12, color: "var(--text-dim)", marginLeft: "auto" }}>
          {sorted.length} of {total} transactions
        </span>
      </div>

      {/* Table */}
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          overflow: "hidden",
        }}
      >
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr>
                {COLUMNS.map(({ key, label, sortable }) => (
                  <th
                    key={label}
                    onClick={sortable ? () => toggleSort(key) : undefined}
                    style={{
                      padding: "12px 16px",
                      textAlign: "left",
                      borderBottom: "1px solid var(--border)",
                      color: "var(--text-muted)",
                      fontSize: 11,
                      fontWeight: 600,
                      letterSpacing: "0.04em",
                      textTransform: "uppercase",
                      cursor: sortable ? "pointer" : "default",
                      userSelect: "none",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {label}
                    {sortKey === key && (
                      <span style={{ marginLeft: 4 }}>{sortAsc ? "↑" : "↓"}</span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr
                  key={r.transaction_id}
                  onClick={() => onSelect(r)}
                  style={{
                    cursor: "pointer",
                    borderBottom: "1px solid var(--border)",
                    transition: "background 0.15s",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = "var(--surface-hover)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = "transparent")
                  }
                >
                  <td
                    className="mono"
                    style={{ padding: "10px 16px", fontSize: 12, color: "var(--text-muted)" }}
                  >
                    {r.transaction_id}
                  </td>
                  <td style={{ padding: "10px 16px" }}>
                    <span
                      onClick={(e) => { e.stopPropagation(); onSelectUser && onSelectUser(r.user_id); }}
                      style={{
                        color: "var(--accent)",
                        cursor: "pointer",
                        textDecoration: "underline",
                        textDecorationStyle: "dotted",
                      }}
                    >
                      {r.user_id}
                    </span>
                  </td>
                  <td className="mono" style={{ padding: "10px 16px" }}>
                    ${fmtAmount(r.amount)}
                  </td>
                  <td style={{ padding: "10px 16px", color: "var(--text-muted)" }}>
                    {fmtTime(r.transaction_time)}
                  </td>
                  <td
                    className="mono"
                    style={{
                      padding: "10px 16px",
                      fontWeight: 600,
                      color: riskColor(r.risk_class),
                    }}
                  >
                    {fmtScore(r.final_score)}
                  </td>
                  <td style={{ padding: "10px 16px" }}>
                    <Badge riskClass={r.risk_class} />
                  </td>
                  <td style={{ padding: "10px 16px" }}>
                    {r.triggered_rules?.length > 0 ? (
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {r.triggered_rules.map((rule) => (
                          <span
                            key={rule}
                            style={{
                              padding: "2px 6px",
                              borderRadius: 3,
                              fontSize: 10,
                              background: "var(--white-08)",
                              color: "var(--text-muted)",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {rule}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span style={{ color: "var(--text-dim)", fontSize: 12 }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
