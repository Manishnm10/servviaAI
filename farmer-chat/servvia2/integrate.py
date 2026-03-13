"""
ServVia - Integration Module
"""
import logging

logger = logging.getLogger(__name__)

_initialized = False


def initialize_servvia():
    """Initialize ServVia Knowledge Graph - call once at startup"""
    global _initialized
    
    if _initialized:
        return
    
    try:
        from servvia2.knowledge_graph. models import seed_knowledge_graph, HERBS_DATA
        
        # Only seed if empty
        if not HERBS_DATA:
            print("Initializing ServVia Knowledge Graph...")
            seed_knowledge_graph()
        
        _initialized = True
        
    except Exception as e:
        logger.error(f"ServVia initialization error: {e}")
        print(f"ServVia initialization error: {e}")


def ensure_initialized():
    """Ensure ServVia is initialized before use"""
    global _initialized
    if not _initialized:
        initialize_servvia()


# Auto-initialize on import
initialize_servvia()
