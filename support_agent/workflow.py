from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from support_agent.classify import classify_ticket
from support_agent.decide import decide_action
from support_agent.faq import match_faq
from support_agent.models import (
    Action,
    Classification,
    CloseRequest,
    FAQMatch,
    HandoffRequest,
    ReplyRequest,
    ReplyVerification,
)
from support_agent.verify import verify_reply
from support_agent.prepare_request import prepare_request


class WorkflowState(TypedDict):
    ticket: dict
    faq_text: str
    classification: Classification
    faq_match: FAQMatch | None
    action: Action
    request: ReplyRequest | HandoffRequest | CloseRequest | None
    verification: ReplyVerification | None
    handoff_reason: str


def classify_node(state: WorkflowState):
    ticket = state["ticket"]
    return {
        "classification": classify_ticket(ticket["subject"], ticket["body"]),
        "faq_match": None,
        "request": None,
        "verification": None,
        "handoff_reason": "",
    }


def route_classification(state: WorkflowState):
    if state["classification"].proposed_action == "reply":
        return "match_faq"
    return "decide"


def match_faq_node(state: WorkflowState):
    ticket = state["ticket"]
    return {"faq_match": match_faq(ticket["subject"], ticket["body"], state["faq_text"])}


def decide_node(state: WorkflowState):
    classification = state["classification"]
    action = decide_action(classification, state["faq_match"])
    return {"action": action, "classification": classification}


def prepare_request_node(state: WorkflowState):
    ticket = state["ticket"]
    return {"request": prepare_request(
        subject=ticket["subject"],
        body=ticket["body"],
        classification=state["classification"],
        action=state["action"],
        faq_text=state["faq_text"],
        faq_match=state["faq_match"],
        handoff_reason=state["handoff_reason"],
    )}


def route_prepared_request(state: WorkflowState):
    if state["action"] == "reply":
        return "verify_reply"
    return END


def verify_reply_node(state: WorkflowState):
    ticket = state["ticket"]
    return {"verification": verify_reply(
        ticket["subject"], ticket["body"], state["faq_text"], state["request"],
    )}


def route_reply_verification(state: WorkflowState):
    if state["verification"].approved:
        return END
    return "handoff"


def handoff_node(state: WorkflowState):
    classification = state["classification"]
    classification.reason += " Reply verification failed; the final action is handoff for human review."
    return {
        "action": "handoff",
        "classification": classification,
        "handoff_reason": state["verification"].reason,
        "request": None,
    }


def build_workflow():
    graph = StateGraph(WorkflowState)
    graph.add_node("classify", classify_node)
    graph.add_node("match_faq", match_faq_node)
    graph.add_node("decide", decide_node)
    graph.add_node("prepare_request", prepare_request_node)
    graph.add_node("verify_reply", verify_reply_node)
    graph.add_node("handoff", handoff_node)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", route_classification)
    graph.add_edge("match_faq", "decide")
    graph.add_edge("decide", "prepare_request")
    graph.add_conditional_edges("prepare_request", route_prepared_request)
    graph.add_conditional_edges("verify_reply", route_reply_verification)
    graph.add_edge("handoff", "prepare_request")
    return graph.compile()
