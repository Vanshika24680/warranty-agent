import json
import os
import re

MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

ALLOWED_ACTIONS = {
    "check_warranty",
    "troubleshoot_issue",
    "find_service_center",
    "create_support_ticket",
    "analyse_claim_history",
}

SYSTEM_PROMPT = """
You are a planning agent in an intelligent warranty and
after-sales support system.

Analyse the customer's problem and decide which actions
the support system should perform.

Available actions:
1. check_warranty
2. troubleshoot_issue
3. find_service_center
4. create_support_ticket
5. analyse_claim_history

Return ONLY a valid JSON object containing:
- product
- issue
- priority (Low, Medium, High)
- planned_actions (list of action names)

Use only the available action names.
Do not claim that any action has already been executed.
"""


def _get_api_key():
    """Read the Groq key from the environment or Streamlit secrets."""
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("GROQ_API_KEY")
    except Exception:
        return None


def _llm_plan(customer_issue):
    """Ask the hosted LLM for a JSON plan. Raises on any failure."""
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    from groq import Groq  # imported lazily so the app still loads without it

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": customer_issue},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


def _fallback_plan(customer_issue, reason):
    """Deterministic plan used when the LLM is unavailable or returns junk."""
    text = re.sub(r"\s+", " ", str(customer_issue)).strip()
    return {
        "product": "Unknown",
        "issue": text,
        "priority": "Medium",
        "planned_actions": ["check_warranty", "troubleshoot_issue"],
        "planner": "RULE_BASED_FALLBACK",
        "fallback_reason": reason,
    }


def create_plan(customer_issue):
    reason = None

    try:
        plan = _llm_plan(customer_issue)
        if not isinstance(plan, dict):
            raise ValueError("Planner did not return a JSON object")
        planner = f"LLM:{MODEL}"
    except Exception as error:
        reason = f"{type(error).__name__}: {error}"
        plan = _fallback_plan(customer_issue, reason)
        planner = plan["planner"]

    actions = plan.get("planned_actions", [])
    if not isinstance(actions, list):
        actions = []

    plan["planned_actions"] = [
        action for action in actions
        if isinstance(action, str) and action in ALLOWED_ACTIONS
    ]

    # An LLM plan with no usable actions is treated as a failed plan.
    if not plan["planned_actions"]:
        reason = reason or "Planner returned no valid actions"
        plan = _fallback_plan(customer_issue, reason)
        planner = plan["planner"]

    plan["planner"] = planner
    plan["source_issue"] = customer_issue  # lets the workflow detect a new complaint
    return plan


if __name__ == "__main__":
    complaint = (
        "My HP Pavilion laptop is overheating. "
        "I purchased it 8 months ago and live in "
        "Vijay Nagar, Indore."
    )

    print("\n===== AI AGENT PLAN =====")
    print(json.dumps(create_plan(complaint), indent=4))
