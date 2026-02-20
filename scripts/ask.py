"""
Script: ask.py
===============
Interactive CLI to query the RAG system.

Usage:
    # Single question
    python scripts/ask.py "What is the power consumption of C-PON?"

    # Interactive mode
    python scripts/ask.py

    # Stream answer
    python scripts/ask.py --stream "What are the C-PON test results?"
"""

import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,          # suppress INFO logs in interactive mode
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Load .env
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_system.generation.response_generator import ResponseGenerator

PROJECT_ROOT = Path(__file__).parent.parent
CHUNKS_FILE  = PROJECT_ROOT / "data" / "chunks" / "chunks.json"
API_KEY      = os.environ.get("OPENAI_API_KEY", "")


def main():
    if not API_KEY:
        print("❌ OPENAI_API_KEY not set in .env"); sys.exit(1)

    stream_mode = "--stream" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    print("🔧 Initialising RAG pipeline...")
    gen = ResponseGenerator.from_config(
        api_key=API_KEY,
        chunks_path=CHUNKS_FILE,
    )
    print("✅ Ready\n")

    # Single question from CLI args
    if args:
        question = " ".join(args)
        _ask(gen, question, stream=stream_mode)
        return

    # Interactive loop
    print("💬 ECOICE RAG Assistant  (type 'exit' to quit, '--stream' to toggle streaming)\n")
    use_stream = False
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!"); break

        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            print("Goodbye!"); break
        if question.lower() == "--stream":
            use_stream = not use_stream
            print(f"  Streaming: {'ON' if use_stream else 'OFF'}\n")
            continue

        _ask(gen, question, stream=use_stream)


def _ask(gen: ResponseGenerator, question: str, stream: bool = False):
    if stream:
        print(f"\nAssistant: ", end="", flush=True)
        tokens, sources = gen.stream_answer(question)
        for token in tokens:
            print(token, end="", flush=True)
        print(f"\n\n--- Sources ---")
        for i, s in enumerate(sources, 1):
            headers = " > ".join(s.get("headers", [])) or "General"
            print(f"  [{i}] {s['source_file']} | {headers}")
        print()
    else:
        response = gen.answer(question)
        response.print_pretty()


if __name__ == "__main__":
    main()