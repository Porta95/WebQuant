'use client';

import { useEffect, useState } from 'react';
import { getPerformance } from '@/lib/api';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, BarChart, Bar, ReferenceLine, Area, AreaChart, ComposedChart
} from 'recharts';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://webquant-production.up.railway.app';

const SCENARIOS = [
  { key: 'covid_2020',  name: 'COVID Crash',    date: 'Feb–Mar 2020', icon: '🦠', color: '#f87171' },
  { key: 'ftx_2022',   name: 'FTX Collapse',   date: 'Nov 2022',     icon: '💥', color: '#fb923c' },
  { key: 'rates_2022', name: 'Rate Hike Cycle', date: '2022',         icon: '📈', color: '#fbbf24' },
  { key: 'crypto_2018',name: 'Crypto Bear',     date: '2018',         icon: '🐻', color: '#a78bfa' },
];

const TOOLTIP_STYLE = {
  contentStyle: { background: '#09090b', border: '1px solid #27272a', borderRadius: 8, fontFamily: 'monospace', fontSize: 11 },
  labelStyle:   { color: '#71717a', fontSize: 10 },
  itemStyle:    { fontSize: 11 },
};

async function fetchStress(key: string) {
  const r = await fetch(`${API_URL}/api/backtest/stress/${key}`, { cache: 'no-store' });
  if (!r.ok) throw new Error('stress error');
  return r.json();
}

