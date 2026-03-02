const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://webquant-production.up.railway.app';

export async function getSignal() {
  const res = await fetch(`${API_URL}/api/signal/compute`, { next: { revalidate: 3600 } });
  if (!res.ok) throw new Error('Error fetching signal');
  return res.json();
}

export async function getHistory() {
  const res = await fetch(`${API_URL}/api/signal/history`, { next: { revalidate: 3600 } });
  if (!res.ok) throw new Error('Error fetching history');
  return res.json();
}

export async function getPerformance() {
  const res = await fetch(`${API_URL}/api/signal/performance`, { next: { revalidate: 3600 } });
  if (!res.ok) throw new Error('Error fetching performance');
  return res.json();
}

export async function analyzeAsset(ticker: string) {
  const res = await fetch(`${API_URL}/api/backtest/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker }),
  });
  if (!res.ok) throw new Error('Error analyzing asset');
  return res.json();
}

export async function sendTelegram() {
  const res = await fetch(`${API_URL}/api/signal/telegram`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  return res.json();
}
