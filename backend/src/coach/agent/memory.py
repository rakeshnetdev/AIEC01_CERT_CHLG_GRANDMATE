from langgraph.checkpoint.memory import MemorySaver

_memory_saver = MemorySaver()

def get_memory_saver() -> MemorySaver:
    """Returns the global instance of LangGraph MemorySaver for session checkpointing."""
    return _memory_saver
