import React, { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
} from "recharts";
import { riskColor } from "../utils";

// Hardcoded colours — Recharts tooltips don't inherit CSS variables
const tooltipStyle = {
  background: "#ffffff",
  border: "1px solid #e2e8f2",
  borderRadius: 6,
  fontSize: 12,
  color: "#111927",
  boxShadow: "0 4px 12px rgba(0,0,0,0.10)",
};

const fmtAmt = (v) =>
  v >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${Math.round(v)}`;

export default function Charts({ results, counts }) {
  const barData = useMemo(
    () =>
      [...results]
        .filter((r) => r.risk_class === "high_risk")
        .sort((a, b) => b.amount - a.amount)
        .slice(0, 15)
        .map((r) => ({
          id: r.transaction_id,
          amount: Math.round(r.amount),
          risk: r.risk_class,
        })),
    [results]
  );

  const pieData = useMemo(
    () =>
      [
        { name: "Высокий", value: counts.high,   color: "#ef4444" },
        { name: "Средний", value: counts.medium, color: "#f59e0b" },
        { name: "Низкий",  value: counts.low,    color: "#22c55e" },
      ].filter((d) => d.value > 0),
    [counts]
  );

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 280px",
        gap: 16,
        marginBottom: 28,
      }}
    >
      {/* Bar chart — top high-risk by amount */}
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: "20px 24px",
        }}
      >
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 16, letterSpacing: "0.04em" }}>
          ТОП ВЫСОКОРИСКОВЫХ ТРАНЗАКЦИЙ ПО СУММЕ
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={barData} margin={{ top: 0, right: 0, bottom: 0, left: 10 }}>
            <XAxis
              dataKey="id"
              tick={{ fill: "#4A5568", fontSize: 9 }}
              axisLine={{ stroke: "#1E2433" }}
              tickLine={false}
            />
            <YAxis
              tickFormatter={fmtAmt}
              tick={{ fill: "#4A5568", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(v) => [fmtAmt(v), "Сумма"]}
              labelStyle={{ color: "#94a3b8", marginBottom: 4 }}
            />
            <Bar dataKey="amount" radius={[3, 3, 0, 0]}>
              {barData.map((d, i) => (
                <Cell key={i} fill={riskColor(d.risk)} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Pie chart */}
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: "20px 24px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12, letterSpacing: "0.04em", alignSelf: "flex-start" }}>
          РАСПРЕДЕЛЕНИЕ
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              data={pieData}
              dataKey="value"
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={75}
              paddingAngle={3}
              stroke="none"
            >
              {pieData.map((d, i) => (
                <Cell key={i} fill={d.color} />
              ))}
            </Pie>
            <Legend
              verticalAlign="bottom"
              iconType="circle"
              iconSize={8}
              formatter={(v) => (
                <span style={{ color: "#7A8494", fontSize: 11 }}>{v}</span>
              )}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(v, name) => [v, name]}
              labelStyle={{ color: "#94a3b8" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}