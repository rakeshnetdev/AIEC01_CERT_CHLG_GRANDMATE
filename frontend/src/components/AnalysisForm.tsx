import React from "react";
import { Search, User, Sparkles, RefreshCw, ShieldAlert } from "lucide-react";
import type { Source, PraggGame } from "../lib/api";

interface AnalysisFormProps {
  username: string;
  setUsername: (u: string) => void;
  source: Source;
  setSource: (s: Source) => void;
  pgn: string;
  setPgn: (p: string) => void;
  activeTab: "fetch" | "paste";
  setActiveTab: (t: "fetch" | "paste") => void;
  retrieverType: "hybrid" | "dense" | "sparse";
  setRetrieverType: (r: "hybrid" | "dense" | "sparse") => void;
  isAnalyzing: boolean;
  error: string | null;
  onSubmit: (e: React.FormEvent) => void;
  praggGames: PraggGame[];
}

export function AnalysisForm({
  username,
  setUsername,
  source,
  setSource,
  pgn,
  setPgn,
  activeTab,
  setActiveTab,
  retrieverType,
  setRetrieverType,
  isAnalyzing,
  error,
  onSubmit,
  praggGames
}: AnalysisFormProps) {
  return (
    <section className="glass-panel rounded-2xl p-4 md:p-5 flex flex-col gap-4 shadow-xl relative overflow-hidden">
      <div className="absolute top-0 right-0 w-80 h-80 bg-sky-500/5 rounded-full filter blur-[80px] -z-10"></div>
      
      <div className="flex items-center gap-2.5 border-b border-white/5 pb-3">
        <div className="w-7 h-7 rounded-lg bg-sky-500/10 flex items-center justify-center border border-sky-500/20 text-sky-400 shrink-0">
          <Sparkles className="w-4 h-4" />
        </div>
        <div className="flex-1">
          <h2 className="text-base font-bold tracking-tight text-white">Start Your Analysis</h2>
          <div className="flex items-center gap-3 flex-wrap mt-0.5">
            <p className="text-[11px] text-slate-400">
              Submit matches to get Stockfish evaluations and RAG-driven opening insights.
            </p>
            <button
              type="submit"
              form="analysis-form"
              disabled={isAnalyzing}
              className={`px-5 py-2.5 rounded-lg text-sm font-semibold flex items-center gap-2 transition-all border shrink-0 ${
                isAnalyzing 
                  ? "bg-slate-800 text-slate-500 border-white/5 cursor-not-allowed" 
                  : "bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white border-transparent shadow-lg shadow-sky-500/20 active:scale-[0.98]"
              }`}
            >
              {isAnalyzing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  <span>Run Analysis</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      <div className="flex border-b border-white/5 gap-4">
        <button
          type="button"
          onClick={() => setActiveTab("fetch")}
          className={`pb-3 text-sm font-semibold relative transition-all ${
            activeTab === "fetch" ? "text-sky-400 border-b-2 border-sky-400" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          Fetch from Platform
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("paste")}
          className={`pb-3 text-sm font-semibold relative transition-all ${
            activeTab === "paste" ? "text-sky-400 border-b-2 border-sky-400" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          Upload / Paste PGN
        </button>
      </div>

      <form id="analysis-form" onSubmit={onSubmit} className="flex flex-col gap-4">
        {activeTab === "fetch" ? (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold text-slate-400 tracking-wider">CHESS PLATFORM</label>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value as Source)}
                className="bg-slate-900/60 border border-white/10 rounded-lg p-3 text-sm focus:border-sky-400 focus:outline-none"
              >
                <option value="lichess">Lichess.org</option>
                <option value="chesscom">Chess.com</option>
              </select>
            </div>
            
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold text-slate-400 tracking-wider">ACTIVE PROFILES</label>
              <select
                value={username}
                onChange={(e) => {
                  if (e.target.value) {
                    setUsername(e.target.value);
                    setSource("lichess");
                  }
                }}
                className="bg-slate-900/60 border border-white/10 rounded-lg p-3 text-sm focus:border-sky-400 focus:outline-none text-slate-200"
              >
                <option value="">-- Choose profile --</option>
                {[
                  { username: "Arkadiy_Khromaev", label: "Arkadiy_Khromaev (Yearly H)" },
                  { username: "Kurald_Galain", label: "Kurald_Galain (Yearly Bullet)" },
                  { username: "celvic", label: "celvic (Weekly Blitz)" },
                  { username: "nguyenmanhduc_2x", label: "CM nguyenmanhduc_2x (Yearly Rapid)" },
                  { username: "GlasnostPerestroika", label: "GlasnostPerestroika (2026 Spring)" },
                  { username: "bzdybowicz", label: "bzdybowicz (Yearly)" },
                  { username: "Master-06", label: "Master-06 (Yearly)" },
                  { username: "alexa0112358", label: "alexa0112358 (Weekly)" },
                  { username: "Surgut_Challenger", label: "Surgut_Challenger (Yearly Three-check)" },
                  { username: "Tetiksh1Agrawal", label: "Tetiksh1Agrawal (Yearly)" },
                  { username: "maxwellssilvrhaMMer", label: "maxwellssilvrhaMMer" }
                ].map((player) => (
                  <option key={player.username} value={player.username} className="bg-slate-950 text-slate-100">
                    {player.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-2 md:col-span-2">
              <label className="text-xs font-semibold text-slate-400 tracking-wider">USERNAME</label>
              <div className="relative">
                <User className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-500" />
                <input
                  type="text"
                  placeholder="e.g. magnus, drnykterstein"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-slate-900/60 border border-white/10 rounded-lg p-3 pl-10 text-sm focus:border-sky-400 focus:outline-none"
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {praggGames && praggGames.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-bold text-slate-500 tracking-wider uppercase">Load Praggnanandhaa's Top Games</label>
                <select
                  onChange={(e) => {
                    if (e.target.value) {
                      setPgn(e.target.value);
                    }
                  }}
                  className="w-full md:max-w-md bg-slate-900/60 border border-white/10 rounded-lg p-2 text-xs focus:border-sky-400 focus:outline-none text-slate-300"
                  defaultValue=""
                >
                  <option value="">-- Select a game from Praggnanandhaa.pgn --</option>
                  {praggGames.map((game, idx) => (
                    <option key={idx} value={game.pgn} className="bg-slate-950 text-slate-100">
                      {game.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold text-slate-400 tracking-wider">PGN GAME DATA</label>
              <textarea
                rows={5}
                placeholder="Paste standard PGN format block..."
                value={pgn}
                onChange={(e) => setPgn(e.target.value)}
                className="bg-slate-900/60 border border-white/10 rounded-lg p-3 text-sm font-mono focus:border-sky-400 focus:outline-none resize-none"
              />
            </div>
          </div>
        )}

        {/* Retriever Strategy Selection Row */}
        <div className="flex flex-col gap-2 border-t border-white/5 pt-4">
          <label className="text-xs font-semibold text-slate-400 tracking-wider">RETRIEVER STRATEGY</label>
          <div className="flex flex-wrap gap-2">
            {[
              { id: "hybrid", label: "Fused Hybrid (RRF)", desc: "Best of both: Vector + Keyword" },
              { id: "dense", label: "Semantic Search", desc: "Embeddings only" },
              { id: "sparse", label: "Keyword (BM25)", desc: "Exact query matches" }
            ].map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setRetrieverType(item.id as any)}
                className={`flex-1 min-w-[200px] text-left p-3 rounded-lg border text-xs transition-all ${
                  retrieverType === item.id 
                    ? "bg-sky-500/10 border-sky-400 text-sky-300 shadow-lg shadow-sky-500/5" 
                    : "bg-slate-900/60 border-white/10 text-slate-400 hover:text-slate-300"
                }`}
              >
                <strong className="block font-bold text-slate-200 mb-0.5">{item.label}</strong>
                <span>{item.desc}</span>
              </button>
            ))}
          </div>
        </div>
      </form>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm p-4 rounded-lg flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
    </section>
  );
}
