import json
import os
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from support_agent.api import HelpdeskClient
from support_agent.faq import load_faq
from support_agent.workflow import build_workflow


LABEL_FIELDS = ("language", "category", "priority", "action")


def evaluate_example(example: dict, workflow, faq_text: str) -> dict:
    expected = {field: example["label"][field] for field in LABEL_FIELDS}
    result = {
        "ticket_id": example["id"],
        "expected": expected,
        "reference_reason": example["label"]["reason"],
        "predicted": dict.fromkeys(LABEL_FIELDS),
        "classification_reason": None,
        "matches": dict.fromkeys(LABEL_FIELDS, False),
        "faq_ids": [],
        "faq_fully_supported": None,
        "faq_confidence": None,
        "reply_approved": None,
        "reply_revised": False,
        "verification_reason": None,
        "error": None,
    }

    # Keep reference answers out of the workflow input.
    ticket = example.copy()
    del ticket["label"]

    try:
        state = workflow.invoke({"ticket": ticket, "faq_text": faq_text})
    except Exception:
        result["error"] = "Workflow processing failed; no action was submitted."
        return result

    classification = state["classification"]
    result["reply_revised"] = state["revision_attempted"]
    result["classification_reason"] = classification.reason
    result["predicted"] = {
        "language": classification.language,
        "category": classification.category,
        "priority": classification.priority,
        "action": state["action"],
    }
    for field in LABEL_FIELDS:
        result["matches"][field] = result["predicted"][field] == expected[field]

    faq_match = state["faq_match"]
    if faq_match is not None:
        result["faq_fully_supported"] = faq_match.fully_supported
        result["faq_confidence"] = faq_match.confidence
        for reference in faq_match.matched_faq_ids:
            if reference in faq_text:
                result["faq_ids"].append(reference)

    verification = state["verification"]
    if verification is not None:
        result["reply_approved"] = verification.approved
        result["verification_reason"] = verification.reason

    return result


def summarize_results(results: list[dict]) -> dict:
    total = len(results)
    metrics = {
        "examples": total,
        "accuracy": dict.fromkeys(LABEL_FIELDS, 0),
        "exact_match_accuracy": 0,
        "processing_failures": 0,
        "missed_reference_handoffs": 0,
        "unnecessary_handoffs": 0,
    }

    for result in results:
        for field in LABEL_FIELDS:
            if result["matches"][field]:
                metrics["accuracy"][field] += 1

        if all(result["matches"].values()):
            metrics["exact_match_accuracy"] += 1

        if result["error"] is not None:
            metrics["processing_failures"] += 1

        expected_action = result["expected"]["action"]
        predicted_action = result["predicted"]["action"]
        if expected_action == "handoff" and predicted_action in ("reply", "close"):
            metrics["missed_reference_handoffs"] += 1
        if expected_action == "reply" and predicted_action == "handoff":
            metrics["unnecessary_handoffs"] += 1

    # Convert correct-answer counts into accuracy fractions.
    for field in LABEL_FIELDS:
        metrics["accuracy"][field] /= total
    metrics["exact_match_accuracy"] /= total
    return metrics


def main():
    load_dotenv()
    client = HelpdeskClient()
    try:
        examples = client.get_examples()["examples"]
    finally:
        client.close()

    faq_text = load_faq()
    workflow = build_workflow()
    results = []

    for example in examples:
        result = evaluate_example(example, workflow, faq_text)
        results.append(result)
        matched_fields = sum(result["matches"].values())
        print(f"{example['id']}: {matched_fields}/4 labels matched")

    metrics = summarize_results(results)
    report = {
        "time": datetime.now(UTC).isoformat(),
        "models": {
            "agent": os.environ["OPENAI_AGENT_MODEL"],
            "verifier": os.environ["OPENAI_VERIFIER_MODEL"],
        },
        "reply_confidence_threshold": float(os.environ["REPLY_CONFIDENCE_THRESHOLD"]),
        "metrics": metrics,
        "results": results,
    }

    directory = Path(__file__).resolve().parent.parent / "evaluations"
    directory.mkdir(exist_ok=True)
    filename = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ.json")
    path = directory / filename
    with path.open("x") as report_file:
        json.dump(report, report_file, indent=2)

    print(json.dumps(metrics, indent=2))
    print(f"Evaluation saved to {path}")


if __name__ == "__main__":
    main()
