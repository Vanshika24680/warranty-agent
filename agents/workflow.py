
from tools.ticket_tool import create_support_ticket
import json
import sys
from agents.research_agent import research_and_troubleshoot
from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from tools.customer_warranty_tool import assess_customer_warranty

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.planning_agent import create_plan
from tools.warranty_tool import (
    check_warranty,
    check_warranty_by_id
)



class WarrantyState(TypedDict, total=False):
    # Customer request
    customer_issue: str
    customer_name: str
    brand: str
    product_id: int
    purchase_date: str
    warranty_months: int

    # Agent outputs
    plan: dict
    warranty_result: dict
    research_result: dict
    ticket_result: dict

    # Customer approval
    create_ticket_requested: bool

    # Workflow control and observability
    next_action: str
    execution_trace: list[str]
    research_attempts: int
    research_status: str



def planning_node(state: WarrantyState):
    issue = state["customer_issue"]
    existing = state.get("plan")

    # Preserve the plan only when resuming the SAME complaint
    # (e.g. continuing with a product ID). A new complaint in the
    # same session must be planned again.
    if existing and existing.get("source_issue") == issue:
        return {}

    plan = create_plan(issue)

    trace = state.get("execution_trace", []) + [
        f"Planning agent analysed the customer complaint ({plan.get('planner')})."
    ]

    if plan.get("fallback_reason"):
        trace.append(
            "Self-correction: LLM planner unavailable, rule-based plan used "
            f"({plan['fallback_reason']})."
        )

    return {
        "plan": plan,
        "execution_trace": trace
    }




def warranty_node(state: WarrantyState):
    """Calculate estimated warranty coverage from customer inputs."""

    result = assess_customer_warranty(
        purchase_date=state.get("purchase_date"),
        warranty_months=state.get("warranty_months")
    )

    return {
        "warranty_result": result,
        "execution_trace": state.get("execution_trace", []) + [
            f"Warranty assessment executed: {result['status']}"
        ]
    }




def validation_node(state: WarrantyState):
    """Validate warranty inputs and research evidence."""

    result = state.get("warranty_result") or {}
    status = result.get("status", "UNKNOWN")

    research = state.get("research_result") or {}
    research_status = research.get("status", "NOT_REQUESTED")

    trace = list(state.get("execution_trace", []))

    if status == "NEEDS_PURCHASE_DETAILS":
        action = "REQUEST_PURCHASE_DETAILS"

    elif status == "INVALID_INPUT":
        action = "CORRECT_PURCHASE_DETAILS"

    else:
        action = "COMPLETE"

    trace.append(f"Warranty validation completed: {action}")

    if research_status == "INSUFFICIENT_EVIDENCE":
        trace.append(
            "Evidence validation failed: insufficient manufacturer evidence."
        )
        trace.append(
            "Self-correction: unsupported troubleshooting steps must not be shown."
        )

    elif research_status in {
        "RESEARCH_FAILED",
        "SEARCH_FAILED",
        "AI_FAILED",
        "NO_RESULTS"
    }:
        trace.append(
            f"Research could not be verified: {research_status}."
        )
        trace.append(
            "Fallback: customer directed to official manufacturer support."
        )

    elif research_status == "SUCCESS":
        trace.append(
            "Research validation completed. Review evidence confidence before presenting steps."
        )

    return {
        "next_action": action,
        "execution_trace": trace
    }


def route_after_validation(state: WarrantyState):
    if state["next_action"] == "COMPLETE":
        return "complete"
    return "needs_input"


def needs_input_node(state: WarrantyState):
    return {
        "execution_trace": state["execution_trace"] + [
            "Workflow paused logically: customer input required."
        ]
    }


