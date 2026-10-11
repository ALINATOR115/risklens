/** Risk class → CSS variable name mapping */
export function riskColor(cls) {
  if (cls === "high_risk") return "var(--high)";
  if (cls === "medium_risk") return "var(--medium)";
  return "var(--low)";
}

export function riskBg(cls) {
  if (cls === "high_risk") return "var(--high-bg)";
  if (cls === "medium_risk") return "var(--medium-bg)";
  return "var(--low-bg)";
}

export function riskBorder(cls) {
  if (cls === "high_risk") return "var(--high-border)";
  if (cls === "medium_risk") return "var(--medium-border)";
  return "var(--low-border)";
}

export function riskLabel(cls) {
  if (cls === "high_risk") return "ВЫСОКИЙ";
  if (cls === "medium_risk") return "СРЕДНИЙ";
  return "НИЗКИЙ";
}

/** Format a float score to 4 decimal places */
export function fmtScore(n) {
  return typeof n === "number" ? n.toFixed(4) : "—";
}

/** Format currency amount */
export function fmtAmount(n) {
  if (typeof n !== "number") return "—";
  return n.toLocaleString("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Format ISO timestamp to HH:MM */
export function fmtTime(t) {
  try {
    return new Date(t).toLocaleTimeString("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return "—";
  }
}
