import React from "react";
import { Terminal } from "lucide-react";
import type { CoachReport } from "../lib/api";

interface DevInsightsProps {
  report: CoachReport;
  activeDevTab: "engine" | "rag" | "prompt";
  setActiveDevTab: (t: "engine" | "rag" | "prompt") => void;
}

export function DevInsights({ report, activeDevTab, setActiveDevTab }: DevInsightsProps) {
  if (!report.developer_insight) return null;

  return (
    <div className="glass-panel rounded-2xl p-6 md:p-8 flex flex-col gap-6 shadow-xl border border-indigo-500/20 bg-slate-950/40">
      <div className="flex flex-wrap justify-between items-center gap-4 border-b border-white/5 pb-4">
        <div>
          <h4 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            <Terminal className="w-5 h-5 text-indigo-400" /> Graph Execution Inspector
          </h4>
          <p className="text-xs text-slate-500 mt-0.5">Real-time tracing of LangGraph nodes & pipeline states</p>
        </div>
        <div className="flex border border-white/5 bg-slate-900/60 p-1 rounded-lg gap-1">
          <button
            onClick={() => setActiveDevTab("engine")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeDevTab === "engine" ? "bg-indigo-500/20 text-indigo-300" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            ♟️ Stockfish
          </button>
          <button
            onClick={() => setActiveDevTab("rag")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeDevTab === "rag" ? "bg-indigo-500/20 text-indigo-300" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            📚 RAG Store
          </button>
          <button
            onClick={() => setActiveDevTab("prompt")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeDevTab === "prompt" ? "bg-indigo-500/20 text-indigo-300" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            📝 LLM Prompt
          </button>
        </div>
      </div>

      <div className="text-sm">
        {activeDevTab === "engine" && (
          <div className="flex flex-col gap-4">
            <span className="text-xs font-semibold text-slate-400 tracking-wider">RAW CENTIPAWN LOSS ANALYSIS:</span>
            <div className="overflow-x-auto max-h-[300px] overflow-y-auto border border-white/5 rounded-xl">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-950 border-b border-white/5 text-slate-500 font-semibold sticky top-0">
                    <th className="py-2.5 px-3">Ply</th>
                    <th className="py-2.5 px-3">Played Move</th>
                    <th className="py-2.5 px-3">Stockfish Best</th>
                    <th className="py-2.5 px-3">CP Loss</th>
                    <th className="py-2.5 px-3">Eval Before</th>
                    <th className="py-2.5 px-3">Eval After</th>
                  </tr>
                </thead>
                <tbody>
                  {report.developer_insight.stockfish_raw.map((item, idx) => (
                    <tr key={idx} className="border-b border-white/5 hover:bg-slate-900/10 transition-colors">
                      <td className="py-3 px-3 font-mono text-slate-400">#{item.ply}</td>
                      <td className="py-3 px-3 font-semibold text-white">{item.played_san} ({item.played_uci})</td>
                      <td className="py-3 px-3 font-semibold text-emerald-400">{item.best_san} ({item.best_uci})</td>
                      <td className="py-3 px-3 font-mono font-bold text-rose-400">-{item.centipawn_loss}</td>
                      <td className="py-3 px-3 font-mono text-slate-400">{item.eval_before_cp}</td>
                      <td className="py-3 px-3 font-mono text-slate-400">{item.eval_after_cp}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeDevTab === "rag" && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-slate-400 tracking-wider flex items-center justify-between">
                <span>RETRIEVER CALL:</span>
                <span className="bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider">
                  Mode: {report.developer_insight?.retriever_type || "hybrid"}
                </span>
              </span>
              <div className="bg-slate-900/60 p-3 rounded-lg border border-white/10 text-xs font-mono text-indigo-300">
                {`retrieve_context(query, persist_dir, limit, retriever_type="${report.developer_insight?.retriever_type || "hybrid"}")`}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-slate-400 tracking-wider">GENERATED RAG QUERIES:</span>
              <div className="flex flex-wrap gap-2">
                {report.developer_insight.rag_queries.map((q, idx) => (
                  <span key={idx} className="bg-sky-500/10 border border-sky-500/20 text-sky-400 px-2.5 py-1 rounded-md text-xs font-semibold">
                    "{q}"
                  </span>
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold text-slate-400 tracking-wider">RETRIEVED CONTEXT (CHROMADB + BM25):</span>
              <div className="bg-slate-950 p-4 rounded-xl border border-white/5 max-h-60 overflow-y-auto text-xs font-mono text-slate-300 whitespace-pre-line leading-relaxed">
                {report.developer_insight.rag_context || "No RAG context retrieved for this match."}
              </div>
            </div>
          </div>
        )}

        {activeDevTab === "prompt" && (
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold text-slate-400 tracking-wider">AUGMENTED SYSTEM PROMPT (GEMINI INPUT):</span>
            <div className="bg-slate-950 p-4 rounded-xl border border-white/5 max-h-[350px] overflow-y-auto text-xs font-mono text-slate-300 whitespace-pre-wrap leading-relaxed">
              {report.developer_insight.raw_prompt}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
