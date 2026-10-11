import React, { useState, useEffect } from "react";
import Badge from "./Badge";
import ScoreBar from "./ScoreBar";
import { riskColor, fmtScore, fmtAmount, fmtTime } from "../utils";

const BASE = "/api/v1";

const STATUS_META = {
  confirmed_fraud: { label: "Подтверждённый фрод", color: "var(--high)" },
  false_positive:  { label: "Ложная тревога",       color: "var(--low)"  },
  under_review:    { label: "На проверке",           color: "var(--medium)" },
};

export default function DetailPanel({ result, onClose }) {
  const [caseData,    setCaseData]    = useState(null);
  const [caseLoading, setCaseLoading] = useState(false);
  const [comment,     setComment]     = useState("");

  // Fetch existing case whenever the selected transaction changes
  useEffect(() => {
    if (!result) return;
    setCaseData(null);
    setComment("");
    fetch(`${BASE}/cases/${result.transaction_id}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) {
          setCaseData(data);
          setComment(data.comment || "");
        }
      })
      .catch(() => {});
  }, [result?.transaction_id]);

  const handleReview = async (status) => {
    setCaseLoading(true);
    try {
      const r = await fetch(`${BASE}/cases/${result.transaction_id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status,
          comment: comment || null,
          reviewed_by: "analyst",
        }),
      });
      if (r.ok) setCaseData(await r.json());
    } catch (e) {
      console.error(e);
    } finally {
      setCaseLoading(false);
    }
  };

  if (!result) return null;

  const { breakdown, triggered_rules } = result;

  return (
    <div
      style={{
        position: "fixed",
        top: 0, right: 0,
        width: 420,
        height: "100vh",
        background: "var(--surface)",
        borderLeft: "1px solid var(--border)",
        zIndex: 100,
        display: "flex",
        flexDirection: "column",
        boxShadow: "-8px 0 32px rgba(0,0,0,0.4)",
      }}
    >
      {/* Header */}
      <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>ТРАНЗАКЦИЯ</div>
          <div className="mono" style={{ fontSize: 15, color: "var(--text)" }}>{result.transaction_id}</div>
        </div>
        <button
          onClick={onClose}
          style={{ background: "none", border: "1px solid var(--border)", color: "var(--text-muted)", width: 32, height: 32, borderRadius: "var(--radius-sm)", cursor: "pointer", fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center" }}
        >✕</button>
      </div>

      {/* Body */}
      <div style={{ padding: 24, overflowY: "auto", flex: 1 }}>

        {/* Risk badge + score */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
          <Badge riskClass={result.risk_class} />
          <span className="mono" style={{ fontSize: 24, fontWeight: 700, color: riskColor(result.risk_class) }}>
            {fmtScore(result.final_score)}
          </span>
        </div>

        {/* Meta grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 28 }}>
          {[
            ["Пользователь", result.user_id],
            ["Сумма", `$${fmtAmount(result.amount)}`],
            ["Время", fmtTime(result.transaction_time)],
          ].map(([k, v]) => (
            <div key={k}>
              <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 2 }}>{k}</div>
              <div style={{ fontSize: 13, color: "var(--text)" }}>{v}</div>
            </div>
          ))}
        </div>

        {/* Score breakdown */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.06em", marginBottom: 14, textTransform: "uppercase" }}>
            Разбивка скора
          </div>
          <ScoreBar score={breakdown.rule_score}           label="Скор правил"       color="#8B5CF6" />
          <ScoreBar score={breakdown.behavioral_risk_score} label="Поведенческий риск" color="#F59E0B" />
          <ScoreBar score={breakdown.model_score}           label="ML-модель"          color="#3B82F6" />
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
            <ScoreBar score={result.final_score} label="Итоговый скор" color={riskColor(result.risk_class)} />
          </div>
        </div>

        {/* Explanations */}
        {result.explanations?.length > 0 && (
          <div style={{ marginBottom: 28 }}>
            <div style={{ fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.06em", marginBottom: 10, textTransform: "uppercase" }}>
              Почему это подозрительно?
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {result.explanations.map((exp, i) => (
                <div key={i} style={{ padding: "10px 12px", borderRadius: "var(--radius-sm)", background: "var(--high-bg)", border: "1px solid var(--high-border)", fontSize: 12, color: "var(--text)", lineHeight: 1.5 }}>
                  ⚠ {exp}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Triggered rules */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.06em", marginBottom: 10, textTransform: "uppercase" }}>
            Сработавшие правила
          </div>
          {triggered_rules?.length > 0 ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {triggered_rules.map((r) => (
                <span key={r} className="mono" style={{ padding: "4px 10px", borderRadius: "var(--radius-xs)", fontSize: 11, background: "var(--white-08)", color: "var(--text)", border: "1px solid var(--border)" }}>
                  {r}
                </span>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: 12, color: "var(--text-dim)" }}>Правила не сработали</div>
          )}
        </div>

        {/* ── Case Management ── */}
        <div style={{ paddingTop: 20, borderTop: "1px solid var(--border)" }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.06em", marginBottom: 14, textTransform: "uppercase" }}>
            Решение по кейсу
          </div>

          {/* Current status banner */}
          {caseData && (
            <div style={{ marginBottom: 12, padding: "8px 12px", borderRadius: "var(--radius-sm)", background: "var(--white-08)", border: "1px solid var(--border)", fontSize: 12, color: "var(--text-muted)" }}>
              Статус:{" "}
              <strong style={{ color: STATUS_META[caseData.status]?.color || "var(--text)" }}>
                {STATUS_META[caseData.status]?.label || caseData.status}
              </strong>
              {caseData.reviewed_by && (
                <span style={{ marginLeft: 8, color: "var(--text-dim)" }}>· {caseData.reviewed_by}</span>
              )}
            </div>
          )}

          {/* Action buttons */}
          <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
            {Object.entries(STATUS_META).map(([key, { label, color }]) => {
              const isActive = caseData?.status === key;
              return (
                <button
                  key={key}
                  onClick={() => handleReview(key)}
                  disabled={caseLoading}
                  style={{
                    flex: 1,
                    padding: "8px 4px",
                    borderRadius: "var(--radius-sm)",
                    border: `1px solid ${isActive ? color : "var(--border)"}`,
                    background: isActive ? `${color}22` : "transparent",
                    color: isActive ? color : "var(--text-muted)",
                    fontSize: 11,
                    fontWeight: isActive ? 700 : 400,
                    cursor: caseLoading ? "wait" : "pointer",
                    lineHeight: 1.3,
                    transition: "all 0.15s",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* Comment input */}
          <input
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Комментарий (необязательно)"
            style={{
              width: "100%",
              padding: "8px 12px",
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--text)",
              fontSize: 12,
              outline: "none",
              boxSizing: "border-box",
            }}
          />
        </div>

      </div>
    </div>
  );
}