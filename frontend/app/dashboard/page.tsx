'use client';

import { useEffect, useState } from 'react';
import { getSignal, getPerformance, getHistory, sendTelegram } from '@/lib/api';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';
import { Send, TrendingUp, Shield, Activity, RefreshCw } from 'lucide-react';

const PHASE_COLORS: Record<string, string> = {
  EARLY:    'text-green-400 bg-green-400/10 border-green-400/20',
  OK:       'text-cyan-400 bg-cyan-400/10 border-cyan-400/20',
  EXTENDED: 'text-amber-400 bg-amber-400/10 border-amber-400/20',
  BROKEN:   'text-red-400 bg-red-400/10 border-red-400/20',
  NO_DATA:  'text-zinc-500 bg-zinc-500/10 border-zinc-500/20',
};

const ASSET_COLORS: Record<string, string> = {
  'QQQ':     '#00d4ff',
  'SPY':     '#00d4ff',
  'BTC-USD': '#f7931a',
  'ETH-USD': '#627eea',
  'GLD':     '#ffd700',
};

export default function Dashboard() {
  const [signal, setSignal]       = useState<any>(null);
  const [perf, setPerf]           = useState<any>(null);
  const [history, setHistory]     = useState<any[]>([]);
  const [loading, setLoading]     = useState(true);
  const [tgStatus, setTgStatus]   = useState('');

  useEffect(() => {
    Promise.all([getSignal(), getPerformance(), getHistory()])
      .then(([s, p, h]) => { setSignal(s); setPerf(p); setHistory(h); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleTelegram = async () => {
    setTgStatus('Enviando...');
    try {
      const r = await sendTelegram();
      setTgStatus(r.ok ? '✅ Enviado' : '❌ Error');
    } catch { setTgStatus('❌ Error'); }
    setTimeout(() => setTgStatus(''), 3000);
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-zinc-500 font-mono text-sm animate-pulse">Cargando señal...</div>
    </div>
  );

  if (!signal) return (
    <div className="text-red-400 font-mono text-sm p-8">Error cargando datos del API</div>
  );

  const weights   = signal.weights || {};
  const phases    = signal.phases  || {};
  const buffett   = signal.buffett || {};
  const metrics   = perf?.metrics  || {};
  const curve     = perf?.equity_curve || [];

  const qualityColor = signal.quality === 'ALTA' ? 'text-green-400' :
                       signal.quality === 'MEDIA' ? 'text-amber-400' : 'text-red-400';

  return (
    <div className="space-y-6">

      {/* Signal Banner */}
      <div className="bg-cyan-400/5 border border-cyan-400/20 rounded-xl p-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-1">Señal activa · {signal.signal_date}</div>
          <div className="font-bold text-2xl text-cyan-400 tracking-wide">↻ ROTAR HACIA {signal.dominant}</div>
        </div>
        <div className="flex gap-6 flex-wrap">
          <div className="text-center">
            <div className={`font-mono text-xl font-bold ${qualityColor}`}>{signal.quality}</div>
            <div className="font-mono text-xs text-zinc-500 mt-1 tracking-widest">CALIDAD</div>
          </div>
          {metrics.cagr && (
            <div className="text-center">
              <div className="font-mono text-xl font-bold text-green-400">+{metrics.cagr}%</div>
              <div className="font-mono text-xs text-zinc-500 mt-1 tracking-widest">CAGR</div>
            </div>
          )}
          {metrics.sharpe && (
            <div className="text-center">
              <div className="font-mono text-xl font-bold text-cyan-400">{metrics.sharpe}</div>
              <div className="font-mono text-xs text-zinc-500 mt-1 tracking-widest">SHARPE</div>
            </div>
          )}
          <div className="text-center">
            <div className="font-mono text-xl font-bold text-amber-400">{buffett.value}%</div>
            <div className="font-mono text-xs text-zinc-500 mt-1 tracking-widest">BUFFETT</div>
          </div>
        </div>
        <button onClick={handleTelegram}
          className="flex items-center gap-2 px-4 py-2 bg-sky-500/10 border border-sky-500/30 text-sky-400 rounded-lg font-mono text-xs hover:bg-sky-500/20 transition-all">
          <Send size={14} />
          {tgStatus || 'Telegram'}
        </button>
      </div>

      {/* Row 1: Allocation + Phases + Buffett */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">

        {/* Allocation */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4 flex justify-between">
            Asignación
            <span className="text-green-400 text-xs">LIVE</span>
          </div>
          <div className="space-y-3">
            {Object.entries(weights)
              .sort(([,a]: any, [,b]: any) => b - a)
              .map(([ticker, pct]: [string, any]) => (
              <div key={ticker} className="flex items-center gap-3">
                <span className="font-mono text-xs font-bold w-16 text-zinc-300">{ticker.replace('-USD','')}</span>
                <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-1000"
                    style={{ width: `${pct * 100}%`, background: ASSET_COLORS[ticker] || '#00d4ff' }} />
                </div>
                <span className="font-mono text-xs font-bold w-10 text-right"
                  style={{ color: pct > 0 ? (ASSET_COLORS[ticker] || '#00d4ff') : '#52525b' }}>
                  {(pct * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Phases */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Fases de mercado</div>
          <div className="space-y-2">
            {Object.entries(phases).map(([ticker, info]: [string, any]) => (
              <div key={ticker} className="flex items-center justify-between py-2 px-3 bg-zinc-800/50 rounded-lg">
                <div>
                  <div className="font-mono text-xs font-bold text-zinc-200">{ticker.replace('-USD','')}</div>
                  <div className="font-mono text-xs text-zinc-500">${info.price?.toLocaleString()}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-zinc-500">
                    {info.dist >= 0 ? '+' : ''}{info.dist?.toFixed(1)}%
                  </span>
                  <span className={`font-mono text-xs font-bold px-2 py-0.5 rounded border ${PHASE_COLORS[info.phase] || PHASE_COLORS.NO_DATA}`}>
                    {info.phase}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Buffett */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Indicador Buffett</div>
          <div className="text-center py-3">
            <div className="font-mono text-5xl font-bold text-amber-400">{buffett.value}
              <span className="text-2xl text-zinc-500">%</span>
            </div>
            <div className="font-mono text-xs tracking-widest text-amber-400 mt-2 uppercase">{buffett.phase}</div>
          </div>
          <div className="mt-3">
            <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div className="h-full rounded-full bg-gradient-to-r from-green-400 via-amber-400 to-red-400"
                style={{ width: `${Math.min((buffett.value / 200) * 100, 100)}%` }} />
            </div>
            <div className="flex justify-between font-mono text-xs text-zinc-600 mt-1">
              <span>&lt;90 Barato</span>
              <span>120 Justo</span>
              <span>&gt;150 Caro</span>
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between p-3 bg-amber-400/5 border border-amber-400/15 rounded-lg">
            <span className="font-mono text-xs text-zinc-500 tracking-widest">MULT. EQUITY</span>
            <span className="font-mono text-sm font-bold text-amber-400">× {buffett.mult}</span>
          </div>
        </div>
      </div>

      {/* Performance Chart */}
      {curve.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4 flex justify-between items-center">
            Performance histórico
            <div className="flex gap-4">
              <span className="flex items-center gap-1.5 text-cyan-400"><span className="w-4 h-0.5 bg-cyan-400 inline-block rounded" />Estrategia</span>
              <span className="flex items-center gap-1.5 text-zinc-600"><span className="w-4 h-0.5 bg-zinc-600 inline-block rounded" />SPY B&H</span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={curve.slice(-80)}>
              <CartesianGrid stroke="#18181b" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fill: '#52525b', fontSize: 9, fontFamily: 'monospace' }}
                tickFormatter={v => v.slice(2, 7)} interval={Math.floor(curve.length / 8)} />
              <YAxis tick={{ fill: '#52525b', fontSize: 9, fontFamily: 'monospace' }}
                tickFormatter={v => v.toFixed(0)} />
              <Tooltip contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 8 }}
                labelStyle={{ color: '#71717a', fontSize: 10, fontFamily: 'monospace' }}
                itemStyle={{ fontSize: 11, fontFamily: 'monospace' }} />
              <Line type="monotone" dataKey="strategy" stroke="#00d4ff" strokeWidth={2} dot={false} name="Estrategia" />
              <Line type="monotone" dataKey="benchmark" stroke="#3f3f46" strokeWidth={1.5} dot={false}
                strokeDasharray="4 4" name="SPY B&H" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Metrics Row */}
      {metrics.cagr && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {[
            { label: 'CAGR', val: `+${metrics.cagr}%`, color: 'text-green-400', bench: `SPY ${metrics.cagr_bench}%` },
            { label: 'Sharpe', val: metrics.sharpe, color: 'text-cyan-400', bench: 'SPY 0.92' },
            { label: 'Max DD', val: `${metrics.max_drawdown}%`, color: 'text-red-400', bench: 'SPY −34%' },
            { label: 'Win Rate', val: `${metrics.win_rate}%`, color: 'text-green-400', bench: 'semanas ganadoras' },
            { label: 'Volatilidad', val: `${metrics.volatility}%`, color: 'text-amber-400', bench: 'anualizada' },
          ].map(m => (
            <div key={m.label} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
              <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-2">{m.label}</div>
              <div className={`font-mono text-xl font-bold ${m.color}`}>{m.val}</div>
              <div className="font-mono text-xs text-zinc-600 mt-1">{m.bench}</div>
            </div>
          ))}
        </div>
      )}

      {/* Signal History */}
      {history.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Historial de señales</div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-800">
                  {['Fecha','Dominante','BTC','ETH','GLD','SPY','QQQ','Buffett','Calidad'].map(h => (
                    <th key={h} className="font-mono text-xs text-zinc-600 tracking-widest text-left pb-3 pr-4">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 10).map((row: any, i: number) => {
                  const w = row.weights || {};
                  const qc = row.quality === 'ALTA' ? 'text-green-400' : row.quality === 'MEDIA' ? 'text-amber-400' : 'text-red-400';
                  return (
                    <tr key={i} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                      <td className="font-mono text-xs text-zinc-400 py-3 pr-4">{row.date}</td>
                      <td className="font-mono text-xs font-bold text-cyan-400 pr-4">{row.dominant}</td>
                      <td className="font-mono text-xs text-zinc-400 pr-4">{((w['BTC-USD']||0)*100).toFixed(0)}%</td>
                      <td className="font-mono text-xs text-zinc-400 pr-4">{((w['ETH-USD']||0)*100).toFixed(0)}%</td>
                      <td className="font-mono text-xs text-zinc-400 pr-4">{((w['GLD']||0)*100).toFixed(0)}%</td>
                      <td className="font-mono text-xs text-zinc-400 pr-4">{((w['SPY']||0)*100).toFixed(0)}%</td>
                      <td className="font-mono text-xs text-zinc-400 pr-4">{((w['QQQ']||0)*100).toFixed(0)}%</td>
                      <td className="font-mono text-xs text-amber-400 pr-4">{row.buffett?.value}%</td>
                      <td className={`font-mono text-xs font-bold ${qc}`}>{row.quality}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
