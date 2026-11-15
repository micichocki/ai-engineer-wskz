from typing import Annotated, Any, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import InjectedState, ToolNode
from langgraph.types import Command

from app import mailer
from app.config import Settings
from app.decision import DecisionModel
from app.departments import DESCRIPTIONS, Department
from app.errors import MailDeliveryError, ModelError

_SYSTEM_PROMPT = (
    "You route employee messages to company departments. "
    "Call the send_email tool exactly once with the address of the department that should "
    "handle the message. Do not answer the employee and do not write any text.\n\n"
    "Departments:\n" + "\n".join(f"- {d.value}: {text}" for d, text in DESCRIPTIONS.items())
)


class RouterState(TypedDict, total=False):
    email: str
    message: str
    messages: Annotated[list[AnyMessage], add_messages]
    suggestion: Department
    confidence: float
    sent_to: Department
    decided_by: Literal["decision_model", "agent"]


def _make_send_email(settings: Settings) -> BaseTool:
    @tool
    def send_email(
        to: Department,
        state: Annotated[dict[str, Any], InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        """Forward the employee's message by e-mail to the chosen department."""
        # The model only picks the recipient; body and Reply-To come from the request.
        mailer.send_email(settings, to=to, reply_to=state["email"], body=state["message"])
        followed_confident_suggestion = (
            to == state["suggestion"] and state["confidence"] >= settings.confidence_threshold
        )
        return Command(
            update={
                "sent_to": to,
                "decided_by": "decision_model" if followed_confident_suggestion else "agent",
                "messages": [ToolMessage(f"E-mail sent to {to.value}.", tool_call_id=tool_call_id)],
            }
        )

    return send_email


def build_graph(
    settings: Settings, chat_model: BaseChatModel, decision_model: DecisionModel
) -> CompiledStateGraph:
    """classify (decision model) -> agent (LLM tool call) -> tools (send the e-mail)."""
    send_email = _make_send_email(settings)
    agent_model = chat_model.bind_tools([send_email])

    async def classify(state: RouterState) -> RouterState:
        decision = await decision_model.classify(state["message"])
        return {"suggestion": decision.department, "confidence": decision.confidence}

    async def agent(state: RouterState) -> RouterState:
        suggestion, confidence = state["suggestion"], state["confidence"]
        if confidence >= settings.confidence_threshold:
            hint = (
                f"A classifier suggests {suggestion.value} with high confidence "
                f"({confidence:.2f}). Use it."
            )
        else:
            hint = (
                f"A classifier suggests {suggestion.value} with low confidence "
                f"({confidence:.2f}). Decide yourself; the suggestion may be wrong."
            )
        prompt = [
            SystemMessage(_SYSTEM_PROMPT),
            HumanMessage(f"Employee message:\n{state['message']}\n\n{hint}"),
        ]
        try:
            response = await agent_model.ainvoke(prompt)
        except Exception as exc:  # langchain/ollama/httpx raise unrelated types
            raise ModelError(f"Agent model {settings.agent_model!r} failed: {exc}") from exc
        if not response.tool_calls:
            raise ModelError(f"Agent model {settings.agent_model!r} made no send_email tool call.")
        # One request sends one e-mail, even if the model emits several tool calls.
        response.tool_calls = response.tool_calls[:1]
        return {"messages": [response]}

    def tool_error(exc: Exception) -> str:
        if isinstance(exc, MailDeliveryError):
            raise exc
        raise ModelError(
            f"Agent model {settings.agent_model!r} made an invalid send_email call: {exc}"
        ) from exc

    graph = StateGraph(RouterState)
    graph.add_node("classify", classify)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode([send_email], handle_tool_errors=tool_error))
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "agent")
    graph.add_edge("agent", "tools")
    graph.add_edge("tools", END)
    return graph.compile()
