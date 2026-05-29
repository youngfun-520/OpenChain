# Building-Langchain-Agents - Other

**Pages:** 1

---

## LangChain overview - Docs by LangChain

**URL:** https://docs.langchain.com/oss/python/langchain/overview?utm_source=chatgpt.com

**Contents:**
- On this page
- LangChain overview
- Documentation Index
- ​ Create an agent
- ​ Core benefits
- Standard model interface
- Highly configurable harness
- Built on top of LangGraph
- Debug with LangSmith

LangChain provides create_agent: a minimal, highly configurable agent harness. Compose exactly the agent your use case needs from model, tools, prompt, and middleware.

Fetch the complete documentation index at: https://docs.langchain.com/llms.txt

Use this file to discover all available pages before exploring further.

Was this page helpful?

**Examples:**

Example 1 (json):
```json
# pip install -qU langchain "langchain[openai]"
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"

agent = create_agent(
    model="openai:gpt-5.4",
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "What's the weather in San Francisco?"}]}
)
print(result["messages"][-1].content_blocks)
```

---
