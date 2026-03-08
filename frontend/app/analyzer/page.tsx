'use client';

import { useState } from 'react';
import { analyzeAsset } from '@/lib/api';
import { Search, TrendingUp, TrendingDown, Minus, Plus } from 'lucide-react';

const QUICK_TICKERS = ['SOL-USD', 'TLT', 'NVDA', 'SLV', 'BNB-USD', 'IAU', 'MSFT', 'AAPL'];

const VERDICT_CONFIG: Record<string, { style: string; text: string; color: string; bg: string }> = {
  INCLUDE: {
    style: 'border-green-400/30 bg-green-400/5',
    text:  '✓ INCLUIR EN CARTERA',
    color: 'text-green-400',
    bg:    'bg-green-400',
  },
  WATCH: {
    style: 'border-amber-400/30 bg-amber-400/5',
    text:  '◌ OBSERVAR',
    color: 'text-amber-400',
    bg:    'bg-amber-400',
  },
  DISCARD: {
    style: 'border-red-400/30 bg-red-400/5',
    text:  '✕ DESCARTAR',
    color: 'text-red-400',
    bg:    'bg-red-400',
  },
};

function ScoreRing({ score, color }: { score: number; color: string }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  return (
    <div className="relative w-20 h-20 flex items-center justify-center flex-shrink-0">
      <svg className="absolute inset-0 -rotate-90" width="80" height="80">
        <circle cx="40" cy="40" r={r} fill="none" stroke="#27272a" strokeWidth="4" />
        <circle cx="40" cy="40" r={r} fill="none"
          stroke="currentColor" strokeWidth="4"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round"
          className={color}
          style={{ transition: 'stroke-dashoffset 1s ease' }}
        />
      </svg>
      <div className="text-center z-10">
        <div className={`font-mono text-xl font-bold ${color}`}>{score}</div>
      </div>
    </div>
  );
}

function MetricBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between font-mono text-xs mb-1">
        <span className="text-zinc-500">{label}</span>
        <span className={color}>{value}</span>
      </div>
      <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color.replace('text-', 'bg-')}`}
          style={{ width: `${Math.min(Math.abs(value) / max * 100, 100)}%` }} />
      </div>
    </div>
  );
}

export default function Analyzer() {
  const [ticker, setTicker]   = useState('');
  const [result, setResult]   = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [history, setHistory] = useState<any[]>([]);

  const analyze = async (t: string) => {
    const tk = t.trim().toUpperCase();
    if (!tk) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const data = await analyzeAsset(tk);
      if (data.error) { setError(data.error); return; }
      setResult(data);
      setHistory(prev => [data, ...prev.filter(h => h.ticker !== tk)].slice(0, 5));
    } catch {
      setError('Error analizando el activo. Verificá el ticker.');
    } finally {
      setLoading(false);
    }
  };

  const vc = result ? VERDICT_CONFIG[result.verdict] : null;

  return (
    <div className="space-y-5">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Analizador de Activos</h1>
        <p className="font-mono text-xs text-zinc-500 mt-1">
          Evaluá si un activo mejora tu cartera antes de incluirlo
        </p>
      </div>

      {/* Input */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5 space-y-4">
        <div className="flex gap-2 sm:gap-3">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-600" />
            <input
              type="text"
              value={ticker}
              onChange={e => setTicker(e.target.value.toUpperCase())}
              onKeyDown={e => e.key === 'Enter' && analyze(ticker)}
              placeholder="Ej: SOL-USD, TLT, NVDA..."
              className="w-full bg-zinc-800 border border-zinc-700 rounded-xl pl-10 pr-4 py-3 font-mono text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-cyan-400/50 focus:bg-cyan-400/5 transition-all"
            />
          </div>
          <button onClick={() => analyze(ticker)}
            disabled={loading || !ticker.trim()}
            className="px-4 sm:px-6 py-3 bg-cyan-400/10 border border-cyan-400/30 text-cyan-400 rounded-xl font-mono text-xs sm:text-sm font-bold hover:bg-cyan-400/20 transition-all disabled:opacity-40 whitespace-nowrap">
            {loading ? 'Analizando...' : 'Analizar'}
          </button>
        </div>

        {/* Quick tickers */}
        <div className="flex gap-2 flex-wrap">
          {QUICK_TICKERS.map(t => (
            <button key={t} onClick={() => { setTicker(t); analyze(t); }}
              className="px-2.5 py-1 bg-zinc-800 border border-zinc-700 rounded-full font-mono text-xs text-zinc-400 hover:text-cyan-400 hover:border-cyan-400/30 hover:bg-cyan-400/5 transition-all">
              {t}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="text-red-400 font-mono text-sm p-4 bg-red-400/5 border border-red-400/20 rounded-xl">
          ⚠️ {error}
        </div>
      )}

      {loading && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 flex items-center justify-center gap-3">
          <div className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <div className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <div className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          <span className="font-mono text-xs text-zinc-500 ml-2">Analizando {ticker}...</span>
        </div>
      )}

      {/* Resultado */}
      {result && vc && (
        <div className="space-y-4 animate-in fade-in duration-300">

          {/* Verdict banner */}
          <div className={`border rounded-xl p-4 sm:p-6 ${vc.style}`}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className={`font-mono text-[10px] tracking-widest uppercase mb-1 ${vc.color}`}>
                  {result.ticker} · {result.suggested_sleeve.toUpperCase()}
                </div>
                <div className={`font-bold text-xl sm:text-2xl ${vc.color}`}>
                  {vc.text}
                </div>
                <div className="flex flex-wrap gap-4 mt-3">
                  <div className="font-mono text-xs text-zinc-400">
                    Delta Sharpe{' '}
                    <span className={result.portfolio_impact.delta_sharpe > 0 ? 'text-green-400' : 'text-red-400'}>
                      {result.portfolio_impact.delta_sharpe > 0 ? '+' : ''}
                      {result.portfolio_impact.delta_sharpe.toFixed(3)}
                    </span>
                  </div>
                  <div className="font-mono text-xs text-zinc-400">
                    Corr. media{' '}
                    <span className={Math.abs(result.metrics.avg_corr) < 0.5 ? 'text-green-400' : 'text-amber-400'}>
                      {result.metrics.avg_corr.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
              <div className="text-center flex-shrink-0">
                <ScoreRing score={result.score} color={vc.color} />
                <div className="font-mono text-[10px] text-zinc-500 mt-1 tracking-widest">SCORE</div>
              </div>
            </div>
          </div>

          {/* Métricas + Correlaciones */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

            {/* Métricas individuales */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5">
              <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">
                Métricas de {result.ticker}
              </div>
              <div className="space-y-4">
                <MetricBar
                  label="Sharpe"
                  value={result.metrics.sharpe}
                  max={3}
                  color={result.metrics.sharpe > 1.5 ? 'text-green-400' : result.metrics.sharpe > 0.8 ? 'text-amber-400' : 'text-red-400'}
                />
                <MetricBar
                  label="Retorno anual"
                  value={result.metrics.annual_ret}
                  max={100}
                  color={result.metrics.annual_ret > 0 ? 'text-green-400' : 'text-red-400'}
                />
                <MetricBar
                  label="Volatilidad anual"
                  value={result.metrics.annual_vol}
                  max={100}
                  color={result.metrics.annual_vol < 30 ? 'text-green-400' : result.metrics.annual_vol < 60 ? 'text-amber-400' : 'text-red-400'}
                />
                <MetricBar
                  label="Max Drawdown"
                  value={Math.abs(result.metrics.max_dd)}
                  max={100}
                  color={Math.abs(result.metrics.max_dd) < 20 ? 'text-green-400' : Math.abs(result.metrics.max_dd) < 40 ? 'text-amber-400' : 'text-red-400'}
                />
              </div>

              {/* Valores exactos */}
              <div className="grid grid-cols-2 gap-2 mt-4 pt-4 border-t border-zinc-800">
                {[
                  { label: 'Sharpe',       val: result.metrics.sharpe },
                  { label: 'Retorno anual',val: `${result.metrics.annual_ret > 0 ? '+' : ''}${result.metrics.annual_ret}%` },
                  { label: 'Volatilidad',  val: `${result.metrics.annual_vol}%` },
                  { label: 'Max DD',       val: `${result.metrics.max_dd}%` },
                ].map(m => (
                  <div key={m.label} className="bg-zinc-800/50 rounded-lg p-2.5">
                    <div className="font-mono text-[10px] text-zinc-600 mb-0.5">{m.label}</div>
                    <div className="font-mono text-sm font-bold text-zinc-200">{m.val}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Correlaciones */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5">
              <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">
                Correlación con cartera actual
              </div>
              <div className="space-y-3">
                {Object.entries(result.correlations).map(([asset, corr]: [string, any]) => {
                  const abs   = Math.abs(corr);
                  const color = abs > 0.7 ? '#f87171' : abs > 0.4 ? '#fbbf24' : '#4ade80';
                  const label = abs > 0.7 ? 'Alta' : abs > 0.4 ? 'Media' : 'Baja';
                  return (
                    <div key={asset} className="flex items-center gap-3">
                      <span className="font-mono text-xs font-bold w-14 text-zinc-300 flex-shrink-0">
                        {asset.replace('-USD', '')}
                      </span>
                      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all duration-700"
                          style={{ width: `${abs * 100}%`, background: color }} />
                      </div>
                      <span className="font-mono text-xs w-8 text-right" style={{ color }}>
                        {corr.toFixed(2)}
                      </span>
                      <span className="font-mono text-[10px] w-8 text-zinc-600">{label}</span>
                    </div>
                  );
                })}
              </div>

              {/* Impacto en cartera */}
              <div className="mt-4 pt-4 border-t border-zinc-800">
                <div className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase mb-3">
                  Impacto si se incluye (5% de peso)
                </div>
                <div className="space-y-2">
                  {[
                    {
                      label:  'Sharpe',
                      before: result.portfolio_impact.sharpe_before,
                      after:  result.portfolio_impact.sharpe_after,
                      better: result.portfolio_impact.sharpe_after > result.portfolio_impact.sharpe_before,
                    },
                    {
                      label:  'Volatilidad',
                      before: `${result.portfolio_impact.vol_before}%`,
                      after:  `${result.portfolio_impact.vol_after}%`,
                      better: result.portfolio_impact.vol_after < result.portfolio_impact.vol_before,
                    },
                  ].map(row => (
                    <div key={row.label} className="flex items-center justify-between py-2 px-3 bg-zinc-800/50 rounded-lg">
                      <span className="font-mono text-xs text-zinc-500">{row.label}</span>
                      <div className="flex items-center gap-2 font-mono text-xs">
                        <span className="text-zinc-600">{row.before}</span>
                        <span className="text-zinc-700">→</span>
                        <span className={row.better ? 'text-green-400 font-bold' : 'text-red-400 font-bold'}>
                          {row.after}
                        </span>
                        {row.better
                          ? <TrendingUp size={12} className="text-green-400" />
                          : <TrendingDown size={12} className="text-red-400" />
                        }
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Historial de análisis */}
      {history.length > 1 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 sm:p-5">
          <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-3">
            Comparativa de esta sesión
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[400px]">
              <thead>
                <tr className="border-b border-zinc-800">
                  {['Ticker', 'Score', 'Veredicto', 'Sharpe', 'Max DD', 'Corr. media'].map(h => (
                    <th key={h} className="font-mono text-[10px] text-zinc-600 tracking-widest text-left pb-2 pr-4">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => {
                  const vc = VERDICT_CONFIG[h.verdict];
                  return (
                    <tr key={i}
                      onClick={() => setResult(h)}
                      className="border-b border-zinc-800/50 hover:bg-zinc-800/30 cursor-pointer transition-colors">
                      <td className="font-mono text-xs font-bold text-zinc-200 py-2.5 pr-4">{h.ticker}</td>
                      <td className={`font-mono text-xs font-bold py-2.5 pr-4 ${vc.color}`}>{h.score}</td>
                      <td className={`font-mono text-xs py-2.5 pr-4 ${vc.color}`}>{vc.text}</td>
                      <td className="font-mono text-xs text-zinc-400 py-2.5 pr-4">{h.metrics.sharpe}</td>
                      <td className="font-mono text-xs text-red-400 py-2.5 pr-4">{h.metrics.max_dd}%</td>
                      <td className="font-mono text-xs text-zinc-400 py-2.5">{h.metrics.avg_corr.toFixed(2)}</td>
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
