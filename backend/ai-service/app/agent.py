"""AI Agent - LangGraph-based multi-step agent with function calling.

This agent uses LangGraph to create a stateful, multi-step agent that:
1. Receives a user query
2. Decides which tools to call (function calling)
3. Executes tools against microservices
4. Synthesizes results into a coherent answer
5. Can take multiple steps for complex queries
"""
import json
import logging
import time
from typing import TypedDict, Annotated, Sequence, Literal, Optional, Any, Dict, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END, add_messages
from langgraph.prebuilt import ToolExecutor, ToolInvocation

from app.tools import SYSTEM_TOOLS, TOOL_DEFINITIONS

logger = logging.getLogger("ai-service.agent")


# ─────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """State of the agent graph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    intermediate_results: List[dict]
    final_answer: Optional[str]
    tool_call_count: int
    max_tool_calls: int


# ─────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Nexus AI Agent, an intelligent assistant for the Nexus User Management System.

## Your Capabilities
You have real-time access to the system's data through function calling tools. You can:
- **User Management**: Look up user profiles, list all users, search by name/department
- **Role Management**: List all roles and permissions, check what permissions a user has
- **Audit System**: Review audit logs with filters, get event statistics
- **Knowledge Base**: Query the RAG system for document-based answers, ingest new documents

## How You Work
1. **Analyze** the user's request carefully
2. **Decide** which tools to call — you can call multiple tools if needed
3. **Execute** tool calls and get real data from the system
4. **Synthesize** the results into a clear, helpful response
5. **Iterate** if needed — for complex queries you may need multiple rounds of tool calls

## Guidelines
- Always explain what you're doing before calling tools
- If you need more information, ask the user
- Be honest about limitations — if you can't do something, say so
- For comparisons (e.g., "how many users have admin role?"), make multiple tool calls
- Present data in a clean, readable format
- Respect privacy — never expose sensitive information unnecessarily
- When showing audit logs, include timestamps and event types

Available tools: {tool_names}
"""


# ─────────────────────────────────────────────────────────
# AGENT GRAPH
# ─────────────────────────────────────────────────────────

class NexusAgent:
    """Multi-step agent that orchestrates function calls across microservices."""

    def __init__(self, openai_api_key: str, model: str = "gpt-4o-mini", max_tool_calls: int = 10):
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model=model,
            temperature=0.2,
            max_tokens=2000,
        )
        self.tools = SYSTEM_TOOLS
        self.tool_executor = ToolExecutor(self.tools)
        self.max_tool_calls = max_tool_calls
        
        # Bind tools to the LLM for function calling
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Build the graph
        self.graph = self._build_graph()

    def _should_continue(self, state: AgentState) -> Literal["continue", "end"]:
        """Determine if the agent should take another step or end."""
        messages = state["messages"]
        last_message = messages[-1]
        
        # Check if tool call limit reached
        if state.get("tool_call_count", 0) >= state.get("max_tool_calls", self.max_tool_calls):
            logger.warning(f"Max tool calls ({state['max_tool_calls']}) reached")
            return "end"
        
        # If the LLM made a tool call, continue
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "continue"
        
        return "end"

    async def _call_model(self, state: AgentState) -> AgentState:
        """Call the LLM model."""
        messages = state["messages"]
        
        # Add system prompt if this is the first message
        if not any(isinstance(m, SystemMessage) for m in messages):
            tool_names = ", ".join([t.name for t in self.tools])
            system_msg = SystemMessage(content=SYSTEM_PROMPT.format(tool_names=tool_names))
            messages = [system_msg] + list(messages)
        
        response = await self.llm_with_tools.ainvoke(messages)
        
        return {
            "messages": [response],
            "tool_call_count": state.get("tool_call_count", 0),
            "max_tool_calls": state.get("max_tool_calls", self.max_tool_calls),
        }

    async def _call_tool(self, state: AgentState) -> AgentState:
        """Execute tool calls requested by the LLM."""
        messages = state["messages"]
        last_message = messages[-1]
        
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return state
        
        results = []
        for tool_call in last_message.tool_calls:
            logger.info(
                f"Agent calling tool: {tool_call['name']}",
                extra={"args": json.dumps(tool_call["args"])},
            )
            
            try:
                result = await self.tool_executor.ainvoke(
                    ToolInvocation(
                        tool=tool_call["name"],
                        tool_input=tool_call["args"],
                    )
                )
                
                results.append({
                    "tool": tool_call["name"],
                    "args": tool_call["args"],
                    "result": result,
                })
                
                tool_message = ToolMessage(
                    content=json.dumps(result, default=str),
                    tool_call_id=tool_call["id"],
                )
                
            except Exception as e:
                logger.error(f"Tool call failed: {tool_call['name']} - {e}")
                tool_message = ToolMessage(
                    content=json.dumps({"success": False, "error": str(e)}),
                    tool_call_id=tool_call["id"],
                )
                results.append({
                    "tool": tool_call["name"],
                    "args": tool_call["args"],
                    "result": {"error": str(e)},
                })
            
            messages = list(messages) + [tool_message]
        
        return {
            "messages": messages,
            "intermediate_results": state.get("intermediate_results", []) + results,
            "tool_call_count": state.get("tool_call_count", 0) + len(last_message.tool_calls),
            "max_tool_calls": state.get("max_tool_calls", self.max_tool_calls),
        }

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph agent graph."""
        workflow = StateGraph(AgentState)
        
        workflow.add_node("agent", self._call_model)
        workflow.add_node("action", self._call_tool)
        
        workflow.set_entry_point("agent")
        
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "action",
                "end": END,
            },
        )
        
        workflow.add_edge("action", "agent")
        
        return workflow.compile()

    async def run(self, query: str, conversation_history: Optional[List[dict]] = None) -> dict:
        """Run the agent with a user query.
        
        Args:
            query: The user's question or request.
            conversation_history: Optional list of previous messages 
                [{"role": "user"|"assistant", "content": "..."}]
        
        Returns:
            Agent response with final answer and trace information.
        """
        start_time = time.time()
        
        # Build initial messages
        messages = [HumanMessage(content=query)]
        
        if conversation_history:
            for msg in conversation_history:
                if msg["role"] == "user":
                    messages.insert(0, HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.insert(0, AIMessage(content=msg["content"]))
        
        # Run the agent
        result = await self.graph.ainvoke({
            "messages": messages,
            "intermediate_results": [],
            "tool_call_count": 0,
            "max_tool_calls": self.max_tool_calls,
        })
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        # Extract final answer
        final_answer = ""
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                final_answer = msg.content
                break
        
        # Build trace
        tool_calls_made = result.get("intermediate_results", [])
        trace = [
            {
                "step": i + 1,
                "tool": step["tool"],
                "args": step["args"],
                "success": step["result"].get("success", True),
            }
            for i, step in enumerate(tool_calls_made)
        ]
        
        return {
            "answer": final_answer,
            "tool_calls": len(tool_calls_made),
            "trace": trace,
            "latency_ms": round(elapsed_ms, 2),
            "metadata": {
                "agent_type": "LangGraph Multi-Step Agent",
                "model": "gpt-4o-mini",
                "max_tool_calls": self.max_tool_calls,
            },
        }