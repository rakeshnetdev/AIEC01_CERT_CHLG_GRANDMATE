import React, { useState } from "react";
import { Sparkles, TrendingDown, Target, ExternalLink, BookOpen } from "lucide-react";
import type { CoachReport } from "../lib/api";

interface CoachSummaryProps {
  report: CoachReport;
}

function highlightChessKeywords(text: string) {
  if (!text) return "";
  const regex = /(\*\*.*?\*\*|\b(?:blunder[s]?|blundered|mistake[s]?|inaccuracy|inaccuracies|excellent|brilliant|best|victory|victories|win[s]?|won|stockfish|en passant)\b|(?:\b\d+\.+\s*)?\b(?:[KQRBN][a-h1-8x]?[a-h][1-8]|[a-h]x[a-h][1-8]|[a-h][1-8]|\d+\.+[a-hKQRBNx+#\-=\/O]+|O-O(?:-O)?)[+#]?\b)/gi;
  const parts = text.split(regex);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={index} className="font-bold text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }
    const lower = part.toLowerCase();
    if (lower.startsWith("blunder")) {
      return (
        <span key={index} className="px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 font-semibold inline-block text-xs mx-0.5 align-baseline">
          {part}
        </span>
      );
    }
    if (lower.startsWith("mistake")) {
      return (
        <span key={index} className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold inline-block text-xs mx-0.5 align-baseline">
          {part}
        </span>
      );
    }
    if (lower.startsWith("inaccurac")) {
      return (
        <span key={index} className="px-1.5 py-0.5 rounded bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 font-semibold inline-block text-xs mx-0.5 align-baseline">
          {part}
        </span>
      );
    }
    if (lower === "excellent" || lower === "brilliant" || lower === "best") {
      return (
        <span key={index} className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold inline-block text-xs mx-0.5 align-baseline">
          {part}
        </span>
      );
    }
    if (lower === "stockfish") {
      return (
        <span key={index} className="px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-semibold inline-block text-xs mx-0.5 align-baseline">
          {part}
        </span>
      );
    }
    if (lower === "victory" || lower === "victories" || lower === "win" || lower === "wins" || lower === "won") {
      return (
        <span key={index} className="px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 font-semibold inline-block text-xs mx-0.5 align-baseline">
          {part}
        </span>
      );
    }
    if (lower === "en passant") {
      return (
        <span key={index} className="px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 border border-orange-500/20 font-semibold inline-block text-xs mx-0.5 align-baseline">
          {part}
        </span>
      );
    }
    
    // Check if it matches a chess move pattern
    const isMove = /^(?:\d+\.+\s*)?(?:[KQRBN][a-h1-8x]?[a-h][1-8]|[a-h]x[a-h][1-8]|[a-h][1-8]|O-O(?:-O)?)[+#]?$/i.test(part.trim());
    if (isMove) {
      return (
        <code key={index} className="px-1.5 py-0.5 rounded bg-slate-800/80 text-sky-300 font-mono text-[11px] border border-white/10 mx-0.5 align-baseline">
          {part}
        </code>
      );
    }
    
    return part;
  });
}

export function CoachSummary({ report }: CoachSummaryProps) {
  const [activeTab, setActiveTab] = useState<"summary" | "explanations">("summary");

  return (
    <div className="flex flex-col gap-10">
      {/* Unified Analysis Workspace Card */}
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

        {/* Tab Selector */}
        <div className="flex border-b border-white/5 gap-4">
          <button
            onClick={() => setActiveTab("summary")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 relative transition-all ${
              activeTab === "summary" ? "text-sky-400 border-b-2 border-sky-400" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>Narrative Summary</span>
          </button>
          <button
            onClick={() => setActiveTab("explanations")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 relative transition-all ${
              activeTab === "explanations" ? "text-sky-400 border-b-2 border-sky-400" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Sparkles className="w-4 h-4" />
            <span>Strategic Takeaways</span>
          </button>
        </div>

        {/* Content Area */}
        {activeTab === "summary" ? (
          <div className="text-slate-300 leading-relaxed text-sm whitespace-pre-line border-l-2 border-sky-500 pl-4 py-1">
            {highlightChessKeywords(report.summary)}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <ul className="list-disc pl-5 text-sm text-slate-300 space-y-3">
              {report.position_explanation?.length > 0 ? (
                report.position_explanation.map((item, index) => (
                  <li key={index} className="leading-relaxed">
                    {highlightChessKeywords(item)}
                  </li>
                ))
              ) : (
                <li className="text-slate-500 italic">No position explanation available yet.</li>
              )}
            </ul>
          </div>
        )}
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
