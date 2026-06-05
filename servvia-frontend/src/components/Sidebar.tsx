'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Activity, Beaker, FileText, UserPlus, Clock, Moon, ShieldCheck, HeartPulse } from 'lucide-react';

const menuItems = [
  { name: 'Dashboard', path: '/', icon: Activity },
  { name: 'Lab Report Co-Pilot', path: '/lab-report', icon: FileText },
  { name: 'Skin Analysis', path: '/skin', icon: HeartPulse },
  { name: 'Chronobiology', path: '/chronobiology', icon: Moon },
  { name: 'Legacy Healthcare', path: '/legacy', icon: ShieldCheck },
  { name: 'Farmer Registry', path: '/registry', icon: UserPlus },
];

export function Sidebar({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen bg-[var(--background)]">
      {/* Sidebar */}
      <aside className="w-64 border-r border-[var(--color-border)] glass flex flex-col pt-6 z-10 hidden md:flex">
        <div className="px-6 mb-10 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center shadow-[0_0_12px_var(--color-primary-glow)]">
            <Activity className="text-white w-5 h-5" />
          </div>
          <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-primary">
            ServVia AI
          </h1>
        </div>

        <nav className="flex-1 px-4 space-y-2">
          {menuItems.map((item) => {
            const isActive = pathname === item.path;
            const Icon = item.icon;
            
            return (
              <Link 
                key={item.path} 
                href={item.path}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                  isActive 
                    ? 'bg-primary/10 text-primary border border-primary/20 shadow-[0_4px_20px_var(--color-primary-glow)]' 
                    : 'text-muted hover:bg-white/5 hover:text-white border border-transparent'
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? 'text-primary' : ''}`} />
                <span className="font-medium text-sm">{item.name}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-6 border-t border-[var(--color-border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-primary font-bold">
              MR
            </div>
            <div>
              <p className="text-sm font-semibold">User Profile</p>
              <p className="text-xs text-muted">test@example.com</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col relative overflow-y-auto w-full h-screen">
        {/* Top Navbar Mobile (Optional placeholder) */}
        <header className="md:hidden flex items-center justify-between p-4 border-b border-[var(--color-border)] glass">
          <h1 className="font-bold text-primary">ServVia AI</h1>
        </header>
        
        <div className="flex-1 p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
