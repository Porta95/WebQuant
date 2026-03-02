'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, LineChart, Search, Settings } from 'lucide-react';

const NAV = [
  { href: '/dashboard', label: 'Dashboard',  icon: LayoutDashboard },
  { href: '/backtest',  label: 'Backtest',   icon: LineChart },
  { href: '/analyzer',  label: 'Analizador', icon: Search },
  { href: '/portfolio', label: 'Cartera',    icon: Settings },
];

export default function Sidebar() {
  const path = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-52 bg-zinc-900 border-r border-zinc-800 flex flex-col py-7 z-50">
      <div className="px-6 mb-8">
        <div className="font-mono text-xs text-cyan-400 tracking-widest uppercase mb-1">Sistema</div>
        <div className="font-bold text-lg text-zinc-100 leading-tight">Quant<br/>Rotational</div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = path.startsWith(href);
          return (
            <Link key={href} href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg font-medium text-sm transition-all
                ${active
                  ? 'bg-cyan-400/10 text-cyan-400 border-l-2 border-cyan-400'
                  : 'text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800'}`}>
              <Icon size={16} className={active ? 'text-cyan-400' : 'text-zinc-600'} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-6 pt-6 border-t border-zinc-800">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
          <span className="font-mono text-xs text-green-400 tracking-widest">LIVE</span>
        </div>
        <div className="font-mono text-xs text-zinc-600 mt-1">Railway · FastAPI</div>
      </div>
    </aside>
  );
}
