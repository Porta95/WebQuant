'use client';

import { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';

type Asset = {
  ticker: string;
  name: string;
  sleeve: 'CRYPTO' | 'EQUITIES' | 'COMMODITIES';
  enabled: boolean;
};

const SLEEVE_COLORS: Record<string, string> = {
  CRYPTO: '#f7931a',
  EQUITIES: '#00d4ff',
  COMMODITIES: '#ffd700',
};

export default function Portfolio() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [newTicker, setNewTicker] = useState('');

  // ---------- LOAD FROM BACKEND ----------
  useEffect(() => {
    fetch('/api/portfolio')
      .then(r => r.json())
      .then(port => {
        const a: Asset[] = [
          ...(port.crypto || []).map((t: string) => ({
            ticker: t,
            name: t,
            sleeve: 'CRYPTO',
            enabled: true,
          })),
          ...(port.equities || []).map((t: string) => ({
            ticker: t,
            name: t,
            sleeve: 'EQUITIES',
            enabled: true,
          })),
          ...(port.commodities || []).map((t: string) => ({
            ticker: t,
            name: t,
            sleeve: 'COMMODITIES',
            enabled: true,
          })),
        ];
        setAssets(a);
      });
  }, []);

  // ---------- SAVE TO BACKEND ----------
  const savePortfolio = async (list: Asset[]) => {
    setAssets(list);

    const port = {
      crypto: list.filter(a => a.sleeve === 'CRYPTO' && a.enabled).map(a => a.ticker),
      equities: list.filter(a => a.sleeve === 'EQUITIES' && a.enabled).map(a => a.ticker),
      commodities: list.filter(a => a.sleeve === 'COMMODITIES' && a.enabled).map(a => a.ticker),
    };

    await fetch('/api/portfolio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(port),
    });
  };

  // ---------- TOGGLE ----------
  const toggle = (i: number) => {
    const next = assets.map((a, idx) =>
      idx === i ? { ...a, enabled: !a.enabled } : a
    );
    savePortfolio(next);
  };

  // ---------- ADD ----------
  const addAsset = () => {
    if (!newTicker.trim()) return;

    const next = [
      ...assets,
      {
        ticker: newTicker.toUpperCase(),
        name: newTicker.toUpperCase(),
        sleeve: 'EQUITIES',
        enabled: true,
      },
    ];

    setNewTicker('');
    savePortfolio(next);
  };

  const sleeves = ['CRYPTO', 'EQUITIES', 'COMMODITIES'];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-zinc-100">Configuración de Cartera</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {sleeves.map(sleeve => (
          <div key={sleeve} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-2 h-2 rounded-full" style={{ background: SLEEVE_COLORS[sleeve] }} />
              <span className="font-bold text-sm text-zinc-200">{sleeve}</span>
            </div>

            {assets
              .filter(a => a.sleeve === sleeve)
              .map((asset, i) => {
                const globalIdx = assets.indexOf(asset);
                return (
                  <div key={asset.ticker} className="flex justify-between py-2 border-b border-zinc-800/50">
                    <div className="font-mono text-xs font-bold text-zinc-200">
                      {asset.ticker}
                    </div>

                    <button
                      onClick={() => toggle(globalIdx)}
                      className={`w-8 h-4 rounded-full ${
                        asset.enabled ? 'bg-cyan-400/30' : 'bg-zinc-700'
                      }`}
                    />
                  </div>
                );
              })}
          </div>
        ))}
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="flex gap-3">
          <input
            value={newTicker}
            onChange={e => setNewTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && addAsset()}
            placeholder="Ej: NVDA"
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 font-mono text-sm"
          />
          <button onClick={addAsset} className="px-5 py-3 bg-cyan-400/10 border">
            Agregar
          </button>
        </div>
      </div>
    </div>
  );
}
