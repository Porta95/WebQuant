'use client';

import { useEffect, useState } from 'react';
import { getSignal, getPerformance, getHistory, sendTelegram } from '@/lib/api';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Area, ComposedChart
} from 'recharts';
import { Send } from 'lucide-react';

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
  'NVDA':    '#76b900',
  'KO':      '#c00',
  'V':       '#1a1f71',
};

const TOOLTIP_STYLE = {
  contentStyle: { background: '#09090b', border: '1px solid #27272a', borderRadius: 8, fontFamily: 'monospace', fontSize: 11 },
  labelStyle:   { color: '#71717a', fontSize: 10 },
  itemStyle:    { fontSize: 11 },
};

export default function Dashboard() {
  const [signal, setSignal]     = useState<any>(null);
  const [perf, setPerf]         = useState<any>(null);
  const [history, setHistory]   = useState<any[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(false);
  const [tgStatus, setTgStatus] = useState('');

  useEffect(() => {
    Promise.all([getSignal(), getPerformance(), getHistory()])
      .then(([s, p, h]) => { setSignal(s); setPerf(p); setHistory(h); })
      .catch(() => setError(true))
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
      <div className="flex gap-1.5">
        {[0,150,300].map(d => (
          <div key={d} className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce"
            style={{ animationDelay: `${d}ms` }} />
        ))}
      </div>
    </div>
  );

  if (error || !signal) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center space-y-2">
        <div className="text-red-400 font-mono text-sm">Error cargando datos del API</div>
        <button onClick={() => window.location.reload()}
          className="font-mono text-xs text-zinc-500 hover:text-zinc-300 underline">
          Reintentar
        </button>
      </div>
    </div>
  );

  const weights = signal.weights  || {};
  const phases  = signal.phases   || {};
  const buffett = signal.buffett  || {};
  const momenta = signal.momenta  || {};
  const metrics = perf?.metrics   || {};
  const curve   = perf?.equity_curve || [];

  const qualityColor = signal.quality === 'ALTA'  ? 'text-green-400' :
                       signal.quality === 'MEDIA' ? 'text-amber-400' : 'text-red-400';

  // Columnas dinámicas del historial basadas en los tickers disponibles
  const historyTickers = history.length > 0
    ? Object.keys(history[0]?.weights || {})
    : [];

  return (
    <div className="space-y-4 sm:space-y-5">

      {/* Signal Banner */}
      <div className="bg-cyan-400/5 border border-cyan-400/20 rounded-xl p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono text-[10px] sm:text-xs text-zinc-500 tracking-widest uppercase mb-1">
              Señal activa · {signal.signal_date}
            </div>
            <div className="font-bold text-xl sm:text-2xl text-cyan-400 tracking-wide truncate">
              ↻ ROTAR HACIA {signal.dominant}
            </div>
          </div>
          <button onClick={handleTelegram}
            className="flex items-center gap-2 px-3 py-2 bg-sky-500/10 border border-sky-500/30 text-sky-400 rounded-lg font-mono text-xs hover:bg-sky-500/20 transition-all flex-shrink-0">
            <Send size={12} />
            <span className="hidden sm:inline">{tgStatus || 'Telegram'}</span>
            <span className="sm:hidden">{tgStatus ? tgStatus.split(' ')[0] : '↗'}</span>
          </button>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-4 gap-2 sm:gap-4 mt-4 pt-4 border-t border-cyan-400/10">
          {[
            { label: 'CALIDAD',  val: signal.quality,          color: qualityColor },
            { label: 'CAGR',     val: metrics.cagr ? `+${metrics.cagr}%` : '—', color: 'text-green-400' },
            { label: 'SHARPE',   val: metrics.sharpe || '—',   color: 'text-cyan-400' },
            { label: 'BUFFETT',  val: `${buffett.value}%`,      color: 'text-amber-400' },
          ].map(s => (
            <div key={s.label} className="text-center">
              <div className={`font-mono text-base sm:text-xl font-bold ${s.color}`}>{s.val}</div>
              <div className="font-mono text-[9px] sm:text-xs text-zinc-500 mt-0.5 tracking-widest">{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Asignación + Fases + Buffett */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

        {/* Asignación */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5">
          <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4 flex justify-between">
            Asignación
            <span className="text-green-400 text-xs">LIVE</span>
          </div>
          <div className="space-y-2.5">
            {Object.entries(weights)
              .sort(([, a]: any, [, b]: any) => b - a)
              .map(([ticker, pct]: [string, any]) => (
                <div key={ticker} className="flex items-center gap-2 sm:gap-3">
                  <span className="font-mono text-xs font-bold w-12 sm:w-16 text-zinc-300 flex-shrink-0">
                    {ticker.replace('-USD', '')}
                  </span>
                  <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-1000"
                      style={{
                        width: `${pct * 100}%`,
                        background: ASSET_COLORS[ticker] || '#00d4ff',
                      }} />
                  </div>
                  <span className="font-mono text-xs font-bold w-8 text-right flex-shrink-0"
                    style={{ color: pct > 0 ? (ASSET_COLORS[ticker] || '#00d4ff') : '#52525b' }}>
                    {(pct * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
          </div>
        </div>

        {/* Fases */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5">
          <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">
            Fases de mercado
          </div>
          <div className="space-y-1.5">
            {Object.entries(phases).map(([ticker, info]: [string, any]) => {
              const mom    = momenta[ticker];
              const momPct = mom != null ? (mom * 100).toFixed(0) : null;
              const momClr = mom == null ? '' : mom >= 0.1 ? 'text-green-400' : mom >= 0 ? 'text-zinc-400' : 'text-red-400';
              return (
                <div key={ticker}
                  className="flex items-center justify-between py-1.5 px-2.5 sm:py-2 sm:px-3 bg-zinc-800/50 rounded-lg">
                  <div className="min-w-0 flex-1">
                    <div className="font-mono text-xs font-bold text-zinc-200">
                      {ticker.replace('-USD', '')}
                    </div>
                    <div className="font-mono text-[10px] text-zinc-500">
                      ${info.price?.toLocaleString()}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
                    {momPct != null && (
                      <span className={`font-mono text-[10px] hidden sm:block ${momClr}`}
                        title="Momentum 12-1m">
                        {mom >= 0 ? '+' : ''}{momPct}%
                      </span>
                    )}
                    <span className="font-mono text-[10px] sm:text-xs text-zinc-500 hidden sm:block">
                      {info.dist >= 0 ? '+' : ''}{info.dist?.toFixed(1)}%
                    </span>
                    <span className={`font-mono text-[10px] sm:text-xs font-bold px-1.5 sm:px-2 py-0.5 rounded border ${PHASE_COLORS[info.phase] || PHASE_COLORS.NO_DATA}`}>
                      {info.phase}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Buffett */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5 sm:col-span-2 lg:col-span-1">
          <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">
            Indicador Buffett
          </div>
          <div className="text-center py-2">
            <div className="font-mono text-4xl sm:text-5xl font-bold text-amber-400">
              {buffett.value}
              <span className="text-xl sm:text-2xl text-zinc-500">%</span>
            </div>
            <div className="font-mono text-xs tracking-widest text-amber-400 mt-2 uppercase">
              {buffett.phase}
            </div>
          </div>
          <div className="mt-3">
            <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
              <div className="h-full rounded-full bg-gradient-to-r from-green-400 via-amber-400 to-red-400 transition-all duration-1000"
                style={{ width: `${Math.min((buffett.value / 200) * 100, 100)}%` }} />
            </div>
            <div className="flex justify-between font-mono text-[10px] text-zinc-600 mt-1.5">
              <span>&lt;90 Barato</span>
              <span>120 Justo</span>
              <span>&gt;150 Caro</span>
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between p-3 bg-amber-400/5 border border-amber-400/15 rounded-lg">
            <span className="font-mono text-xs text-zinc-500 tracking-widest">MULT. EQUITY</span>
            <span className="font-mono text-sm font-bold text-amber-400">× {buffett.mult}</span>
          </div>
        </div>
      </div>

      {/* Performance Chart */}
      {curve.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase">
              Performance histórico
            </div>
            <div className="flex gap-3 sm:gap-4">
              <span className="flex items-center gap-1.5 font-mono text-xs text-cyan-400">
                <span className="w-3 sm:w-4 h-0.5 bg-cyan-400 inline-block rounded" />
                <span className="hidden sm:inline">Estrategia</span>
              </span>
              <span className="flex items-center gap-1.5 font-mono text-xs text-zinc-600">
                <span className="w-3 sm:w-4 h-0.5 bg-zinc-600 inline-block rounded" />
                <span className="hidden sm:inline">SPY B&H</span>
              </span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={curve}>
              <defs>
                <linearGradient id="dashGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#00d4ff" stopOpacity={0.12} />
                  <stop offset="95%" stopColor="#00d4ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#18181b" strokeDasharray="3 3" />
              <XAxis dataKey="date"
                tick={{ fill: '#52525b', fontSize: 9, fontFamily: 'monospace' }}
                tickFormatter={v => v.slice(2, 7)}
                interval={Math.floor(curve.length / 6)} />
              <YAxis
                tick={{ fill: '#52525b', fontSize: 9, fontFamily: 'monospace' }}
                tickFormatter={v => v.toFixed(0)} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Area type="monotone" dataKey="strategy" stroke="none" fill="url(#dashGrad)" />
              <Line type="monotone" dataKey="strategy"  stroke="#00d4ff" strokeWidth={2}   dot={false} name="Estrategia" />
              <Line type="monotone" dataKey="benchmark" stroke="#3f3f46" strokeWidth={1.5} dot={false} strokeDasharray="4 4" name="SPY B&H" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Métricas */}
      {metrics.cagr && (
        <div className="grid grid-cols-3 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-3">
          {[
            { label: 'CAGR',       val: `+${metrics.cagr}%`,       color: 'text-green-400',  bench: `SPY ${metrics.cagr_bench}%` },
            { label: 'Sharpe',     val: metrics.sharpe,            color: 'text-cyan-400',   bench: 'SPY 0.92' },
            { label: 'Max DD',     val: `${metrics.max_drawdown}%`, color: 'text-red-400',    bench: 'SPY −34%' },
            { label: 'Win Rate',   val: `${metrics.win_rate}%`,     color: 'text-green-400',  bench: 'sem. ganadoras' },
            { label: 'Volatilidad',val: `${metrics.volatility}%`,   color: 'text-amber-400',  bench: 'anualizada' },
          ].map(m => (
            <div key={m.label} className="bg-zinc-900 border border-zinc-800 rounded-xl p-3 sm:p-4">
              <div className="font-mono text-[10px] sm:text-xs text-zinc-500 tracking-widest uppercase mb-1 sm:mb-2">
                {m.label}
              </div>
              <div className={`font-mono text-base sm:text-xl font-bold ${m.color}`}>{m.val}</div>
              <div className="font-mono text-[10px] text-zinc-600 mt-1 hidden sm:block">{m.bench}</div>
            </div>
          ))}
        </div>
      )}

      {/* Historial */}
      {history.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5">
          <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">
            Historial de señales
          </div>
          <div className="overflow-x-auto -mx-4 sm:mx-0 px-4 sm:px-0">
            <table className="w-full min-w-[500px]">
              <thead>
                <tr className="border-b border-zinc-800">
                  {['Fecha', 'Dominante',
                    ...historyTickers.map(t => t.replace('-USD', '')),
                    'Buffett', 'Calidad'
                  ].map(h => (
                    <th key={h}
                      className="font-mono text-[10px] text-zinc-600 tracking-widest text-left pb-2 pr-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 10).map((row: any, i: number) => {
                  const w  = row.weights || {};
                  const qc = row.quality === 'ALTA'  ? 'text-green-400' :
                             row.quality === 'MEDIA' ? 'text-amber-400' : 'text-red-400';
                  return (
                    <tr key={i} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                      <td className="font-mono text-xs text-zinc-400 py-2.5 pr-3">{row.date}</td>
                      <td className="font-mono text-xs font-bold text-cyan-400 pr-3">{row.dominant}</td>
                      {historyTickers.map(t => (
                        <td key={t} className="font-mono text-xs text-zinc-400 pr-3">
                          {((w[t] || 0) * 100).toFixed(0)}%
                        </td>
                      ))}
                      <td className="font-mono text-xs text-amber-400 pr-3">{row.buffett?.value}%</td>
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
