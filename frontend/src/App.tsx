import React, { useState, useEffect, useRef } from "react";
import { reviewGame, chatMessage } from "./lib/api";
import type { CoachReport, Source } from "./lib/api";
import { Header } from "./components/Header";
import { AnalysisForm } from "./components/AnalysisForm";
import { CoachSummary } from "./components/CoachSummary";
import { MoveBreakdown } from "./components/MoveBreakdown";
import { DevInsights } from "./components/DevInsights";
import { ChatPanel } from "./components/ChatPanel";

export default function App() {
  // Session ID generation for conversational memory
  const [sessionId] = useState(() => `session_${Math.random().toString(36).substring(2, 11)}`);
  
  // App states
  const [username, setUsername] = useState("");
  const [source, setSource] = useState<Source>("lichess");
  const [pgn, setPgn] = useState("");
  const [activeTab, setActiveTab] = useState<"fetch" | "paste">("fetch");
  const [showDevInsights, setShowDevInsights] = useState(false);
  const [activeDevTab, setActiveDevTab] = useState<"engine" | "rag" | "prompt">("engine");
  const [retrieverType, setRetrieverType] = useState<"hybrid" | "dense" | "sparse">("hybrid");
  
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
        ? { username, source, max_games: 1, session_id: sessionId, retriever_type: retrieverType }
        : { pgn, session_id: sessionId, retriever_type: retrieverType };
        
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

  return (
    <div className="min-h-screen bg-[#060814] text-slate-100 flex flex-col">
      {/* Top Navigation Header */}
      <Header />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-10 flex flex-col gap-10">
        
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
        />

        {/* Step 2: Dashboard Content */}
        {report && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
            {/* Left/Middle Column (Report Overview, Weaknesses, Findings) */}
            <div className="lg:col-span-2 flex flex-col gap-10">
              
              {/* Metrics & Summary Card */}
              <CoachSummary
                report={report}
                showDevInsights={showDevInsights}
                setShowDevInsights={setShowDevInsights}
              />

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
