import React from "react";
import { Crown } from "lucide-react";

export function Header() {
  return (
    <header className="glass-panel sticky top-0 z-50 border-b border-white/5 py-4 px-6 md:px-12 flex justify-between items-center">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-400 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
          <Crown className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-sky-400 via-indigo-200 to-white bg-clip-text text-transparent">
            GRANDMATE
          </h1>
          <p className="text-xs text-slate-500 font-medium tracking-wide">AI CHESS COACHING SYSTEM</p>
        </div>
      </div>
      <div className="flex items-center gap-3 text-xs bg-slate-900/60 border border-white/5 px-3 py-1.5 rounded-lg text-slate-400">
        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
        FastAPI Connected
      </div>
    </header>
  );
}
