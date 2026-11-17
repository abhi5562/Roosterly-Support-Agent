import os

from support_agent.models import Action, Classification, FAQMatch


def decide_action(
    classification: Classification,
    faq_match: FAQMatch | None = None,
) -> Action:
    if classification.proposed_action != "reply":
        return classification.proposed_action

    if faq_match is None or not faq_match.fully_supported or not faq_match.matched_faq_ids:
        classification.reason += " The final action is handoff because full FAQ support has not been established."
        return "handoff"

    threshold = float(os.environ["REPLY_CONFIDENCE_THRESHOLD"])
    if not 0 <= threshold <= 1:
        raise ValueError("REPLY_CONFIDENCE_THRESHOLD must be between 0 and 1.")

    if faq_match.confidence >= threshold:
        return "reply"

    classification.reason += " The final action is handoff because FAQ confidence is below the required threshold."
    return "handoff"
