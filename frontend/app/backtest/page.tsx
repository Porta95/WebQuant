'use client';

import { useEffect, useState } from 'react';
import { getPerformance } from '@/lib/api';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar } from 'recharts';

const SCENARIOS = [
  { key: 'covid_2020',  name: 'COVID Crash',      date: 'Feb-Mar 2020' },
  { key: 'ftx_2022',    name: 'FTX Collapse',      date: 'Nov 2022' },
  { key: 'rates_2022',  name: 'Rate Hike Cycle',   date: '2022 completo' },
  { key: 'crypto_2018', name: 'Crypto Bear',        date: '2018' },
];

export default function Backtest() {
  const [perf, setPerf]         = useState<any>(null);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    getPerformance()
      .then(setPerf)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-zinc-500 font-mono text-sm animate-pulse">Cargando backtest...</div>
    </div>
  );

  const m     = perf?.metrics || {};
  const curve = perf?.equity_curve || [];
  const rets  = perf?.weekly_returns || [];
  const dd    = perf?.drawdown_series || [];

  const ddData = dd.slice(-100).map((v: number, i: number) => ({ i, dd: v }));
  const retBins: Record<string, number> = {};
  rets.forEach((r: number) => {
    const bin = `${Math.floor(r / 2) * 2}`;
    retBins[bin] = (retBins[bin] || 0) + 1;
  });
  const distData = Object.entries(retBins)
    .sort(([a], [b]) => parseFloat(a) - parseFloat(b))
    .map(([bin, count]) => ({ bin: `${bin}%`, count }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Backtest</h1>
        <p className="font-mono text-xs text-zinc-500 mt-1">Performance histórico desde 2022</p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {[
          { label: 'CAGR', val: `+${m.cagr}%`, bench: `SPY +${m.cagr_bench}%`, color: 'text-green-400' },
          { label: 'Sharpe', val: m.sharpe, bench: 'vs SPY 0.92', color: 'text-cyan-400' },
          { label: 'Sortino', val: m.sortino, bench: 'retornos negativos', color: 'text-cyan-400' },
          { label: 'Max DD', val: `${m.max_drawdown}%`, bench: 'SPY −34%', color: 'text-red-400' },
          { label: 'Win Rate', val: `${m.win_rate}%`, bench: 'semanas ganadoras', color: 'text-green-400' },
        ].map(stat => (
          <div key={stat.label} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
            <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-2">{stat.label}</div>
            <div className={`font-mono text-xl font-bold ${stat.color}`}>{stat.val}</div>
            <div className="font-mono text-xs text-zinc-600 mt-1">{stat.bench}</div>
          </div>
        ))}
      </div>

      {/* Equity Curve */}
      {curve.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Equity Curve</div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={curve}>
              <CartesianGrid stroke="#18181b" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fill: '#52525b', fontSize: 9, fontFamily: 'monospace' }}
                tickFormatter={v => v.slice(2, 7)} interval={Math.floor(curve.length / 8)} />
              <YAxis tick={{ fill: '#52525b', fontSize: 9, fontFamily: 'monospace' }} tickFormatter={v => v.toFixed(0)} />
              <Tooltip contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 8 }}
                labelStyle={{ color: '#71717a', fontSize: 10 }} itemStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="strategy" stroke="#00d4ff" strokeWidth={2} dot={false} name="Estrategia" />
              <Line type="monotone" dataKey="benchmark" stroke="#3f3f46" strokeWidth={1.5} dot={false} strokeDasharray="4 4" name="SPY" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Drawdown */}
        {ddData.length > 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Drawdown histórico</div>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={ddData}>
                <CartesianGrid stroke="#18181b" strokeDasharray="3 3" />
                <XAxis hide />
                <YAxis tick={{ fill: '#52525b', fontSize: 9 }} tickFormatter={v => `${v}%`} />
                <Tooltip contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 8 }}
                  itemStyle={{ fontSize: 11 }} formatter={(v: any) => [`${v.toFixed(2)}%`, 'Drawdown']} />
                <Line type="monotone" dataKey="dd" stroke="#f87171" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Distribution */}
        {distData.length > 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Distribución retornos semanales</div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={distData}>
                <CartesianGrid stroke="#18181b" strokeDasharray="3 3" />
                <XAxis dataKey="bin" tick={{ fill: '#52525b', fontSize: 8 }} />
                <YAxis tick={{ fill: '#52525b', fontSize: 9 }} />
                <Tooltip contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 8 }}
                  itemStyle={{ fontSize: 11 }} />
                <Bar dataKey="count" fill="#00d4ff" opacity={0.7} radius={[2, 2, 0, 0]} name="Semanas" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Stress scenarios */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Stress Tests históricos</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {SCENARIOS.map(sc => (
            <div key={sc.key} className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
              <div className="font-bold text-sm text-zinc-200 mb-1">{sc.name}</div>
              <div className="font-mono text-xs text-zinc-500 mb-3">{sc.date}</div>
              <div className="font-mono text-xs text-zinc-500">Ver datos reales en próxima versión</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
