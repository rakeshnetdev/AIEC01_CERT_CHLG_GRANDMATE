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
            <span>{m.text}</span>
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
