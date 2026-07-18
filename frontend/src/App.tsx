import React, { useState, useEffect, useRef } from "react";
import { reviewGame, chatMessage, fetchCarlsenGames } from "./lib/api";
import type { CoachReport, Source, CarlsenGame } from "./lib/api";
import { Header } from "./components/Header";
import { AnalysisForm } from "./components/AnalysisForm";
import { CoachSummary } from "./components/CoachSummary";
import { MoveBreakdown } from "./components/MoveBreakdown";
import { DevInsights } from "./components/DevInsights";
import { ChatPanel } from "./components/ChatPanel";
import { Crown, RefreshCw } from "lucide-react";

function generateSessionId() {
  return `session_${Math.random().toString(36).substring(2, 11)}`;
}

export default function App() {
  // Session ID for conversational memory. Regenerated on every "Run Analysis" (see
  // handleAnalyze) so a new user/PGN always starts a fresh LangGraph thread instead of
  // inheriting the previous game's chat history — the backend keys all state by this id.
  const [sessionId, setSessionId] = useState(generateSessionId);
  
  // App states
  const [username, setUsername] = useState("");
  const [source, setSource] = useState<Source>("lichess");
  const [pgn, setPgn] = useState("");
  const [activeTab, setActiveTab] = useState<"fetch" | "paste">("fetch");
  const [showDevInsights, setShowDevInsights] = useState(false);
  const [activeDevTab, setActiveDevTab] = useState<"engine" | "rag" | "prompt" | "grounding" | "logs" | "agents">("engine");
  const [retrieverType, setRetrieverType] = useState<"hybrid" | "dense" | "sparse">("hybrid");
  const [carlsenGames, setCarlsenGames] = useState<CarlsenGame[]>([]);
  const [carlsenError, setCarlsenError] = useState<string | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  
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
  const loaderRef = useRef<HTMLDivElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Scroll to loader when analysis starts
  useEffect(() => {
    if (isAnalyzing) {
      setTimeout(() => {
        loaderRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }
  }, [isAnalyzing]);

  // Scroll to results when report loads
  useEffect(() => {
    if (report) {
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }
  }, [report]);

  // Load Carlsen games on mount and handle 2-second splash screen timeout
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsInitialLoading(false);
    }, 2000);

    fetchCarlsenGames()
      .then((games) => {
        setCarlsenGames(games);
        if (games.length === 0) {
          setCarlsenError("The backend returned no sample games — Carlsen.pgn may be missing from the deployment.");
        }
      })
      .catch((err) => {
        console.error("Failed to load Carlsen games:", err);
        setCarlsenError("Couldn't reach the backend to load sample games. You can still paste a PGN below.");
      });

    return () => clearTimeout(timer);
  }, []);

  // Handle analysis request
  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsAnalyzing(true);
    setError(null);
    setReport(null);
    setMessages([]); // Reset conversation for the new game

    // Fresh thread per review: reusing the old session_id would resume the previous
    // game's LangGraph checkpoint (old chat history, old findings) instead of starting
    // clean. setSessionId is async, so use the new id directly for this request too.
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);

    try {
      const payload = activeTab === "fetch"
        ? { username, source, max_games: 1, session_id: newSessionId, retriever_type: retrieverType }
        : { pgn, session_id: newSessionId, retriever_type: retrieverType };
        
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
      if (res.developer_insight && report) {
        setReport({
          ...report,
          developer_insight: res.developer_insight
        });
      }
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

  if (isInitialLoading) {
    return (
      <div className="min-h-screen bg-[#060814] flex flex-col items-center justify-center relative overflow-hidden">
        {/* Background ambient glowing circles */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-sky-500/10 rounded-full filter blur-[100px]"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full filter blur-[100px]"></div>
        
        {/* Logo and Branding */}
        <div className="flex flex-col items-center gap-4 text-center z-10">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-sky-400 to-indigo-600 flex items-center justify-center shadow-2xl shadow-sky-500/30 animate-pulse">
            <Crown className="w-9 h-9 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-extrabold tracking-wider bg-gradient-to-r from-sky-400 via-indigo-200 to-white bg-clip-text text-transparent">
              GRANDMATE
            </h1>
            <p className="text-xs text-slate-500 font-bold tracking-widest mt-1">AI CHESS ANALYSIS & HELPING AGENT</p>
          </div>
          
          {/* Spinner and loading text */}
          <div className="flex items-center gap-2 text-xs text-sky-400 mt-8 font-semibold">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span>Initializing Chess Intelligence...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen flex flex-col transition-colors duration-300 ${theme === "dark" ? "bg-[#060814] text-slate-100 dark-theme" : "bg-[#f8fafc] text-slate-900 light-theme"}`}>
      {/* Top Navigation Header */}
      <Header showDevInsights={showDevInsights} setShowDevInsights={setShowDevInsights} hasReport={!!report} theme={theme} setTheme={setTheme} />

      {/* Main Container */}
      <main className={`flex-1 w-full p-6 md:p-10 flex flex-col gap-10 ${report ? "" : "max-w-7xl mx-auto"}`}>
        
        {/* Step 1: Input Area */}
        <AnalysisForm
          username={username}
          setUsername={setUsername}
          source={source}
          setSource={setSource}
          pgn={pgn}
          setPgn={setPgn}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          retrieverType={retrieverType}
          setRetrieverType={setRetrieverType}
          isAnalyzing={isAnalyzing}
          error={error}
          onSubmit={handleAnalyze}
          carlsenGames={carlsenGames}
          carlsenError={carlsenError}
        />

        {/* Step 2: Dashboard Content */}
        {isAnalyzing && (
          <div ref={loaderRef} className="glass-panel rounded-2xl p-8 flex flex-col items-center justify-center gap-4 text-center shadow-xl border border-white/5 animate-pulse">
            <RefreshCw className="w-8 h-8 animate-spin text-sky-400" />
            <h3 className="text-lg font-bold text-white">Running Grandmate Chess Analysis...</h3>
            <p className="text-xs text-slate-400 max-w-sm">Checking every move and pulling up relevant chess tips. This will take about 2 seconds.</p>
          </div>
        )}

        {report && (
          <div ref={resultsRef} className="grid grid-cols-1 lg:grid-cols-3 gap-10">
            {/* Left/Middle Column (Report Overview, Weaknesses, Findings) */}
            <div className="lg:col-span-2 flex flex-col gap-10">
              
              {/* Metrics & Summary Card */}
              <CoachSummary report={report} />

              {/* Move Breakdown Table */}
              <MoveBreakdown report={report} />

              {/* Developer Insights Panel */}
              {showDevInsights && report.developer_insight && (
                <DevInsights
                  report={report}
                  activeDevTab={activeDevTab}
                  setActiveDevTab={setActiveDevTab}
                />
              )}

            </div>

            {/* Right Column: Conversational AI Chat Panel */}
            <ChatPanel
              messages={messages}
              chatInput={chatInput}
              setChatInput={setChatInput}
              isSendingChat={isSendingChat}
              onSubmit={handleSendChat}
              chatEndRef={chatEndRef}
            />

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
