import React, { useState, useEffect, useRef } from "react";
import { 
  Search, 
  BookOpen, 
  MessageSquare, 
  Send, 
  ExternalLink, 
  ShieldAlert, 
  Flame, 
  Target, 
  TrendingDown, 
  CheckCircle,
  HelpCircle,
  User,
  Sparkles,
  RefreshCw
} from "lucide-react";
import { reviewGame, chatMessage } from "./lib/api";
import type { CoachReport, Severity, Source } from "./lib/api";

export default function App() {
  // Session ID generation for conversational memory
  const [sessionId] = useState(() => `session_${Math.random().toString(36).substring(2, 11)}`);
  
  // App states
  const [username, setUsername] = useState("");
  const [source, setSource] = useState<Source>("lichess");
  const [pgn, setPgn] = useState("");
  const [activeTab, setActiveTab] = useState<"fetch" | "paste">("fetch");
  
  // Loading & error states
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSendingChat, setIsSendingChat] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Results states
  const [report, setReport] = useState<CoachReport | null>(null);
  
  // Chat states
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<Array<{ sender: "user" | "ai"; text: string }>>([]);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Handle analysis request
  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsAnalyzing(true);
    setError(null);
    setReport(null);
    setMessages([]); // Reset conversation for the new game
    
    try {
      const payload = activeTab === "fetch" 
        ? { username, source, max_games: 1, session_id: sessionId }
        : { pgn, session_id: sessionId };
        
      if (activeTab === "fetch" && !username.trim()) {
        throw new Error("Please enter a username.");
      }
      if (activeTab === "paste" && !pgn.trim()) {
        throw new Error("Please paste a PGN string.");
      }

      const res = await reviewGame(payload);
      setReport(res);
      // Prime the chat panel with a welcome message from the coach
      setMessages([
        { 
          sender: "ai", 
          text: `Hi ${res.username || "Chess Learner"}! I've analyzed your game. Look at the metrics and findings, and let me know if you want to walk through specific moves or need clarification on our recommended drills!` 
        }
      ]);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "An unexpected error occurred during analysis.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Handle sending chat message
  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isSendingChat) return;

    const userText = chatInput.trim();
    setChatInput("");
    setMessages((prev) => [...prev, { sender: "user", text: userText }]);
    setIsSendingChat(true);

    try {
      const res = await chatMessage({
        message: userText,
        session_id: sessionId
      });
      setMessages((prev) => [...prev, { sender: "ai", text: res.reply }]);
    } catch (err: any) {
      console.error(err);
      setMessages((prev) => [
        ...prev, 
        { sender: "ai", text: `Sorry, I encountered an error: ${err.message || "Could not connect to the assistant."}` }
      ]);
    } finally {
      setIsSendingChat(false);
    }
  };

  // Helper to color-code move severity labels
  const getSeverityColor = (label: Severity) => {
    switch (label) {
      case "blunder": return "bg-red-500/20 text-red-400 border border-red-500/30";
      case "mistake": return "bg-amber-500/20 text-amber-400 border border-amber-500/30";
      case "inaccuracy": return "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20";
      default: return "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
    }
  };

  return (
    <div className="min-h-screen bg-[#060814] text-slate-100 flex flex-col">
      {/* Top Navigation Header */}
      <header className="glass-panel sticky top-0 z-50 border-b border-white/5 py-4 px-6 md:px-12 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-400 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <Flame className="w-6 h-6 text-white" />
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

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-10 flex flex-col gap-10">
        
        {/* Step 1: Input Area */}
        <section className="glass-panel rounded-2xl p-6 md:p-8 flex flex-col gap-6 shadow-xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-80 h-80 bg-sky-500/5 rounded-full filter blur-[80px] -z-10"></div>
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-sky-400" /> Start Your Analysis
            </h2>
            <p className="text-sm text-slate-400 mt-1">Submit your chess matches to receiveStockfish-powered tactical breakdowns and RAG-driven opening insights.</p>
          </div>

          <div className="flex border-b border-white/5 gap-4">
            <button
              onClick={() => setActiveTab("fetch")}
              className={`pb-3 text-sm font-semibold relative transition-all ${
                activeTab === "fetch" ? "text-sky-400 border-b-2 border-sky-400" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Fetch from Platform
            </button>
            <button
              onClick={() => setActiveTab("paste")}
              className={`pb-3 text-sm font-semibold relative transition-all ${
                activeTab === "paste" ? "text-sky-400 border-b-2 border-sky-400" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Upload / Paste PGN
            </button>
          </div>

          <form onSubmit={handleAnalyze} className="flex flex-col gap-4">
            {activeTab === "fetch" ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
            )}

            <button
              type="submit"
              disabled={isAnalyzing}
              className="w-full md:w-auto self-end bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-semibold py-3 px-6 rounded-lg text-sm flex items-center justify-center gap-2 transition-all disabled:opacity-50"
            >
              {isAnalyzing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Analyzing match data...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" /> Run Analysis Report
                </>
              )}
            </button>
          </form>

          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm p-4 rounded-lg flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </section>

        {/* Step 2: Dashboard Content */}
        {report && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
            {/* Left/Middle Column (Report Overview, Weaknesses, Findings) */}
            <div className="lg:col-span-2 flex flex-col gap-10">
              
              {/* Metrics & Summary Card */}
              <div className="glass-panel rounded-2xl p-6 md:p-8 flex flex-col gap-6 shadow-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full filter blur-[60px] -z-10"></div>
                
                {/* Meta Row */}
                <div className="flex flex-wrap justify-between items-center gap-4 border-b border-white/5 pb-4">
                  <div>
                    <h3 className="text-xl font-bold tracking-tight text-white">{report.username}'s Coaching Summary</h3>
                    <p className="text-xs text-slate-400 mt-0.5">Report generated with Stockfish depth 16 & local semantic RAG</p>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span className="px-3 py-1 bg-slate-900 border border-white/5 rounded-md text-slate-400">
                      Latency: <strong className="text-sky-400 font-bold">{report.latency_s}s</strong>
                    </span>
                    <span className="px-3 py-1 bg-slate-900 border border-white/5 rounded-md text-slate-400">
                      Cost: <strong className="text-emerald-400 font-bold">${report.cost_usd.toFixed(4)}</strong>
                    </span>
                  </div>
                </div>

                {/* Coaching Narration Text */}
                <div className="text-slate-300 leading-relaxed text-sm whitespace-pre-line border-l-2 border-sky-500 pl-4 py-1">
                  {report.summary}
                </div>
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

              {/* Move Breakdown Table */}
              <div className="glass-panel rounded-2xl p-6 md:p-8 flex flex-col gap-4 shadow-xl">
                <h4 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-indigo-400" /> Move-by-Move Analysis
                </h4>
                {report.findings.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-white/5 text-slate-500 font-semibold">
                          <th className="py-3 px-4">Ply</th>
                          <th className="py-3 px-4">Severity</th>
                          <th className="py-3 px-4">Mistake Explanation</th>
                          <th className="py-3 px-4 text-right">Action Plan</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.findings.map((f, index) => (
                          <tr key={index} className="border-b border-white/5 hover:bg-slate-900/20 transition-all">
                            <td className="py-4 px-4 font-mono font-semibold text-slate-400">#{f.ply}</td>
                            <td className="py-4 px-4">
                              <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full ${getSeverityColor(f.label)}`}>
                                {f.label}
                              </span>
                            </td>
                            <td className="py-4 px-4 text-slate-200 leading-normal max-w-xs md:max-w-sm">
                              {f.why}
                            </td>
                            <td className="py-4 px-4 text-right font-medium text-sky-400 max-w-xs">
                              {f.correct_plan}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm p-4 rounded-lg">
                    <CheckCircle className="w-5 h-5" />
                    <span>No errors detected in this game! Exceptional play!</span>
                  </div>
                )}
              </div>

            </div>

            {/* Right Column: Conversational AI Chat Panel */}
            <div className="lg:col-span-1 flex flex-col h-[650px] glass-panel rounded-2xl overflow-hidden shadow-xl border border-white/5">
              
              {/* Panel Header */}
              <div className="bg-slate-900/60 p-4 border-b border-white/5 flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-sky-500/10 flex items-center justify-center text-sky-400 border border-sky-500/20">
                  <MessageSquare className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-white">Ask your Grandmate Coach</h4>
                  <p className="text-[10px] text-slate-500">Conversational context holds thread history</p>
                </div>
              </div>

              {/* Chat Messages Log */}
              <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 bg-slate-950/20">
                {messages.length === 0 && (
                  <div className="flex flex-col items-center justify-center h-full text-center p-6 gap-3">
                    <HelpCircle className="w-8 h-8 text-slate-600" />
                    <p className="text-xs text-slate-500 max-w-[200px]">Once a game is analyzed, ask follow-up questions here!</p>
                  </div>
                )}
                {messages.map((m, index) => (
                  <div
                    key={index}
                    className={`flex flex-col max-w-[85%] rounded-2xl p-3.5 text-sm leading-relaxed ${
                      m.sender === "user"
                        ? "self-end bg-gradient-to-r from-sky-500 to-indigo-600 text-white rounded-br-none"
                        : "self-start bg-slate-900 border border-white/5 text-slate-300 rounded-bl-none"
                    }`}
                  >
                    <span>{m.text}</span>
                  </div>
                ))}
                {isSendingChat && (
                  <div className="self-start bg-slate-900 border border-white/5 text-slate-400 rounded-2xl rounded-bl-none p-3.5 text-sm flex items-center gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
                    <span>Coach is thinking...</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Chat Input Area */}
              <form onSubmit={handleSendChat} className="p-4 border-t border-white/5 bg-slate-950/40 flex gap-2">
                <input
                  type="text"
                  placeholder="Ask about mistakes, lines, or drills..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  disabled={messages.length === 0 || isSendingChat}
                  className="flex-1 bg-slate-900/60 border border-white/10 rounded-lg px-3 py-2 text-sm focus:border-sky-400 focus:outline-none disabled:opacity-50 text-slate-100"
                />
                <button
                  type="submit"
                  disabled={messages.length === 0 || isSendingChat || !chatInput.trim()}
                  className="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-white p-2.5 rounded-lg transition-colors flex items-center justify-center"
                >
                  <Send className="w-4 h-4" />
                </button>
              </form>

            </div>

          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-white/5 py-6 px-6 text-center text-xs text-slate-600 bg-slate-950/40">
        © 2026 Grandmate Systems, Inc. All rights reserved. Designed for AIEC01.
      </footer>
    </div>
  );
}
