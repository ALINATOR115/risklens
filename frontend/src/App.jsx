import React, { useState, useCallback, useRef } from "react";
import Header from "./components/Header";
import StatCard from "./components/StatCard";
import Charts from "./components/Charts";
import TransactionsTable from "./components/TransactionsTable";
import DetailPanel from "./components/DetailPanel";
import ColumnMapper from "./components/ColumnMapper";
import UserProfile from "./components/UserProfile";
import { scoreBatch, scoreDemo, detectColumns, scoreUploadMapped } from "./api/client";
import DEMO_TRANSACTIONS from "./api/demoData";

export default function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedTx, setSelectedTx] = useState(null);
  const [tab, setTab] = useState("demo");
  const [selectedUser, setSelectedUser] = useState(null);
  const fileRef = useRef(null);

  // Column mapping state
  const [pendingFile, setPendingFile] = useState(null);
  const [mappingInfo, setMappingInfo] = useState(null); // { columns, sample, guess }

  // ── Run demo ───────────────────────────────────────────────────
  const runDemo = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSelectedTx(null);
    try {
      const result = await scoreDemo();
      setData(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Step 1: detect columns ─────────────────────────────────────
  const handleFileChange = useCallback(async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setLoading(true);
    try {
      const info = await detectColumns(file);
      setPendingFile(file);
      setMappingInfo(info);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }, []);

  // ── Step 2: user confirms mapping → score ──────────────────────
  const handleMappingConfirm = useCallback(async (mapping) => {
    setMappingInfo(null);
    setLoading(true);
    setSelectedTx(null);
    try {
      const result = await scoreUploadMapped(
        pendingFile,
        mapping.user_id,
        mapping.amount,
        mapping.transaction_time
      );
      setData(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setPendingFile(null);
    }
  }, [pendingFile]);

  const handleMappingCancel = useCallback(() => {
    setMappingInfo(null);
    setPendingFile(null);
  }, []);

  const counts = data
    ? { high: data.high_risk_count, medium: data.medium_risk_count, low: data.low_risk_count }
    : { high: 0, medium: 0, low: 0 };

  const pct = (n) =>
    data && data.total ? `${((n / data.total) * 100).toFixed(1)}%` : "";

  return (
    <div style={{ minHeight: "100vh" }}>
      <Header isConnected={!!data} />

      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "28px 32px" }}>
        {/* Action bar */}
        <div style={{ display: "flex", gap: 12, marginBottom: 28, alignItems: "center" }}>
          <div
            style={{
              display: "flex",
              background: "var(--surface)",
              borderRadius: 8,
              border: "1px solid var(--border)",
              overflow: "hidden",
            }}
          >
            {["demo", "upload"].map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                style={{
                  padding: "8px 20px",
                  background: tab === t ? "var(--white-08)" : "transparent",
                  border: "none",
                  color: tab === t ? "var(--text)" : "var(--text-muted)",
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: "pointer",
                  borderRight: t === "demo" ? "1px solid var(--border)" : "none",
                }}
              >
                {t === "demo" ? "Demo dataset" : "Upload CSV"}
              </button>
            ))}
          </div>

          {tab === "demo" ? (
            <button
              onClick={runDemo}
              disabled={loading}
              style={{
                padding: "8px 24px",
                background: loading ? "var(--surface-hover)" : "var(--accent)",
                border: "none",
                borderRadius: 8,
                color: "#fff",
                fontSize: 13,
                fontWeight: 600,
                cursor: loading ? "wait" : "pointer",
              }}
            >
              {loading ? "Scoring..." : "Run analysis"}
            </button>
          ) : (
            <label
              style={{
                padding: "8px 24px",
                background: loading ? "var(--surface-hover)" : "var(--accent)",
                borderRadius: 8,
                color: "#fff",
                fontSize: 13,
                fontWeight: 600,
                cursor: loading ? "wait" : "pointer",
              }}
            >
              {loading ? "Reading file..." : "Choose file"}
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                style={{ display: "none" }}
                disabled={loading}
              />
            </label>
          )}

          {error && (
            <span
              style={{
                fontSize: 12,
                color: "var(--high)",
                background: "var(--high-bg)",
                padding: "6px 12px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--high-border)",
              }}
            >
              {error}
            </span>
          )}
        </div>

        {/* Empty state */}
        {!data && !loading && (
          <div style={{ textAlign: "center", padding: "80px 0", color: "var(--text-dim)" }}>
            <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>⬡</div>
            <div style={{ fontSize: 15, marginBottom: 6, color: "var(--text-muted)" }}>
              No data loaded
            </div>
            <div style={{ fontSize: 13 }}>
              Run the demo dataset or upload any CSV with transaction data
            </div>
          </div>
        )}

        {/* Dashboard */}
        {data && (
          <>
            <div style={{ display: "flex", gap: 16, marginBottom: 28, flexWrap: "wrap" }}>
              <StatCard label="TOTAL TRANSACTIONS" value={data.total} />
              <StatCard label="HIGH RISK" value={counts.high} color="var(--high)" sub={pct(counts.high)} />
              <StatCard label="MEDIUM RISK" value={counts.medium} color="var(--medium)" sub={pct(counts.medium)} />
              <StatCard label="LOW RISK" value={counts.low} color="var(--low)" sub={pct(counts.low)} />
            </div>
            <Charts results={data.results} counts={counts} />
            <TransactionsTable results={data.results} total={data.total} onSelect={setSelectedTx} onSelectUser={setSelectedUser} />
          </>
        )}
      </main>

      {/* User profile panel */}
      {selectedUser && (
        <UserProfile userId={selectedUser} onClose={() => setSelectedUser(null)} />
      )}

      {/* Column mapping modal */}
      {mappingInfo && (
        <ColumnMapper
          columns={mappingInfo.columns}
          sample={mappingInfo.sample}
          guess={mappingInfo.guess}
          onConfirm={handleMappingConfirm}
          onCancel={handleMappingCancel}
        />
      )}

      {/* Detail panel */}
      {selectedTx && (
        <>
          <div
            onClick={() => setSelectedTx(null)}
            style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 90 }}
          />
          <DetailPanel result={selectedTx} onClose={() => setSelectedTx(null)} />
        </>
      )}
    </div>
  );
}
