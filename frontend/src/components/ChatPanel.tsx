import React from "react";
import { MessageSquare, HelpCircle, Send, RefreshCw } from "lucide-react";

interface ChatPanelProps {
  messages: Array<{ sender: "user" | "ai"; text: string }>;
  chatInput: string;
  setChatInput: (s: string) => void;
  isSendingChat: boolean;
  onSubmit: (e: React.FormEvent) => void;
  chatEndRef: React.RefObject<HTMLDivElement | null>;
}

function highlightChessKeywords(text: string) {
  if (!text) return "";
  const regex = /(\*\*.*?\*\*|\b(?:blunder[s]?|blundered|mistake[s]?|inaccuracy|inaccuracies|excellent|brilliant|best|victory|victories|win[s]?|won|stockfish|en passant)\b|(?:\b\d+\.+\s*)?\b(?:[KQRBN][a-h1-8x]?[a-h][1-8]|[a-h]x[a-h][1-8]|[a-h][1-8]|\d+\.+[a-hKQRBNx+#\-=\/O]+|O-O(?:-O)?)[+#]?\b)/gi;
  const parts = text.split(regex);
  return parts.map((part, index) => {
    const lower = part.toLowerCase();
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={index} className="font-bold text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }
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

export function ChatPanel({
  messages,
  chatInput,
  setChatInput,
  isSendingChat,
  onSubmit,
  chatEndRef
}: ChatPanelProps) {
  return (
    <div className="lg:col-span-1 flex flex-col h-[650px] glass-panel rounded-2xl overflow-hidden shadow-xl border border-white/5">
      {/* Panel Header */}
      <div className="bg-slate-900/60 p-4 border-b border-white/5 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-sky-500/10 flex items-center justify-center text-sky-400 border border-sky-500/20">
          <MessageSquare className="w-4 h-4" />
        </div>
        <div>
          <h4 className="font-bold text-sm text-white">Ask your Analysis Helper</h4>
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
            <span>{m.sender === "user" ? m.text : highlightChessKeywords(m.text)}</span>
          </div>
        ))}
        {isSendingChat && (
          <div className="self-start bg-slate-900 border border-white/5 text-slate-400 rounded-2xl rounded-bl-none p-3.5 text-sm flex items-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
            <span>Helper is thinking...</span>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Chat Input Area */}
      <form onSubmit={onSubmit} className="p-4 border-t border-white/5 bg-slate-950/40 flex gap-2">
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
  );
}
