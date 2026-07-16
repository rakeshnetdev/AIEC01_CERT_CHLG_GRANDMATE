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

export interface MoveAnalysis {
  ply: number;
  fen_before: string;
  played_uci: string;
  played_san: string;
  best_uci: string;
  best_san: string;
  eval_before_cp: number;
  eval_after_cp: number;
  centipawn_loss: number;
  label: Severity;
  theme?: string;
  pv_san: string[];
}

export interface GroundingEvent {
  attempt: number;
  mode: string;
  approved: boolean;
  error_category: string;
  critique: string;
  narrative_snippet: string;
}

export interface DeveloperInsight {
  graph_state: string;
  active_nodes: string[];
  rag_queries: string[];
  rag_context: string;
  raw_prompt: string;
  stockfish_raw: MoveAnalysis[];
  retriever_type: string;
  grounding_log?: GroundingEvent[];
}

export interface CoachReport {
  username: string;
  games_reviewed: number;
  summary: string;
  findings: Explanation[];
  top_weaknesses: Weakness[];
  drills: Drill[];
  position_explanation: string[];
  latency_s: number;
  cost_usd: number;
  developer_insight?: DeveloperInsight;
  game_status?: string;
  game_result?: string;
}

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:9392";

export interface ReviewRequest {
  username?: string;
  source?: Source;
  max_games?: number;
  pgn?: string;
  session_id?: string;
  retriever_type?: string;
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
  developer_insight?: DeveloperInsight;
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

export interface CarlsenGame {
  label: string;
  pgn: string;
}

export async function fetchCarlsenGames(): Promise<CarlsenGame[]> {
  const response = await fetch(`${BACKEND_URL}/carlsen-games`);
  if (!response.ok) {
    throw new Error("Failed to load Magnus Carlsen games.");
  }
  return response.json();
}
