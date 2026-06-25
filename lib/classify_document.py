import re

from .types import DocumentRelevanceResult


WARNING = (
    "Civic Flag is flagging that this upload does not appear to be policy-related. "
    "This tool works best with public agendas, policy documents, staff reports, board packets, "
    "memos, planning documents, and other civic or nonprofit materials."
)


CIVIC_TERMS = [
    "agenda", "board", "council", "commission", "committee", "ordinance", "resolution",
    "staff report", "public hearing", "consent calendar", "grant", "budget", "funding",
    "planning", "zoning", "transportation", "transit", "housing", "public safety",
    "community engagement", "equity", "accessibility", "department", "agency", "nonprofit",
    "program", "policy", "municipal", "county", "district", "state", "residents",
]

NON_POLICY_TERMS = [
    "chapter", "novel", "poem", "personal essay", "resume", "curriculum vitae",
    "creative writing", "my vacation", "dear diary", "short story",
]


def classify_document(text):
    lowered = text.lower()
    civic_hits = sum(1 for term in CIVIC_TERMS if term in lowered)
    structure_hits = len(re.findall(r"\b(item|section|resolution|ordinance|agenda)\s+[a-z0-9.-]+", lowered))
    non_policy_hits = sum(1 for term in NON_POLICY_TERMS if term in lowered)

    is_policy_related = civic_hits + structure_hits >= 3 and civic_hits > non_policy_hits
    if is_policy_related:
        explanation = (
            "The upload appears civic or policy-related because it contains public-sector "
            "terms, agenda/report language, or program and funding references."
        )
        return DocumentRelevanceResult(True, explanation, "")

    explanation = (
        "The upload does not contain enough civic, policy, government, nonprofit, agenda, "
        "program, or public-interest signals to support reliable Civic Flags."
    )
    return DocumentRelevanceResult(False, explanation, WARNING)
