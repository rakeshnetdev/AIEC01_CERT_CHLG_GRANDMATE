export type Severity = "ok" | "inaccuracy" | "mistake" | "blunder";
export type Source = "lichess" | "chesscom" | "upload";

export interface Explanation {
  ply: number;
  label: Severity;
  why: string;
  correct_plan: string;
  sources: string[];
  grounded: boolean;
}

export interface Weakness {
  theme: string;
  count: number;
  example_plies: number[];
}

export interface Drill {
  puzzle_id: string;
  theme: string;
  rating: number;
  url: string;
}

export interface CoachReport {
  username: string;
  games_reviewed: number;
  summary: string;
  findings: Explanation[];
  top_weaknesses: Weakness[];
  drills: Drill[];
  latency_s: number;
  cost_usd: number;
}

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:9392";

export interface ReviewRequest {
  username?: string;
  source?: Source;
  max_games?: number;
  pgn?: string;
}

export async function reviewGame(request: ReviewRequest): Promise<CoachReport> {
  const response = await fetch(`${BACKEND_URL}/review`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to analyze game.");
  }

  return response.json();
}

export interface ChatRequest {
  message: string;
  session_id: string;
}

export interface ChatResponse {
  reply: string;
}

export async function chatMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${BACKEND_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to send message.");
  }

  return response.json();
}
