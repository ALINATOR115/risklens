import React, { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
} from "recharts";
import { riskColor } from "../utils";

const tooltipStyle = {
  background: "var(--surface-hover)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  fontSize: 12,
  color: "var(--text)",
};

export default function Charts({ results, counts }) {
  const barData = useMemo(
    () =>
      [...results]
        .sort((a, b) => b.final_score - a.final_score)
        .slice(0, 15)
        .map((r) => ({
          id: r.transaction_id,
          score: r.final_score,
          risk: r.risk_class,
        })),
    [results]
  );

  const pieData = useMemo(
    () =>
      [
        { name: "High", value: counts.high, color: "var(--high)" },
        { name: "Medium", value: counts.medium, color: "var(--medium)" },
        { name: "Low", value: counts.low, color: "var(--low)" },
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
      {/* Bar chart */}
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: "20px 24px",
        }}
      >
        <div
          style={{
            fontSize: 12,
            color: "var(--text-muted)",
            marginBottom: 16,
            letterSpacing: "0.04em",
          }}
        >
          TOP RISK SCORES
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={barData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
            <XAxis
              dataKey="id"
              tick={{ fill: "#4A5568", fontSize: 9 }}
              axisLine={{ stroke: "#1E2433" }}
              tickLine={false}
            />
            <YAxis
              domain={[0, 1]}
              tick={{ fill: "#4A5568", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey="score" radius={[3, 3, 0, 0]}>
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
        <div
          style={{
            fontSize: 12,
            color: "var(--text-muted)",
            marginBottom: 12,
            letterSpacing: "0.04em",
            alignSelf: "flex-start",
          }}
        >
          DISTRIBUTION
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
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
