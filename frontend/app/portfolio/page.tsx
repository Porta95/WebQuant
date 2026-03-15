'use client';

import { useEffect, useState } from 'react';
import { Plus, Trash2, CheckCircle } from 'lucide-react';

<<<<<<< HEAD
type Sleeve = 'CRYPTO' | 'EQUITIES' | 'COMMODITIES';
type Asset = { ticker: string; sleeve: Sleeve; enabled: boolean; };
type PortfolioDTO = { crypto: string[]; equities: string[]; commodities: string[]; };

const API = process.env.NEXT_PUBLIC_API_URL || 'https://webquant-production.up.railway.app';
const SLEEVE_COLORS: Record<Sleeve, string> = { CRYPTO: '#f7931a', EQUITIES: '#00d4ff', COMMODITIES: '#ffd700' };
const SLEEVES: Sleeve[] = ['CRYPTO', 'EQUITIES', 'COMMODITIES'];
=======
type Sleeve = 'EQUITIES' | 'REITS' | 'CRYPTO' | 'COMMODITIES' | 'BONDS' | 'MERVAL';
type Asset  = { ticker: string; sleeve: Sleeve; enabled: boolean; };
type PortfolioDTO = {
  equities:    string[];
  reits:       string[];
  crypto:      string[];
  commodities: string[];
  bonds:       string[];
  merval:      string[];
};

const API = process.env.NEXT_PUBLIC_API_URL || 'https://webquant-production.up.railway.app';

const SLEEVE_META: Record<Sleeve, { color: string; label: string; description: string; placeholder: string }> = {
  EQUITIES:    { color: '#00d4ff', label: 'EQUITIES',    description: 'ETFs y acciones USA',              placeholder: 'Ej: NVDA, XLF, EEM' },
  REITS:       { color: '#fb923c', label: 'REITS',       description: 'Real Estate / Baja correlación',   placeholder: 'Ej: VNQ, XLRE, IYR' },
  CRYPTO:      { color: '#f7931a', label: 'CRYPTO',      description: 'Criptomonedas',                    placeholder: 'Ej: SOL-USD, BNB-USD' },
  COMMODITIES: { color: '#ffd700', label: 'COMMODITIES', description: 'Materias primas',                  placeholder: 'Ej: SLV, USO, DBC' },
  BONDS:       { color: '#a78bfa', label: 'BONDS',       description: 'Bonos / Safe haven',               placeholder: 'Ej: TLT, SHY, AGG' },
  MERVAL:      { color: '#34d399', label: 'MERVAL',      description: 'Acciones argentinas (BYMA)',        placeholder: 'Ej: TXAR.BA, TECO2.BA' },
};

const SLEEVES: Sleeve[] = ['EQUITIES', 'REITS', 'CRYPTO', 'COMMODITIES', 'BONDS', 'MERVAL'];
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)

async function fetchPortfolio(): Promise<PortfolioDTO> {
  const r = await fetch(`${API}/api/portfolio`, { cache: 'no-store' });
  if (!r.ok) throw new Error('fetch failed');
  return r.json();
}
async function savePortfolio(data: PortfolioDTO) {
  await fetch(`${API}/api/portfolio`, {
<<<<<<< HEAD
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

=======
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(data),
  });
}

function toDTO(assets: Asset[]): PortfolioDTO {
  return {
    equities:    assets.filter(a => a.sleeve === 'EQUITIES'    && a.enabled).map(a => a.ticker),
    reits:       assets.filter(a => a.sleeve === 'REITS'       && a.enabled).map(a => a.ticker),
    crypto:      assets.filter(a => a.sleeve === 'CRYPTO'      && a.enabled).map(a => a.ticker),
    commodities: assets.filter(a => a.sleeve === 'COMMODITIES' && a.enabled).map(a => a.ticker),
    bonds:       assets.filter(a => a.sleeve === 'BONDS'       && a.enabled).map(a => a.ticker),
    merval:      assets.filter(a => a.sleeve === 'MERVAL'      && a.enabled).map(a => a.ticker),
  };
}

