"""The agent layer: LangGraph and LangChain agents over the LLM integration.

It imports no module (R2): what an agent needs from a module (the chat's tools and
preamble) is handed to it at startup by `app/main.py`.

Structure:
- core/: what every agent shares (checkpointing, memory, observability, structured calls)
- chatbot/: the chat agent, `create_agent` with its middleware, held by `ChatbotAgent`
- csv_mapping/, transaction_labeler/, insights/: the one-call agents
"""
