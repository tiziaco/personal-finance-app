"""Chatbot agent package.

The root re-exports nothing: `app.agents.base` and `app.agents.messages` import its
`events` and `toolkit`, and `graph` imports `app.agents.base`, so a root that loaded
`graph` would close an import cycle. Import `ChatbotAgent` from `app.agents.chatbot.graph`.
"""