>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
export default function Portfolio() {
  const [assets, setAssets]       = useState<Asset[]>([]);
  const [newTicker, setNewTicker] = useState('');
  const [newSleeve, setNewSleeve] = useState<Sleeve>('EQUITIES');
  const [saved, setSaved]         = useState(false);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    fetchPortfolio().then((p) => {
<<<<<<< HEAD
      setAssets([
        ...p.crypto.map((t) => ({ ticker: t, sleeve: 'CRYPTO' as Sleeve, enabled: true })),
        ...p.equities.map((t) => ({ ticker: t, sleeve: 'EQUITIES' as Sleeve, enabled: true })),
        ...p.commodities.map((t) => ({ ticker: t, sleeve: 'COMMODITIES' as Sleeve, enabled: true })),
      ]);
=======
      const list: Asset[] = [
        ...(p.equities    || []).map(t => ({ ticker: t, sleeve: 'EQUITIES'    as Sleeve, enabled: true })),
        ...(p.reits       || []).map(t => ({ ticker: t, sleeve: 'REITS'       as Sleeve, enabled: true })),
        ...(p.crypto      || []).map(t => ({ ticker: t, sleeve: 'CRYPTO'      as Sleeve, enabled: true })),
        ...(p.commodities || []).map(t => ({ ticker: t, sleeve: 'COMMODITIES' as Sleeve, enabled: true })),
        ...(p.bonds       || []).map(t => ({ ticker: t, sleeve: 'BONDS'       as Sleeve, enabled: true })),
        ...(p.merval      || []).map(t => ({ ticker: t, sleeve: 'MERVAL'      as Sleeve, enabled: true })),
      ];
      setAssets(list);
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const persist = (list: Asset[]) => {
<<<<<<< HEAD
    const dto: PortfolioDTO = {
      crypto:      list.filter((a) => a.sleeve === 'CRYPTO'      && a.enabled).map((a) => a.ticker),
      equities:    list.filter((a) => a.sleeve === 'EQUITIES'    && a.enabled).map((a) => a.ticker),
      commodities: list.filter((a) => a.sleeve === 'COMMODITIES' && a.enabled).map((a) => a.ticker),
    };
    savePortfolio(dto).then(() => { setSaved(true); setTimeout(() => setSaved(false), 2000); });
  };

  const toggle = (i: number) => { const n = assets.map((x, idx) => idx === i ? { ...x, enabled: !x.enabled } : x); setAssets(n); persist(n); };
  const remove = (i: number) => { const n = assets.filter((_, idx) => idx !== i); setAssets(n); persist(n); };
  const addAsset = () => {
    if (!newTicker.trim()) return;
    const ticker = newTicker.trim().toUpperCase();
    if (assets.find((a) => a.ticker === ticker)) { setNewTicker(''); return; }
=======
    savePortfolio(toDTO(list)).then(() => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    });
  };

  const toggle   = (i: number) => { const n = assets.map((x, idx) => idx === i ? { ...x, enabled: !x.enabled } : x); setAssets(n); persist(n); };
  const remove   = (i: number) => { const n = assets.filter((_, idx) => idx !== i); setAssets(n); persist(n); };
  const addAsset = () => {
    if (!newTicker.trim()) return;
    const ticker = newTicker.trim().toUpperCase();
    if (assets.find(a => a.ticker === ticker)) { setNewTicker(''); return; }
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
    const n = [...assets, { ticker, sleeve: newSleeve, enabled: true }];
    setAssets(n); persist(n); setNewTicker('');
  };

<<<<<<< HEAD
=======
  const totalActive = assets.filter(a => a.enabled).length;

>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Configuración de Cartera</h1>
<<<<<<< HEAD
          <p className="font-mono text-xs text-zinc-500 mt-1">Los cambios se aplican en el próximo workflow diario</p>
        </div>
        {saved && <div className="flex items-center gap-2 text-green-400 font-mono text-xs"><CheckCircle size={14} />Guardado</div>}
=======
          <p className="font-mono text-xs text-zinc-500 mt-1">
            Los cambios se aplican en el próximo workflow diario · {totalActive} activos activos
          </p>
        </div>
        {saved && (
          <div className="flex items-center gap-2 text-green-400 font-mono text-xs">
            <CheckCircle size={14} />Guardado en GitHub
          </div>
        )}
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
      </div>

      {loading ? (
        <div className="text-zinc-500 font-mono text-sm animate-pulse">Cargando cartera...</div>
      ) : (
        <>
<<<<<<< HEAD
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {SLEEVES.map((sleeve) => (
              <div key={sleeve} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-2 h-2 rounded-full" style={{ background: SLEEVE_COLORS[sleeve] }} />
                  <span className="font-bold text-sm text-zinc-200">{sleeve}</span>
                  <span className="ml-auto font-mono text-xs text-zinc-600">
                    {assets.filter((a) => a.sleeve === sleeve && a.enabled).length} activos
                  </span>
                </div>
                <div className="space-y-2">
                  {assets.filter((a) => a.sleeve === sleeve).map((asset) => {
                    const idx = assets.indexOf(asset);
                    return (
                      <div key={asset.ticker} className="flex items-center justify-between py-2 border-b border-zinc-800/50">
                        <div className="flex items-center gap-3">
                          <button onClick={() => toggle(idx)}
                            className={`w-8 h-4 rounded-full relative transition-all flex-shrink-0 ${asset.enabled ? 'bg-cyan-400/30' : 'bg-zinc-700'}`}>
                            <div className={`absolute top-0.5 w-3 h-3 rounded-full transition-all ${asset.enabled ? 'left-4 bg-cyan-400' : 'left-0.5 bg-zinc-500'}`} />
                          </button>
                          <span className={`font-mono text-xs font-bold ${asset.enabled ? 'text-zinc-200' : 'text-zinc-600'}`}>{asset.ticker}</span>
                        </div>
                        <button onClick={() => remove(idx)} className="text-zinc-700 hover:text-red-400 transition-colors ml-2">
                          <Trash2 size={12} />
                        </button>
                      </div>
                    );
                  })}
                  {assets.filter((a) => a.sleeve === sleeve).length === 0 && (
                    <div className="text-zinc-700 font-mono text-xs py-2">Sin activos</div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">Agregar nuevo activo</div>
            <div className="flex gap-3">
              <input value={newTicker} onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === 'Enter' && addAsset()}
                placeholder="Ej: SOL-USD, TLT, NVDA"
                className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 font-mono text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-cyan-400/50 transition-all" />
              <select value={newSleeve} onChange={(e) => setNewSleeve(e.target.value as Sleeve)}
                className="bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 font-mono text-sm text-zinc-100 focus:outline-none focus:border-cyan-400/50">
                <option value="EQUITIES">EQUITIES</option>
                <option value="CRYPTO">CRYPTO</option>
                <option value="COMMODITIES">COMMODITIES</option>
              </select>
              <button onClick={addAsset}
                className="px-5 py-3 bg-cyan-400/10 border border-cyan-400/30 text-cyan-400 rounded-lg font-mono text-xs font-bold hover:bg-cyan-400/20 transition-all flex items-center gap-2">
                <Plus size={14} />Agregar
              </button>
            </div>
            <p className="font-mono text-xs text-zinc-600 mt-2">Tip: Usá el Analizador primero para evaluar si el activo mejora tu cartera.</p>
=======
          {/* Grid de sleeves — 2 col en md, 3 col en lg */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {SLEEVES.map((sleeve) => {
              const meta       = SLEEVE_META[sleeve];
              const sleeveList = assets.filter(a => a.sleeve === sleeve);
              const activeCount = sleeveList.filter(a => a.enabled).length;

              return (
                <div key={sleeve} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
                  {/* Header sleeve */}
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ background: meta.color }} />
                    <span className="font-bold text-sm text-zinc-200">{meta.label}</span>
                    <span className="ml-auto font-mono text-xs text-zinc-600">
                      {activeCount} activo{activeCount !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <p className="font-mono text-[10px] text-zinc-600 mb-4">{meta.description}</p>

                  {/* Lista de activos */}
                  <div className="space-y-1.5">
                    {sleeveList.map((asset) => {
                      const idx = assets.indexOf(asset);
                      return (
                        <div key={asset.ticker}
                          className="flex items-center justify-between py-2 px-2.5 bg-zinc-800/40 rounded-lg">
                          <div className="flex items-center gap-3">
                            {/* Toggle */}
                            <button onClick={() => toggle(idx)}
                              className={`w-8 h-4 rounded-full relative transition-all flex-shrink-0 ${asset.enabled ? 'bg-cyan-400/30' : 'bg-zinc-700'}`}>
                              <div className={`absolute top-0.5 w-3 h-3 rounded-full transition-all ${asset.enabled ? 'left-4 bg-cyan-400' : 'left-0.5 bg-zinc-500'}`} />
                            </button>
                            <span className={`font-mono text-xs font-bold ${asset.enabled ? 'text-zinc-200' : 'text-zinc-600'}`}>
                              {asset.ticker}
                            </span>
                          </div>
                          <button onClick={() => remove(idx)}
                            className="text-zinc-700 hover:text-red-400 transition-colors ml-2 p-1">
                            <Trash2 size={11} />
                          </button>
                        </div>
                      );
                    })}
                    {sleeveList.length === 0 && (
                      <div className="text-zinc-700 font-mono text-xs py-3 text-center">Sin activos</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Agregar nuevo activo */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <div className="font-mono text-xs text-zinc-500 tracking-widest uppercase mb-4">
              Agregar nuevo activo
            </div>
            <div className="flex gap-3 flex-wrap sm:flex-nowrap">
              <input
                value={newTicker}
                onChange={e => setNewTicker(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === 'Enter' && addAsset()}
                placeholder={SLEEVE_META[newSleeve].placeholder}
                className="flex-1 min-w-0 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 font-mono text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-cyan-400/50 transition-all"
              />
              <select
                value={newSleeve}
                onChange={e => setNewSleeve(e.target.value as Sleeve)}
                className="bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 font-mono text-sm text-zinc-100 focus:outline-none focus:border-cyan-400/50 flex-shrink-0"
              >
                {SLEEVES.map(s => (
                  <option key={s} value={s}>{SLEEVE_META[s].label}</option>
                ))}
              </select>
              <button
                onClick={addAsset}
                className="px-5 py-3 bg-cyan-400/10 border border-cyan-400/30 text-cyan-400 rounded-lg font-mono text-xs font-bold hover:bg-cyan-400/20 transition-all flex items-center gap-2 flex-shrink-0"
              >
                <Plus size={14} />Agregar
              </button>
            </div>

            {/* Tips por sleeve */}
            <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {[
                { sleeve: 'EQUITIES',    examples: 'SPY · QQQ · XLE · XLK · XLV · EEM · NVDA' },
                { sleeve: 'REITS',       examples: 'VNQ · XLRE · IYR · SCHH' },
                { sleeve: 'CRYPTO',      examples: 'BTC-USD · ETH-USD · SOL-USD' },
                { sleeve: 'COMMODITIES', examples: 'GLD · SLV · USO · DBC' },
                { sleeve: 'BONDS',       examples: 'IEF · BIL · TLT · SHY · AGG' },
                { sleeve: 'MERVAL',      examples: 'GGAL.BA · BMA.BA · TXAR.BA · TECO2.BA · CEPU.BA' },
              ].map(tip => (
                <div key={tip.sleeve} className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0"
                    style={{ background: SLEEVE_META[tip.sleeve as Sleeve].color }} />
                  <div>
                    <span className="font-mono text-[10px] font-bold text-zinc-500">{tip.sleeve}: </span>
                    <span className="font-mono text-[10px] text-zinc-600">{tip.examples}</span>
                  </div>
                </div>
              ))}
            </div>
            <p className="font-mono text-xs text-zinc-600 mt-3">
              Todos los tickers deben existir en Yahoo Finance. Usá el Analizador para evaluar impacto antes de agregar.
            </p>
>>>>>>> 83f8e2e (feat: estrategia rotacional v3.1)
          </div>
        </>
      )}
    </div>
  );
}