def research_node(state: WarrantyState):
    """Research the issue with one controlled retry and trace recovery."""

    plan = state.get("plan") or {}
    actions = plan.get("planned_actions", [])
    trace = list(state.get("execution_trace", []))

    if "troubleshoot_issue" not in actions:
        return {
            "research_result": {"status": "NOT_REQUESTED"},
            "research_status": "NOT_REQUESTED",
            "execution_trace": trace + [
                "Research agent skipped: troubleshooting not requested."
            ]
        }

    brand = state.get("brand", "").strip()
    product = plan.get("product", "")
    issue = plan.get("issue", "")

    if not brand:
        return {
            "research_result": {
                "status": "NEEDS_BRAND",
                "message": "Please provide the product brand."
            },
            "research_status": "NEEDS_BRAND",
            "execution_trace": trace + [
                "Research agent stopped: product brand is missing."
            ]
        }

    result = None
    retryable_statuses = {
        "RESEARCH_FAILED",
        "SEARCH_FAILED",
        "AI_FAILED",
        "NO_RESULTS"
    }

    for attempt in range(1, 3):
        trace.append(
            f"Research attempt {attempt}/2 started."
        )

        try:
            result = research_and_troubleshoot(
                brand=brand,
                product=product,
                issue=issue
            )

            if not isinstance(result, dict):
                raise ValueError("Research agent returned invalid output.")

            status = result.get("status", "UNKNOWN")

            trace.append(
                f"Research attempt {attempt} returned: {status}"
            )

            trace.extend(result.get("execution_trace", []))

            if status not in retryable_statuses:
                break

            if attempt == 1:
                trace.append(
                    "Self-correction: retrying after research failure."
                )

        except Exception as error:
            trace.append(
                f"Research attempt {attempt} failed: {str(error)}"
            )

            result = {
                "status": "RESEARCH_FAILED",
                "message": str(error),
                "recommendation": (
                    "Research could not be completed. "
                    "Please consult official manufacturer support."
                )
            }

            if attempt == 1:
                trace.append(
                    "Self-correction: retrying after tool exception."
                )

    if result is None:
        result = {"status": "RESEARCH_FAILED"}

    return {
        "research_result": result,
        "research_status": result.get("status", "UNKNOWN"),
        "research_attempts": attempt,
        "execution_trace": trace
    }

def ticket_node(state: WarrantyState):
    """Create an internal ticket only with customer approval."""
    trace = list(state.get("execution_trace", []))

    existing = state.get("ticket_result") or {}

    if existing.get("status") == "SUCCESS":
        return {
            "execution_trace": trace + [
                "Existing ticket reused; duplicate creation skipped."
            ]
        }

    if not state.get("create_ticket_requested", False):
        return {
            "ticket_result": {"status": "NOT_REQUESTED"}
        }

    plan = state.get("plan") or {}
    customer = state.get("customer_name", "").strip()
    brand = state.get("brand", "").strip()
    product = plan.get("product", "")
    issue = plan.get("issue", "")

    if not all([customer, brand, product, issue]):
        result = {
            "status": "NEEDS_CUSTOMER_DETAILS",
            "message": "Customer name, brand, product and issue are required."
        }
    else:
        result = create_support_ticket(
            customer_name=customer,
            brand=brand,
            product=product,
            issue=issue
        )

    return {
        "ticket_result": result,
        "execution_trace": trace + [
            f"Ticket handling completed: {result['status']}"
        ]
    }


builder = StateGraph(WarrantyState)

builder.add_node("planning", planning_node)
builder.add_node("warranty", warranty_node)
builder.add_node("research", research_node)
builder.add_node("validation", validation_node)
builder.add_node("needs_input", needs_input_node)
builder.add_node("ticket", ticket_node)

builder.add_edge(START, "planning")
builder.add_edge("planning", "warranty")
builder.add_edge("warranty", "research")
builder.add_edge("research", "validation")


builder.add_conditional_edges(
    "validation",
    route_after_validation,
    {
        "complete": "ticket",
        "needs_input": "needs_input"
    }
)

builder.add_edge("needs_input", END)
builder.add_edge("ticket", END)

checkpointer = InMemorySaver()

warranty_workflow = builder.compile(
    checkpointer=checkpointer
)



if __name__ == "__main__":
    config = {
        "configurable": {
            "thread_id": "warranty_case_001"
        }
    }

    complaint = (
        "My HP Pavilion laptop is overheating. "
        "I purchased it 8 months ago."
    )

    # First run
    first_result = warranty_workflow.invoke(
        {
            "customer_issue": complaint,
            "execution_trace": []
        },
        config=config
    )

    print("\n===== FIRST RUN =====")
    print("Next action:", first_result["next_action"])

    # Retrieve saved workflow state
    saved_state = warranty_workflow.get_state(config)

    print("\n===== SAVED STATE =====")
    print("Saved plan:", saved_state.values["plan"])

    # Continue the same case using the saved state
    second_result = warranty_workflow.invoke(
        {"product_id": 15},
        config=config
    )

    print("\n===== SECOND RUN =====")
    print("Warranty status:", second_result["warranty_result"]["status"])
    print("Next action:", second_result["next_action"])

    print("\n===== EXECUTION TRACE =====")
    for event in second_result["execution_trace"]:
        print("-", event)

        print("\n===== RESEARCH AGENT RESULT =====")
    import json

    print(
        json.dumps(
            second_result.get("research_result", {}),
            indent=2,
            ensure_ascii=False
        )
    )