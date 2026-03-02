'use client';

import { useState } from 'react';
import { analyzeAsset } from '@/lib/api';
import { Search } from 'lucide-react';

const QUICK_TICKERS = ['SOL-USD', 'TLT', 'NVDA', 'SLV', 'BNB-USD', 'IAU', 'VNQ', 'XLK'];

const VERDICT_STYLES: Record<string, string> = {
  INCLUDE: 'border-green-400/30 bg-green-400/5',
  WATCH:   'border-amber-400/30 bg-amber-400/5',
  DISCARD: 'border-red-400/30 bg-red-400/5',
};
const VERDICT_TEXT: Record<string, string> = {
  INCLUDE: '✓ INCLUIR EN CARTERA',
  WATCH:   '◌ OBSERVAR',
  DISCARD: '✕ DESCARTAR',
};
const VERDICT_COLOR: Record<string, string> = {
  INCLUDE: 'text-green-400',
  WATCH:   'text-amber-400',
  DISCARD: 'text-red-400',
};

export default function Analyzer() {
  const [ticker, setTicker]   = useState('');
  const [result, setResult]   = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const analyze = async (t: string) => {
    const tk = t.trim().toUpperCase();
    if (!tk) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const data = await analyzeAsset(tk);
      setResult(data);
    } catch (e: any) {
      setError('Error analizando el activo. Verificá el ticker.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Analizador de Activos</h1>
        <p className="font-mono text-xs text-zinc-500 mt-1">Evaluá si un activo mejora tu cartera antes de incluirlo</p>
      </div>

      {/* Input */}
      <div className="flex gap-3">
        <input
          type="text"
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          onKeyDown={e => e.key === 'Enter' && analyze(ticker)}
          placeholder="SOL-USD, TLT, NVDA, SLV..."
          className="flex-1 bg-zinc-900 border border-zinc-700 rounded-xl px-5 py-4 font-mono text-base text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-cyan-400/50 focus:bg-cyan-400/5 transition-all"
        />
        <button onClick={() => analyze(ticker)}
          disabled={loading}
          className="px-6 py-4 bg-cyan-400/10 border border-cyan-400/30 text-cyan-400 rounded-xl font-mono text-sm font-bold hover:bg-cyan-400/20 transition-all disabled:opacity-50 flex items-center gap-2">
          <Search size={16} />
          {loading ? 'Analizando...' : 'Analizar'}
        </button>
      </div>

      {/* Quick chips */}
      <div className="flex gap-2 flex-wrap">
        {QUICK_TICKERS.map(t => (
          <button key={t} onClick={() => { setTicker(t); analyze(t); }}
            className="px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-full font-mono text-xs text-zinc-400 hover:text-cyan-400 hover:border-cyan-400/30 hover:bg-cyan-400/5 transition-all">
            {t}
          </button>
        ))}
      </div>

      {error && <div className="text-red-400 font-mono text-sm p-4 bg-red-400/5 border border-red-400/20 rounded-xl">{error}</div>}

      {/* Result */}
      {result && (
        <div className="space-y-5 animate-in fade-in duration-300">

          {/* Verdict */}
          <div className={`border rounded-xl p-6 flex items-center justify-between ${VERDICT_STYLES[result.verdict]}`}>
            <div>
              <div className={`font-mono text-xs tracking-widest uppercase mb-2 ${VERDICT_COLOR[result.verdict]}`}>
                Análisis: {result.ticker}
              </div>
              <div className={`font-bold text-2xl ${VERDICT_COLOR[result.verdict]}`}>
                {VERDICT_TEXT[result.verdict]}
              </div>
              <div className="font-mono text-xs text-zinc-400 mt-3 max-w-xl leading-relaxed">
                Sleeve sugerido: <span className="text-cyan-400 uppercase">{result.suggested_sleeve}</span>
                {' · '}Delta Sharpe: <span className={result.portfolio_impact.delta_sharpe > 0 ? 'text-green-400' : 'text-red-400'}>
                  {result.portfolio_impact.delta_sharpe > 0 ? '+' : ''}{result.portfolio_impact.delta_sharpe.toFixed(3)}
                </span>
              </div>
            </div>
            <div className="text-center">
              <div className={`w-20 h-20 rounded-full border-4 flex items-center justify-center flex-col ${VERDICT_COLOR[result.verdict]}`}
                style={{ borderColor: 'currentColor' }}>
                <span className="font-mono text-2xl font-bold">{result.score}</span>
              </div>
              <div className="font-mono text-xs text-zinc-500 mt-2 tracking-widest">SCORE</div>
            </div>
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Sharpe', val: result.metrics.sharpe, color: result.metrics.sharpe > 1.5 ? 'text-green-400' : result.metrics.sharpe > 0.8 ? 'text-amber-400' : 'text-red-400' },
              { label: 'Max Drawdown', val: `${result.metrics.max_dd}%`, color: 'text-red-400' },
              { label: 'Vol Anual', val: `${result.metrics.annual_vol}%`, color: result.metrics.annual_vol < 30 ? 'text-green-400' : 'text-amber-400' },
              { label: 'Retorno Anual', val: `${result.metrics.annual_ret > 0 ? '+' : ''}${result.metrics.annual_ret}%`, color: result.metrics.annual_ret > 0 ? 'text-green-400' : 'text-red-400' },
            ].map(m => (
              <div key={m.label} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-2">{m.label}</div>
                <div className={`font-mono text-xl font-bold ${m.color}`}>{m.val}</div>
              </div>
            ))}
          </div>

          {/* Correlations + Impact */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Correlación con cartera</div>
              <div className="space-y-3">
                {Object.entries(result.correlations).map(([asset, corr]: [string, any]) => {
                  const abs = Math.abs(corr);
                  const color = abs > 0.7 ? '#f87171' : abs > 0.4 ? '#fbbf24' : '#4ade80';
                  return (
                    <div key={asset} className="flex items-center gap-3">
                      <span className="font-mono text-xs font-bold w-16 text-zinc-300">{asset.replace('-USD','')}</span>
                      <div className="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${abs * 100}%`, background: color }} />
                      </div>
                      <span className="font-mono text-xs w-10 text-right" style={{ color }}>{corr.toFixed(2)}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Impacto si se incluye</div>
              <div className="space-y-3">
                {[
                  { label: 'Sharpe', before: result.portfolio_impact.sharpe_before, after: result.portfolio_impact.sharpe_after },
                  { label: 'Volatilidad', before: `${result.portfolio_impact.vol_before}%`, after: `${result.portfolio_impact.vol_after}%` },
                ].map(row => {
                  const improved = typeof row.after === 'number' ? row.after > row.before : parseFloat(row.after) < parseFloat(row.before);
                  return (
                    <div key={row.label} className="flex items-center justify-between py-2 border-b border-zinc-800">
                      <span className="font-mono text-xs text-zinc-500">{row.label}</span>
                      <div className="flex items-center gap-2 font-mono text-xs">
                        <span className="text-zinc-600">{row.before}</span>
                        <span className="text-zinc-600">→</span>
                        <span className={improved ? 'text-green-400 font-bold' : 'text-red-400 font-bold'}>{row.after}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
