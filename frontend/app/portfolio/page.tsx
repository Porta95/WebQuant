'use client';

import { useEffect, useState } from 'react';
import { Plus, X } from 'lucide-react';

/* =========================
   TYPES
========================= */

type Sleeve = 'equities' | 'reits' | 'crypto' | 'commodities' | 'bonds' | 'merval';

type PortfolioDTO = {
  equities:    string[];
  reits:       string[];
  crypto:      string[];
  commodities: string[];
  bonds:       string[];
  merval:      string[];
};

/* =========================
   API
========================= */

const API = process.env.NEXT_PUBLIC_API_URL;

async function fetchPortfolio(): Promise<PortfolioDTO> {
  const r = await fetch(`${API}/api/portfolio`);
  if (!r.ok) throw new Error('portfolio fetch failed');
  return r.json();
}

async function savePortfolio(data: PortfolioDTO) {
  await fetch(`${API}/api/portfolio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

/* =========================
   UI CONFIG
========================= */

const SLEEVE_META: Record<Sleeve, { label: string; color: string }> = {
  equities:    { label: 'EQUITIES',    color: '#00d4ff' },
  reits:       { label: 'REITS',       color: '#7c3aed' },
  crypto:      { label: 'CRYPTO',      color: '#f7931a' },
  commodities: { label: 'COMMODITIES', color: '#ffd700' },
  bonds:       { label: 'BONDS',       color: '#10b981' },
  merval:      { label: 'MERVAL',      color: '#6366f1' },
};

const SLEEVES: Sleeve[] = ['equities', 'reits', 'crypto', 'commodities', 'bonds', 'merval'];

/* =========================
   COMPONENT
========================= */

export default function Portfolio() {
  const [portfolio, setPortfolio] = useState<PortfolioDTO>({
    equities: [], reits: [], crypto: [], commodities: [], bonds: [], merval: [],
  });
  const [newTicker, setNewTicker]   = useState('');
  const [newSleeve, setNewSleeve]   = useState<Sleeve>('equities');
  const [loading, setLoading]       = useState(true);

  /* ===== load from backend ===== */
  useEffect(() => {
    fetchPortfolio()
      .then((p) => {
        setPortfolio({
          equities:    p.equities    ?? [],
          reits:       p.reits       ?? [],
          crypto:      p.crypto      ?? [],
          commodities: p.commodities ?? [],
          bonds:       p.bonds       ?? [],
          merval:      p.merval      ?? [],
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  /* ===== delete asset ===== */
  const deleteAsset = (sleeve: Sleeve, ticker: string) => {
    const next: PortfolioDTO = {
      ...portfolio,
      [sleeve]: portfolio[sleeve].filter((t) => t !== ticker),
    };
    setPortfolio(next);
    savePortfolio(next);
  };

  /* ===== add asset ===== */
  const addAsset = () => {
    const t = newTicker.trim().toUpperCase();
    if (!t) return;
    // Avoid duplicates across all sleeves
    const allTickers = SLEEVES.flatMap((s) => portfolio[s]);
    if (allTickers.includes(t)) {
      setNewTicker('');
      return;
    }
    const next: PortfolioDTO = {
      ...portfolio,
      [newSleeve]: [...portfolio[newSleeve], t],
    };
    setPortfolio(next);
    savePortfolio(next);
    setNewTicker('');
  };

  const totalAssets = SLEEVES.reduce((sum, s) => sum + portfolio[s].length, 0);

  /* =========================
     RENDER
  ========================= */

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Configuración de Cartera</h1>
        <p className="font-mono text-xs text-zinc-500 mt-1">
          {loading ? 'Cargando…' : `${totalAssets} activos en ${SLEEVES.filter(s => portfolio[s].length > 0).length} sleeves`}
        </p>
      </div>

      {/* Sleeves grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {SLEEVES.map((sleeve) => {
          const { label, color } = SLEEVE_META[sleeve];
          const tickers = portfolio[sleeve];
          return (
            <div key={sleeve} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: color }} />
                  <span className="font-bold text-sm text-zinc-200">{label}</span>
                </div>
                <span className="font-mono text-xs text-zinc-600">{tickers.length}</span>
              </div>

              {/* Asset list */}
              <div className="space-y-1">
                {tickers.length === 0 && (
                  <p className="font-mono text-xs text-zinc-700 py-2">Sin activos</p>
                )}
                {tickers.map((ticker) => (
                  <div
                    key={ticker}
                    className="flex items-center justify-between py-1.5 border-b border-zinc-800/50 last:border-0"
                  >
                    <span className="font-mono text-xs font-bold text-zinc-200">{ticker}</span>
                    <button
                      onClick={() => deleteAsset(sleeve, ticker)}
                      className="text-zinc-600 hover:text-red-400 transition-colors ml-2"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Add new asset */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">
          Agregar nuevo activo
        </div>

        <div className="flex gap-3">
          {/* Sleeve selector */}
          <select
            value={newSleeve}
            onChange={(e) => setNewSleeve(e.target.value as Sleeve)}
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-3 font-mono text-xs text-zinc-100 focus:outline-none focus:border-cyan-400/50"
          >
            {SLEEVES.map((s) => (
              <option key={s} value={s}>
                {SLEEVE_META[s].label}
              </option>
            ))}
          </select>

          {/* Ticker input */}
          <input
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === 'Enter' && addAsset()}
            placeholder="Ej: SOL-USD, TLT, NVDA, GGAL.BA"
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 font-mono text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-cyan-400/50"
          />

          <button
            onClick={addAsset}
            className="px-5 py-3 bg-cyan-400/10 border border-cyan-400/30 text-cyan-400 rounded-lg font-mono text-xs font-bold hover:bg-cyan-400/20 flex items-center gap-2"
          >
            <Plus size={14} />
            Agregar
          </button>
        </div>

        <p className="font-mono text-xs text-zinc-600 mt-2">
          Tip: Usá el Analizador primero para evaluar si el activo mejora tu cartera.
        </p>
      </div>
    </div>
  );
}