export default function Backtest() {
  const [perf, setPerf]             = useState<any>(null);
  const [loading, setLoading]       = useState(true);
  const [stressData, setStressData] = useState<Record<string, any>>({});
  const [activeStress, setActiveStress] = useState<string | null>(null);
  const [stressLoading, setStressLoading] = useState(false);

  useEffect(() => {
    getPerformance()
      .then(setPerf)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const loadStress = async (key: string) => {
    if (stressData[key]) { setActiveStress(key); return; }
    setStressLoading(true);
    setActiveStress(key);
    try {
      const data = await fetchStress(key);
      setStressData(prev => ({ ...prev, [key]: data }));
    } catch {}
    finally { setStressLoading(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-zinc-500 font-mono text-sm animate-pulse">Cargando backtest...</div>
    </div>
  );

  const m    = perf?.metrics || {};
  const curve = perf?.equity_curve || [];
  const rets  = (perf?.weekly_returns || []) as number[];
  const dd    = (perf?.drawdown_series || []) as number[];

  const ddData = dd.map((v, i) => ({ i, dd: parseFloat(v.toFixed(2)) }));

  // Distribución de retornos
  const retBins: Record<string, number> = {};
  rets.forEach(r => {
    const bin = `${Math.floor(r / 2) * 2}`;
    retBins[bin] = (retBins[bin] || 0) + 1;
  });
  const distData = Object.entries(retBins)
    .sort(([a], [b]) => parseFloat(a) - parseFloat(b))
    .map(([bin, count]) => ({ bin: `${bin}%`, count, positive: parseFloat(bin) >= 0 }));

  const activeScenario = activeStress ? stressData[activeStress] : null;
  const activeMeta     = SCENARIOS.find(s => s.key === activeStress);

  return (
    <div className="space-y-5">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Backtest</h1>
          <p className="font-mono text-xs text-zinc-500 mt-1">
            Performance histórico · {m.years} años · desde 2020
          </p>
        </div>
        <div className="font-mono text-xs text-zinc-600">
          {perf?.generated_at ? new Date(perf.generated_at).toLocaleString('es-AR') : ''}
        </div>
      </div>

      {/* Métricas */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: 'CAGR',       val: `+${m.cagr}%`,         bench: `SPY +${m.cagr_bench}%`,  color: 'text-green-400'  },
          { label: 'Sharpe',     val: m.sharpe,               bench: 'ratio riesgo/retorno',   color: 'text-cyan-400'   },
          { label: 'Sortino',    val: m.sortino,              bench: 'vs retornos negativos',  color: 'text-cyan-400'   },
          { label: 'Max DD',     val: `${m.max_drawdown}%`,   bench: 'SPY −34%',               color: 'text-red-400'    },
          { label: 'Win Rate',   val: `${m.win_rate}%`,       bench: 'semanas ganadoras',      color: 'text-green-400'  },
          { label: 'Volatilidad',val: `${m.volatility}%`,     bench: 'anualizada',             color: 'text-amber-400'  },
        ].map(stat => (
          <div key={stat.label} className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 sm:p-4">
            <div className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase mb-1">{stat.label}</div>
            <div className={`font-mono text-lg sm:text-xl font-bold ${stat.color}`}>{stat.val}</div>
            <div className="font-mono text-[10px] text-zinc-600 mt-1 hidden sm:block">{stat.bench}</div>
          </div>
        ))}
      </div>

      {/* Equity Curve */}
      {curve.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase">Equity Curve</div>
            <div className="flex gap-4">
              <span className="flex items-center gap-1.5 font-mono text-xs text-cyan-400">
                <span className="w-4 h-0.5 bg-cyan-400 inline-block rounded" />Estrategia
              </span>
              <span className="flex items-center gap-1.5 font-mono text-xs text-zinc-600">
                <span className="w-4 h-0.5 bg-zinc-600 inline-block rounded border-dashed" />SPY B&H
              </span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={curve}>
              <defs>
                <linearGradient id="stratGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#00d4ff" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#00d4ff" stopOpacity={0}    />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#18181b" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fill: '#52525b', fontSize: 9, fontFamily: 'monospace' }}
                tickFormatter={v => v.slice(2, 7)} interval={Math.floor(curve.length / 6)} />
              <YAxis tick={{ fill: '#52525b', fontSize: 9, fontFamily: 'monospace' }}
                tickFormatter={v => v.toFixed(0)} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Area type="monotone" dataKey="strategy" stroke="none" fill="url(#stratGrad)" />
              <Line type="monotone" dataKey="strategy"  stroke="#00d4ff" strokeWidth={2}   dot={false} name="Estrategia" />
              <Line type="monotone" dataKey="benchmark" stroke="#3f3f46" strokeWidth={1.5} dot={false} strokeDasharray="4 4" name="SPY B&H" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Drawdown + Distribución */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {ddData.length > 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5">
            <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-1">Drawdown histórico</div>
            <div className="font-mono text-xs text-red-400 mb-3">Máx: {m.max_drawdown}%</div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={ddData}>
                <defs>
                  <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#f87171" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f87171" stopOpacity={0}   />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#18181b" strokeDasharray="3 3" />
                <XAxis hide />
                <YAxis tick={{ fill: '#52525b', fontSize: 9 }} tickFormatter={v => `${v}%`} />
                <ReferenceLine y={0} stroke="#27272a" />
                <Tooltip {...TOOLTIP_STYLE} formatter={(v: any) => [`${v.toFixed(2)}%`, 'Drawdown']} />
                <Area type="monotone" dataKey="dd" stroke="#f87171" strokeWidth={1.5} fill="url(#ddGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {distData.length > 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5">
            <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-1">Distribución retornos semanales</div>
            <div className="font-mono text-xs text-zinc-600 mb-3">
              {rets.filter(r => r > 0).length} positivos · {rets.filter(r => r < 0).length} negativos
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={distData}>
                <CartesianGrid stroke="#18181b" strokeDasharray="3 3" />
                <XAxis dataKey="bin" tick={{ fill: '#52525b', fontSize: 8, fontFamily: 'monospace' }} />
                <YAxis tick={{ fill: '#52525b', fontSize: 9 }} />
                <ReferenceLine x="0%" stroke="#27272a" />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="count" radius={[2, 2, 0, 0]} name="Semanas">
                  {distData.map((entry, i) => (
                    <rect key={i} fill={entry.positive ? '#00d4ff' : '#f87171'} fillOpacity={0.7} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Stress Tests */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5">
        <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Stress Tests históricos</div>

        {/* Tabs */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-5">
          {SCENARIOS.map(sc => (
            <button key={sc.key}
              onClick={() => loadStress(sc.key)}
              className={`p-3 rounded-xl border text-left transition-all ${
                activeStress === sc.key
                  ? 'border-cyan-400/40 bg-cyan-400/5'
                  : 'border-zinc-800 hover:border-zinc-700 bg-zinc-800/30'
              }`}>
              <div className="text-lg mb-1">{sc.icon}</div>
              <div className="font-bold text-xs text-zinc-200">{sc.name}</div>
              <div className="font-mono text-[10px] text-zinc-500 mt-0.5">{sc.date}</div>
            </button>
          ))}
        </div>

        {/* Resultado del stress */}
        {stressLoading && (
          <div className="text-zinc-500 font-mono text-xs animate-pulse py-4 text-center">
            Cargando escenario...
          </div>
        )}

        {!stressLoading && activeScenario && activeMeta && (
          <div className="space-y-4 animate-in fade-in duration-300">
            {/* Stats */}
            <div className="grid grid-cols-3 gap-3">
              {[
                {
                  label: 'Estrategia',
                  val: `${activeScenario.strategy_return > 0 ? '+' : ''}${activeScenario.strategy_return}%`,
                  color: activeScenario.strategy_return >= 0 ? 'text-green-400' : 'text-red-400',
                },
                {
                  label: 'SPY Benchmark',
                  val: `${activeScenario.benchmark_return > 0 ? '+' : ''}${activeScenario.benchmark_return}%`,
                  color: activeScenario.benchmark_return >= 0 ? 'text-green-400' : 'text-red-400',
                },
                {
                  label: 'Outperformance',
                  val: `${activeScenario.outperformance > 0 ? '+' : ''}${activeScenario.outperformance}%`,
                  color: activeScenario.outperformance >= 0 ? 'text-cyan-400' : 'text-red-400',
                },
              ].map(s => (
                <div key={s.label} className="bg-zinc-800/50 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
                  <div className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase mb-1">{s.label}</div>
                  <div className={`font-mono text-lg sm:text-xl font-bold ${s.color}`}>{s.val}</div>
                </div>
              ))}
            </div>

            {/* Gráfico del escenario */}
            {activeScenario.equity_curve?.length > 0 && (
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={activeScenario.equity_curve}>
                  <CartesianGrid stroke="#18181b" strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fill: '#52525b', fontSize: 8, fontFamily: 'monospace' }}
                    tickFormatter={v => v.slice(5)} />
                  <YAxis tick={{ fill: '#52525b', fontSize: 9 }} tickFormatter={v => `${v}`} />
                  <Tooltip {...TOOLTIP_STYLE} />
                  <ReferenceLine y={100} stroke="#27272a" strokeDasharray="3 3" />
                  <Line type="monotone" dataKey="strategy"  stroke="#00d4ff" strokeWidth={2}   dot={false} name="Estrategia" />
                  <Line type="monotone" dataKey="benchmark" stroke="#3f3f46" strokeWidth={1.5} dot={false} strokeDasharray="4 4" name="SPY" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        )}

        {!stressLoading && !activeScenario && (
          <div className="text-zinc-600 font-mono text-xs py-6 text-center">
            Seleccioná un escenario para ver el análisis
          </div>
        )}
      </div>
    </div>
  );
}
