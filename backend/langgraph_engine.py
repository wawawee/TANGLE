"""LangGraph-powered agent state machine"""
import json, re, os
from typing import TypedDict, Literal, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from free_gateway import FreeGateway
from agent_orchestrator import AGENT_DEFS


class AgentState(TypedDict):
    messages: list
    agent_id: str
    task: str
    turn_count: int
    max_turns: int
    final_response: str
    error: Optional[str]


TOOL_CALL_RE = re.compile(
    r"---(\w+)---\s*(.*?)\s*---END_\w+---", re.DOTALL
)


TOOL_SYSTEM = """You can call tools using this text format:

---tool_name---
{"arg1": "value1", "arg2": "value2"}
---END_tool_name---

Available tools:
- search: query (web search)
- query_memory: query, entity_name (vector memory search)
- delegate: task, agent_id (delegate to specialist)

End your response with a final answer (no tool call) when done.
"""


TOOLS: list = []  # Native function-calling not used — we parse text format (TOOL_CALL_RE)


def _parse_text_tool_calls(content: str) -> list[dict]:
    calls = []
    for match in TOOL_CALL_RE.finditer(content):
        try:
            data = json.loads(match.group(2))
            calls.append(data)
        except json.JSONDecodeError:
            pass
    return calls


class LangGraphEngine:
    def __init__(self, gateway: FreeGateway, orchestrator=None):
        self.gateway = gateway
        self._orchestrator = orchestrator
        self._graph = self._build_graph()
        self._checkpointer = MemorySaver()
        self._compiled = None

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(AgentState)
        builder.add_node("call_agent", self._call_agent)
        builder.add_node("execute_tools", self._execute_tools)
        builder.add_edge(START, "call_agent")
        builder.add_conditional_edges(
            "call_agent",
            self._router,
            {"tools": "execute_tools", END: END},
        )
        builder.add_edge("execute_tools", "call_agent")
        return builder

    def compile(self):
        self._compiled = self._graph.compile(checkpointer=self._checkpointer)
        return self._compiled

    async def _call_agent(self, state: AgentState) -> dict:
        agent = AGENT_DEFS.get(state["agent_id"])
        if not agent:
            return {"error": f"Unknown agent: {state['agent_id']}"}

        model = agent.get("model", "openrouter/meta-llama/llama-3.3-70b-instruct:free")

        messages = list(state["messages"])
        if not messages:
            system_content = agent["prompt"] + "\n\n" + TOOL_SYSTEM
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": state["task"]},
            ]

        turn_count = state.get("turn_count", 0) + 1
        tools_to_send = TOOLS if turn_count < state.get("max_turns", 10) else None

        response = await self.gateway.chat(
            model, messages, {"agent_id": state["agent_id"]}, tools=tools_to_send
        )

        if "error" in response:
            return {"error": response["error"], "turn_count": turn_count}

        content = response.get("content", "").strip()
        content = content or ""

        tool_calls = response.get("tool_calls")
        has_text_tool_calls = bool(_parse_text_tool_calls(content))

        messages.append({"role": "assistant", "content": content})

        return {
            "messages": messages,
            "turn_count": turn_count,
            "final_response": "" if (tool_calls or has_text_tool_calls) else content,
        }

    async def _execute_tools(self, state: AgentState) -> dict:
        messages = list(state["messages"])
        last = messages[-1] if messages else {}

        raw_content = last.get("content", "")
        text_tool_calls = _parse_text_tool_calls(raw_content)

        for tc in text_tool_calls:
            tool_name = tc.get("tool", "")
            tool_args = tc.get("args", {})
            result = await self._run_tool(tool_name, tool_args, state["agent_id"])
            messages.append({
                "role": "tool",
                "content": f"Tool '{tool_name}' returned: {result[:2000]}",
            })

        return {"messages": messages}

    def _router(self, state: AgentState) -> Literal["tools", "__end__"]:
        if state.get("error"):
            return END
        if state.get("turn_count", 0) >= state.get("max_turns", 10):
            return END
        if state.get("final_response"):
            return END

        messages = state.get("messages", [])
        last = messages[-1] if messages else {}
        content = last.get("content", "")

        if _parse_text_tool_calls(str(content)):
            return "tools"
        if last.get("tool_calls"):
            return "tools"

        return END

    async def _run_tool(self, tool: str, args: dict, agent_id: str) -> str:
        if self._orchestrator:
            return await self._orchestrator._execute_tool(tool, args, agent_id)
        from agent_orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(self.gateway)
        return await orch._execute_tool(tool, args, agent_id)

    async def run(
        self,
        agent_id: str,
        task: str,
        max_turns: int = 10,
        thread_id: str = "default",
    ) -> dict:
        if not self._compiled:
            self.compile()

        initial = AgentState(
            messages=[],
            agent_id=agent_id,
            task=task,
            turn_count=0,
            max_turns=max_turns,
            final_response="",
            error=None,
        )

        config = {"configurable": {"thread_id": thread_id}}

        final_state = None
        async for event in self._compiled.astream(initial, config):
            if "__end__" in event:
                break
            for node, state in event.items():
                final_state = state

        if not final_state:
            return {"error": "No state returned"}

        if final_state.get("error"):
            return {"agent_id": agent_id, "error": final_state["error"]}

        return {
            "agent_id": agent_id,
            "result": final_state.get("final_response", ""),
            "turns": final_state.get("turn_count", 0),
            "thread_id": thread_id,
        }
