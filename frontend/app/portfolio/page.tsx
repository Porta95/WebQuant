'use client';

import { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';

/* =========================
   TYPES
========================= */

type Sleeve = 'CRYPTO' | 'EQUITIES' | 'COMMODITIES';

type Asset = {
  ticker: string;
  name: string;
  sleeve: Sleeve;
  enabled: boolean;
};

type PortfolioDTO = {
  crypto: string[];
  equities: string[];
  commodities: string[];
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

const SLEEVE_COLORS: Record<Sleeve, string> = {
  CRYPTO: '#f7931a',
  EQUITIES: '#00d4ff',
  COMMODITIES: '#ffd700',
};

const sleeves: Sleeve[] = ['CRYPTO', 'EQUITIES', 'COMMODITIES'];

/* =========================
   COMPONENT
========================= */

export default function Portfolio() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [newTicker, setNewTicker] = useState('');

  /* ===== load from backend ===== */
  useEffect(() => {
    fetchPortfolio()
      .then((p) => {
        const a: Asset[] = [
          ...p.crypto.map((t) => ({
            ticker: t,
            name: t,
            sleeve: 'CRYPTO' as Sleeve,
            enabled: true,
          })),
          ...p.equities.map((t) => ({
            ticker: t,
            name: t,
            sleeve: 'EQUITIES' as Sleeve,
            enabled: true,
          })),
          ...p.commodities.map((t) => ({
            ticker: t,
            name: t,
            sleeve: 'COMMODITIES' as Sleeve,
            enabled: true,
          })),
        ];
        setAssets(a);
      })
      .catch(() => {});
  }, []);

  /* ===== save to backend ===== */
  const persist = (list: Asset[]) => {
    const dto: PortfolioDTO = {
      crypto: list.filter((a) => a.sleeve === 'CRYPTO' && a.enabled).map((a) => a.ticker),
      equities: list.filter((a) => a.sleeve === 'EQUITIES' && a.enabled).map((a) => a.ticker),
      commodities: list.filter((a) => a.sleeve === 'COMMODITIES' && a.enabled).map((a) => a.ticker),
    };
    savePortfolio(dto);
  };

  /* ===== toggle ===== */
  const toggle = (i: number) => {
    const next = assets.map((x, idx) =>
      idx === i ? { ...x, enabled: !x.enabled } : x
    );
    setAssets(next);
    persist(next);
  };

  /* ===== add ===== */
  const addAsset = () => {
    if (!newTicker.trim()) return;

    const next: Asset[] = [
      ...assets,
      {
        ticker: newTicker.toUpperCase(),
        name: newTicker.toUpperCase(),
        sleeve: 'EQUITIES',
        enabled: true,
      },
    ];

    setAssets(next);
    persist(next);
    setNewTicker('');
  };

  /* =========================
     RENDER
  ========================= */

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Configuración de Cartera</h1>
        <p className="font-mono text-xs text-zinc-500 mt-1">
          Sleeves, activos habilitados y reglas de sizing
        </p>
      </div>

      {/* Sleeves */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {sleeves.map((sleeve) => (
          <div key={sleeve} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <div
                className="w-2 h-2 rounded-full"
                style={{ background: SLEEVE_COLORS[sleeve] }}
              />
              <span className="font-bold text-sm text-zinc-200">{sleeve}</span>
            </div>

            <div className="space-y-2">
              {assets
                .filter((a) => a.sleeve === sleeve)
                .map((asset, i) => {
                  const globalIdx = assets.indexOf(asset);
                  return (
                    <div
                      key={asset.ticker}
                      className="flex items-center justify-between py-2 border-b border-zinc-800/50"
                    >
                      <div>
                        <div className="font-mono text-xs font-bold text-zinc-200">
                          {asset.ticker}
                        </div>
                        <div className="font-mono text-xs text-zinc-600">
                          {asset.name}
                        </div>
                      </div>

                      <button
                        onClick={() => toggle(globalIdx)}
                        className={`w-8 h-4 rounded-full relative transition-all ${
                          asset.enabled ? 'bg-cyan-400/30' : 'bg-zinc-700'
                        }`}
                      >
                        <div
                          className={`absolute top-0.5 w-3 h-3 rounded-full transition-all ${
                            asset.enabled
                              ? 'left-4 bg-cyan-400'
                              : 'left-0.5 bg-zinc-500'
                          }`}
                        />
                      </button>
                    </div>
                  );
                })}
            </div>

            <div className="mt-3 flex items-center gap-2 py-2 border border-dashed border-zinc-700 rounded-lg px-3 text-zinc-600">
              <Plus size={12} />
              <span className="font-mono text-xs">Agregar activo</span>
            </div>
          </div>
        ))}
      </div>

      {/* Add new asset */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">
          Agregar nuevo activo
        </div>

        <div className="flex gap-3">
          <input
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === 'Enter' && addAsset()}
            placeholder="Ej: SOL-USD, TLT, NVDA"
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 font-mono text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-cyan-400/50"
          />

          <button
            onClick={addAsset}
            className="px-5 py-3 bg-cyan-400/10 border border-cyan-400/30 text-cyan-400 rounded-lg font-mono text-xs font-bold hover:bg-cyan-400/20"
          >
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
