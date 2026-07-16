import React from "react";
import { Crown, Terminal, Sun, Moon } from "lucide-react";

interface HeaderProps {
  showDevInsights: boolean;
  setShowDevInsights: (s: boolean) => void;
  hasReport: boolean;
  theme: "dark" | "light";
  setTheme: (t: "dark" | "light") => void;
}

export function Header({ showDevInsights, setShowDevInsights, hasReport, theme, setTheme }: HeaderProps) {
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
          <p className="text-xs text-slate-500 font-medium tracking-wide">AI CHESS ANALYSIS & HELPING AGENT</p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        {hasReport && (
          <button
            onClick={() => setShowDevInsights(!showDevInsights)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all border ${
              showDevInsights 
                ? "bg-indigo-500/20 border-indigo-500/40 text-indigo-300 shadow-lg shadow-indigo-500/10"
                : "bg-slate-900 border-white/5 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            {showDevInsights ? "Hide Dev Insights" : "Dev Insights"}
          </button>
        )}
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="p-2 rounded-lg border border-white/5 bg-slate-900/60 text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all flex items-center justify-center shadow-lg"
          title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
        >
          {theme === "dark" ? <Sun className="w-4 h-4 text-amber-400 animate-pulse" /> : <Moon className="w-4 h-4 text-indigo-400" />}
        </button>

        <div className="flex items-center gap-3 text-xs bg-slate-900/60 border border-white/5 px-3 py-1.5 rounded-lg text-slate-400">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          FastAPI Connected
        </div>
      </div>
    </header>
  );
}
