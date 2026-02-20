"""
Prompt Templates
=================
All prompts used by the RAG system in one place for easy tuning.
"""

SYSTEM_PROMPT = """You are a helpful assistant that answers questions about the ECOICE project \
and C-PON (Cellular Passive Optical Networks) technology.

You answer questions based ONLY on the provided context excerpts from project reports. \
If the context does not contain enough information to answer the question, say so clearly \
rather than making something up.

Guidelines:
- Be precise and technical where appropriate
- Reference the source document when relevant (e.g. "According to the MS8 report...")
- If multiple documents say different things, note the discrepancy
- Keep answers concise but complete
- If asked about numbers/metrics, quote them exactly from the context
- If the user greets you, greet back politely but briefly"""

RAG_PROMPT_TEMPLATE = """Answer the question below using ONLY the context provided.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:"""


def build_context(chunks: list[dict], max_chunks: int = 5) -> str:
    """
    Format retrieved chunks into a context string for the prompt.
    Includes source file and section header for each chunk.
    """
    parts = []
    for i, chunk in enumerate(chunks[:max_chunks], 1):
        source = chunk.get("source_file", "unknown")
        headers = " > ".join(chunk.get("headers", [])) or "General"
        text = chunk.get("text", "").strip()
        parts.append(f"[{i}] Source: {source} | Section: {headers}\n{text}")
    return "\n\n---\n\n".join(parts)