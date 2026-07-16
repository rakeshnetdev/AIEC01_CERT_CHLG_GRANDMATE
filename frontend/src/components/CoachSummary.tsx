import React from "react";
import { Sparkles, TrendingDown, Target, ExternalLink } from "lucide-react";
import type { CoachReport } from "../lib/api";

interface CoachSummaryProps {
  report: CoachReport;
}

export function CoachSummary({ report }: CoachSummaryProps) {
  return (
    <div className="flex flex-col gap-10">
      {/* Metrics & Summary Card */}
      <div className="glass-panel rounded-2xl p-6 md:p-8 flex flex-col gap-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full filter blur-[60px] -z-10"></div>
        
        {/* Meta Row */}
        <div className="flex flex-wrap justify-between items-center gap-4 border-b border-white/5 pb-4">
          <div>
            <h3 className="text-xl font-bold tracking-tight text-white">{report.username}'s Game Analysis</h3>
            <p className="text-xs text-slate-400 mt-0.5">Report generated with Stockfish depth 16 & local semantic RAG</p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="px-3 py-1 bg-slate-900 border border-white/5 rounded-md text-slate-400">
              Latency: <strong className="text-sky-400 font-bold">{report.latency_s}s</strong>
            </span>
            <span className="px-3 py-1 bg-slate-900 border border-white/5 rounded-md text-slate-400">
              Cost: <strong className="text-emerald-400 font-bold">${report.cost_usd.toFixed(4)}</strong>
            </span>
          </div>
        </div>

        {/* Analysis Narration Text */}
        <div className="text-slate-300 leading-relaxed text-sm whitespace-pre-line border-l-2 border-sky-500 pl-4 py-1">
          {report.summary}
        </div>
      </div>

      {/* Explain This Position */}
      <div className="glass-panel rounded-2xl p-6 md:p-8 flex flex-col gap-4 shadow-xl">
        <h4 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-sky-400" /> Explain this position
        </h4>
        <ul className="list-disc pl-5 text-sm text-slate-300 space-y-2">
          {report.position_explanation?.length > 0 ? (
            report.position_explanation.map((item, index) => <li key={index}>{item}</li>)
          ) : (
            <li className="text-slate-500">No position explanation available yet.</li>
          )}
        </ul>
      </div>

      {/* Weaknesses and Drills */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Weaknesses List */}
        <div className="glass-panel rounded-xl p-6 flex flex-col gap-4 shadow-lg">
          <h4 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            <TrendingDown className="w-5 h-5 text-rose-400" /> Focus Weaknesses
          </h4>
          {report.top_weaknesses.length > 0 ? (
            <div className="flex flex-col gap-4">
              {report.top_weaknesses.map((w, index) => (
                <div key={index} className="flex flex-col gap-1.5 bg-slate-900/40 p-3 rounded-lg border border-white/5">
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-sm text-slate-200">{w.theme}</span>
                    <span className="text-xs text-rose-400 font-bold">{w.count} {w.count === 1 ? 'blunder' : 'blunders'}</span>
                  </div>
                  <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden">
                    <div 
                      className="bg-rose-500 h-full rounded-full" 
                      style={{ width: `${Math.min(100, (w.count / 3) * 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-slate-500">Occurrences at plies: {w.example_plies.join(", ")}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-sm italic">No significant tactical weaknesses detected. Great job!</p>
          )}
        </div>

        {/* Training Drills Card */}
        <div className="glass-panel rounded-xl p-6 flex flex-col gap-4 shadow-lg">
          <h4 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            <Target className="w-5 h-5 text-sky-400" /> Recommended Drills
          </h4>
          {report.drills.length > 0 ? (
            <div className="flex flex-col gap-3">
              {report.drills.map((d, index) => (
                <div key={index} className="flex items-center justify-between bg-slate-900/40 p-3 rounded-lg border border-white/5">
                  <div>
                    <span className="text-sm font-semibold text-slate-200 block">{d.theme} Practice</span>
                    <span className="text-xs text-slate-500">Suggested rating level: {d.rating}</span>
                  </div>
                  <a
                    href={d.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 hover:text-sky-300 p-2 rounded-lg transition-colors border border-sky-500/20"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-sm italic">No custom drills required. Ready for tournament play!</p>
          )}
        </div>
      </div>
    </div>
  );
}
