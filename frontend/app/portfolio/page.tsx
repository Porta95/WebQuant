'use client';

import { useState } from 'react';
import { Plus } from 'lucide-react';

const INITIAL_ASSETS = [
  { ticker: 'BTC-USD', name: 'Bitcoin',        sleeve: 'CRYPTO',      enabled: true },
  { ticker: 'ETH-USD', name: 'Ethereum',        sleeve: 'CRYPTO',      enabled: true },
  { ticker: 'QQQ',     name: 'Nasdaq 100 ETF', sleeve: 'EQUITIES',    enabled: true },
  { ticker: 'SPY',     name: 'S&P 500 ETF',    sleeve: 'EQUITIES',    enabled: true },
  { ticker: 'GLD',     name: 'Gold ETF',        sleeve: 'COMMODITIES', enabled: true },
];

const SLEEVE_COLORS: Record<string, string> = {
  CRYPTO:      '#f7931a',
  EQUITIES:    '#00d4ff',
  COMMODITIES: '#ffd700',
};

const RULES = [
  { label: 'Donchian lookback',    desc: 'Ventana de entrada Donchian',   val: '50 días' },
  { label: 'MA Exit',              desc: 'Sale cuando precio < MA',        val: 'MA50' },
  { label: 'Filtro Buffett',       desc: 'Reduce equity si >120%',         val: '× 0.70' },
  { label: 'Vol Target',           desc: 'Volatilidad objetivo cartera',    val: '20%' },
  { label: 'Max posición activo',  desc: 'Límite por activo individual',    val: '55%' },
  { label: 'Rebalanceo',           desc: 'Frecuencia de revisión',          val: 'Semanal' },
];

export default function Portfolio() {
  const [assets, setAssets] = useState(INITIAL_ASSETS);
  const [newTicker, setNewTicker] = useState('');

  const toggle = (i: number) => {
    setAssets(a => a.map((x, idx) => idx === i ? { ...x, enabled: !x.enabled } : x));
  };

  const addAsset = () => {
    if (!newTicker.trim()) return;
    setAssets(a => [...a, {
      ticker: newTicker.toUpperCase(),
      name: newTicker.toUpperCase(),
      sleeve: 'EQUITIES',
      enabled: true,
    }]);
    setNewTicker('');
  };

  const sleeves = [...new Set(assets.map(a => a.sleeve))];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Configuración de Cartera</h1>
        <p className="font-mono text-xs text-zinc-500 mt-1">Sleeves, activos habilitados y reglas de sizing</p>
      </div>

      {/* Sleeves */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {sleeves.map(sleeve => (
          <div key={sleeve} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-2 h-2 rounded-full" style={{ background: SLEEVE_COLORS[sleeve] || '#fff' }} />
              <span className="font-bold text-sm text-zinc-200">{sleeve}</span>
            </div>
            <div className="space-y-2">
              {assets.filter(a => a.sleeve === sleeve).map((asset, i) => {
                const globalIdx = assets.indexOf(asset);
                return (
                  <div key={asset.ticker} className="flex items-center justify-between py-2 border-b border-zinc-800/50">
                    <div>
                      <div className="font-mono text-xs font-bold text-zinc-200">{asset.ticker}</div>
                      <div className="font-mono text-xs text-zinc-600">{asset.name}</div>
                    </div>
                    <button onClick={() => toggle(globalIdx)}
                      className={`w-8 h-4 rounded-full relative transition-all ${asset.enabled ? 'bg-cyan-400/30' : 'bg-zinc-700'}`}>
                      <div className={`absolute top-0.5 w-3 h-3 rounded-full transition-all ${asset.enabled ? 'left-4 bg-cyan-400' : 'left-0.5 bg-zinc-500'}`} />
                    </button>
                  </div>
                );
              })}
            </div>
            <div className="mt-3 flex items-center gap-2 py-2 border border-dashed border-zinc-700 rounded-lg px-3 cursor-pointer hover:border-cyan-400/30 hover:text-cyan-400 text-zinc-600 transition-all">
              <Plus size={12} />
              <span className="font-mono text-xs">Agregar activo</span>
            </div>
          </div>
        ))}
      </div>

      {/* Add new asset */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Agregar nuevo activo</div>
        <div className="flex gap-3">
          <input
            value={newTicker}
            onChange={e => setNewTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && addAsset()}
            placeholder="Ej: SOL-USD, TLT, NVDA"
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 font-mono text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-cyan-400/50 transition-all"
          />
          <button onClick={addAsset}
            className="px-5 py-3 bg-cyan-400/10 border border-cyan-400/30 text-cyan-400 rounded-lg font-mono text-xs font-bold hover:bg-cyan-400/20 transition-all">
            Agregar
          </button>
        </div>
        <p className="font-mono text-xs text-zinc-600 mt-2">
          Tip: Usá el Analizador primero para evaluar si el activo mejora tu cartera.
        </p>
      </div>

      {/* Sizing rules */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Reglas de sizing</div>
        <div className="divide-y divide-zinc-800">
          {RULES.map(r => (
            <div key={r.label} className="flex items-center justify-between py-4">
              <div>
                <div className="font-bold text-sm text-zinc-200">{r.label}</div>
                <div className="font-mono text-xs text-zinc-500 mt-0.5">{r.desc}</div>
              </div>
              <div className="font-mono text-sm font-bold text-cyan-400 bg-cyan-400/7 border border-cyan-400/15 px-3 py-1.5 rounded-lg">
                {r.val}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
