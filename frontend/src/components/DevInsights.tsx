import { Terminal, ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import type { CoachReport } from "../lib/api";

interface DevInsightsProps {
  report: CoachReport;
  activeDevTab: "engine" | "rag" | "prompt" | "grounding" | "logs" | "agents";
  setActiveDevTab: (t: "engine" | "rag" | "prompt" | "grounding" | "logs" | "agents") => void;
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
          <button
            onClick={() => setActiveDevTab("grounding")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeDevTab === "grounding" ? "bg-indigo-500/20 text-indigo-300" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            🛡️ Grounding
          </button>
          <button
            onClick={() => setActiveDevTab("logs")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeDevTab === "logs" ? "bg-indigo-500/20 text-indigo-300" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            📜 Trace Logs
          </button>
          <button
            onClick={() => setActiveDevTab("agents")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeDevTab === "agents" ? "bg-indigo-500/20 text-indigo-300" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            🤖 Agent I/O
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

        {activeDevTab === "grounding" && (
          <div className="flex flex-col gap-4">
            <span className="text-xs font-semibold text-slate-400 tracking-wider">GROUNDING GUARD LOOP HISTORY:</span>
            {(!report.developer_insight.grounding_log || report.developer_insight.grounding_log.length === 0) ? (
              <div className="bg-slate-900/60 p-4 rounded-lg border border-white/10 text-xs text-slate-500 italic">
                No grounding events recorded for this analysis.
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {report.developer_insight.grounding_log.map((evt, idx) => (
                  <div
                    key={idx}
                    className={`rounded-xl border p-4 text-xs transition-all ${
                      evt.approved
                        ? "border-emerald-500/30 bg-emerald-500/5"
                        : "border-rose-500/30 bg-rose-500/5"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`inline-block w-2.5 h-2.5 rounded-full ${
                          evt.approved ? "bg-emerald-400" : "bg-rose-400"
                        }`} />
                        <span className="font-bold text-white">Attempt #{evt.attempt}</span>
                        <span className="bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider">
                          {evt.mode === "llm_judge" ? "LLM Judge" : "Deterministic"}
                        </span>
                      </div>
                      <span className={`font-bold uppercase text-[11px] tracking-wider ${
                        evt.approved ? "text-emerald-400" : "text-rose-400"
                      }`}>
                        {evt.approved ? "✓ APPROVED" : "✗ REJECTED"}
                      </span>
                    </div>
                    {!evt.approved && evt.critique && (
                      <div className="mt-2 bg-slate-950/60 p-3 rounded-lg border border-white/5">
                        <span className="text-[10px] font-semibold text-rose-400 uppercase tracking-wider">Critique:</span>
                        <p className="text-slate-300 mt-1 leading-relaxed">{evt.critique}</p>
                      </div>
                    )}
                    {evt.narrative_snippet && (
                      <div className="mt-2 bg-slate-950/60 p-3 rounded-lg border border-white/5">
                        <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Narrative Snapshot:</span>
                        <p className="text-slate-400 mt-1 font-mono leading-relaxed">{evt.narrative_snippet}…</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {activeDevTab === "logs" && (
          <div className="flex flex-col gap-4">
            <span className="text-xs font-semibold text-slate-400 tracking-wider">GRAPH EXECUTION TRACE LOGS:</span>
            {(!report.developer_insight.execution_log || report.developer_insight.execution_log.length === 0) ? (
              <div className="bg-slate-900/60 p-4 rounded-lg border border-white/10 text-xs text-slate-500 italic">
                No trace logs recorded for this execution.
              </div>
            ) : (
              <div className="bg-slate-950/80 rounded-xl border border-white/5 p-4 max-h-[350px] overflow-y-auto font-mono text-xs flex flex-col gap-2">
                {report.developer_insight.execution_log.map((logLine, idx) => {
                  const parts = logLine.split(":");
                  const prefix = parts[0];
                  const rest = parts.slice(1).join(":");
                  return (
                    <div key={idx} className="leading-relaxed text-slate-300 border-b border-white/5 pb-2 last:border-0 last:pb-0">
                      <span className="text-indigo-400 font-semibold">[{prefix}]</span>
                      <span className="text-slate-300">{rest}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
        {activeDevTab === "agents" && (
          <AgentStepsPanel report={report} />
        )}
      </div>
    </div>
  );
}

function AgentStepsPanel({ report }: { report: CoachReport }) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const steps = report.developer_insight?.agent_steps || [];

  return (
    <div className="flex flex-col gap-4">
      <span className="text-xs font-semibold text-slate-400 tracking-wider">AGENT PROMPT / RESPONSE INSPECTOR:</span>
      {steps.length === 0 ? (
        <div className="bg-slate-900/60 p-4 rounded-lg border border-white/10 text-xs text-slate-500 italic">
          No agent steps recorded for this execution.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {steps.map((step, idx) => {
            const isOpen = expandedIdx === idx;
            return (
              <div
                key={idx}
                className="rounded-xl border border-indigo-500/20 bg-slate-900/50 overflow-hidden transition-all"
              >
                <button
                  onClick={() => setExpandedIdx(isOpen ? null : idx)}
                  className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-800/40 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider">
                      Step {idx + 1}
                    </span>
                    <span className="text-sm font-semibold text-white">{step.agent_name}</span>
                  </div>
                  {isOpen
                    ? <ChevronDown className="w-4 h-4 text-slate-400" />
                    : <ChevronRight className="w-4 h-4 text-slate-400" />
                  }
                </button>
                {isOpen && (
                  <div className="px-4 pb-4 flex flex-col gap-3">
                    <div>
                      <span className="text-[10px] font-semibold text-sky-400 uppercase tracking-wider">Prompt Sent →</span>
                      <pre className="mt-1 bg-slate-950/80 p-3 rounded-lg border border-white/5 text-xs text-slate-300 whitespace-pre-wrap max-h-[250px] overflow-y-auto leading-relaxed">
                        {step.prompt}
                      </pre>
                    </div>
                    <div>
                      <span className="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider">← Response Received</span>
                      <pre className="mt-1 bg-slate-950/80 p-3 rounded-lg border border-white/5 text-xs text-slate-300 whitespace-pre-wrap max-h-[250px] overflow-y-auto leading-relaxed">
                        {step.response}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
