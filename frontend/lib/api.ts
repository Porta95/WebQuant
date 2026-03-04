const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://webquant-production.up.railway.app";

// ================= SIGNAL =================

export async function getSignal() {
  const res = await fetch(`${API_URL}/api/signal`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error("Error fetching signal");
  return res.json();
}

export async function getHistory() {
  const res = await fetch(`${API_URL}/api/signal/history`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error("Error fetching history");
  return res.json();
}

export async function getPerformance() {
  const res = await fetch(`${API_URL}/api/signal/performance`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error("Error fetching performance");
  return res.json();
}

// ================= ANALYZER =================

export async function analyzeAsset(ticker: string) {
  const res = await fetch(`${API_URL}/api/backtest/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker }),
  });
  if (!res.ok) throw new Error("Error analyzing asset");
  return res.json();
}

// ================= TELEGRAM =================

export async function sendTelegram() {
  const res = await fetch(`${API_URL}/api/signal/telegram`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error("Error sending telegram");
  return res.json();
}

// ================= PORTFOLIO =================

export async function getPortfolio() {
  const res = await fetch(`${API_URL}/api/portfolio`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Error fetching portfolio");
  return res.json();
}

export async function savePortfolio(data: any) {
  const res = await fetch(`${API_URL}/api/portfolio`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Error saving portfolio");
  return res.json();
}
