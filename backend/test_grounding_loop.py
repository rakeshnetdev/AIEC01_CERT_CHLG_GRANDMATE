import sys
import os

# Inject backend/src/ to system path to load local coach modules
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(backend_dir, "src"))

from coach.agent.graph import compile_coach_graph
from config.settings import get_settings

def run_grounding_test():
    print("=" * 60)
    print("GRANDMATE GROUNDING GUARD TESTER")
    print("=" * 60)
    
    # Load settings and display current flag status
    settings = get_settings()
    print(f"Current setting: USE_LLM_JUDGE = {settings.use_llm_judge}")
    print("Initializing compiled LangGraph...")
    
    graph = compile_coach_graph()
    
    # Setup starting position PGN input
    pgn_input = '[White "Magnus"]\n[Black "Hikaru"]\n[Result "*"]\n\n1. e4 c5 *'
    
    inputs = {
        "messages": [],
        "username": "Magnus",
        "source": "lichess",
        "pgn": pgn_input,
        "game": None,
        "analyses": [],
        "rag_context": "",
        "output": ""
    }
    
    config = {"configurable": {"thread_id": "manual_grounding_test_session"}}
    
    print("\nInvoking graph workflow (fetch -> RAG -> narrate -> grounding guard)...")
    try:
        final_state = graph.invoke(inputs, config=config)
        print("\nSUCCESS! Graph execution completed.")
        print("-" * 40)
        print("Final Output Narrative:")
        print(final_state.get("output", ""))
        print("-" * 40)
        print(f"Graph check retry count: {final_state.get('retry_count', 0)}")
        print(f"Total messages in history: {len(final_state.get('messages', []))}")
        for idx, msg in enumerate(final_state.get("messages", [])):
            if msg.content.startswith("Grounding check:"):
                print(f"  -> Msg {idx}: {msg.content}")
    except Exception as e:
        print(f"\nERROR: Graph invocation failed: {e}")

if __name__ == "__main__":
    run_grounding_test()
