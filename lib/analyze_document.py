import json
import os
import re
import urllib.error
import urllib.request

from .classify_document import WARNING
from .prompt_templates import ANALYSIS_PROMPT_TEMPLATE


ISSUE_KEYWORDS = {
    "lgbtq+ equity": [
        "lgbtq", "gender identity", "sexual orientation", "pride", "inclusive", "hiv",
        "gender-neutral", "hate crime", "discrimination", "civil rights", "mental health",
        "youth", "homeless", "shelter", "community engagement",
    ],
    "housing": ["housing", "tenant", "rent", "affordable", "homeless", "shelter"],
    "public safety": ["public safety", "police", "fire", "emergency", "violence", "safety"],
    "transportation": [
        "transportation", "transit", "bus", "rail", "street", "bike", "pedestrian",
        "fare", "station", "ridership", "service change", "capital project", "mobility",
        "accessibility", "route", "stop", "outreach",
    ],
    "public health": ["public health", "health", "clinic", "behavioral health", "mental health"],
    "budget/funding": ["budget", "funding", "grant", "allocation", "appropriation", "revenue"],
    "accessibility": ["accessibility", "ada", "disability", "accessible", "mobility"],
    "immigrant communities": ["immigrant", "refugee", "language access", "translation", "newcomer"],
    "youth services": ["youth", "student", "after-school", "child", "teen"],
    "senior services": ["senior", "older adult", "aging", "elder"],
    "nonprofit grants": ["nonprofit", "grant", "community-based organization", "cbo"],
    "community engagement": ["community engagement", "public comment", "outreach", "survey", "workshop"],
    "civil rights": ["civil rights", "discrimination", "equity", "rights", "equal access"],
    "environmental justice": ["environmental justice", "pollution", "climate", "emissions", "air quality"],
    "fare policy": ["fare", "passes", "discount", "free rides", "transit fare"],
    "homelessness services": ["homeless", "unsheltered", "shelter", "encampment", "supportive housing"],
}


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
MAX_DOCUMENT_CHARS = 90000
AGENDA_SCOPE_CAVEAT = (
    "Routine meeting procedures, public participation boilerplate, ADA accommodation "
    "logistics, and prior-meeting minutes or summaries were excluded from Civic Flags."
)


def analyze_document(text, metadata, relevance, selected_issues):
    if os.environ.get("OPENAI_API_KEY"):
        return analyze_document_with_ai(text, metadata, relevance, selected_issues)
    return analyze_document_with_keyword_fallback(text, metadata, relevance, selected_issues)


def analyze_document_with_ai(text, metadata, relevance, selected_issues):
    issues = [issue.strip() for issue in selected_issues if issue.strip()]
    if not issues:
        issues = ["General civic relevance"]

    payload = {
        "model": os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        "input": [
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": ANALYSIS_PROMPT_TEMPLATE.strip(),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            {
                                "selected_issues": issues,
                                "issue_context_notes": issue_context_notes(issues),
                                "detected_metadata": metadata.to_dict(),
                                "preliminary_relevance_check": relevance.to_dict(),
                                "instructions": [
                                    "Act as a civic document review agent, not a keyword search tool.",
                                    "Use only the uploaded document text as evidence.",
                                    "Do not invent agenda items, identifiers, dates, page numbers, agencies, or document details.",
                                    "If a value is not present in the document, return 'Not detected'.",
                                    "Identify related policy concepts even when an exact selected issue phrase does not appear.",
                                    "Every Civic Flag must include a supporting source excerpt from the uploaded document.",
                                    "Flag only substantive current agenda items or substantive current document content.",
                                    "Do not flag routine meeting procedures, public comment instructions, ADA accommodation boilerplate, meeting access logistics, roll call, adjournment, or approval of minutes.",
                                    "For agendas and agenda packets, ignore minutes, summaries, recaps, attendance lists, vote records, and action summaries from prior meetings.",
                                    "If the document is not policy-related, set document_is_policy_related to false and return no flagged items.",
                                ],
                                "document_text": text[:MAX_DOCUMENT_CHARS],
                                "document_text_was_truncated": len(text) > MAX_DOCUMENT_CHARS,
                            },
                            ensure_ascii=False,
                        ),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "civic_flag_analysis",
                "strict": True,
                "schema": analysis_schema(),
            }
        },
    }

    data = post_openai_json(payload)
    result = json.loads(extract_response_text(data))
    result["analysis_mode"] = "AI analysis mode"
    result["analysis_mode_explanation"] = "Civic Flag used the AI civic document review function to analyze meaning, context, selected issues, and potential community impact."
    result["metadata"] = normalize_metadata(result.get("metadata"), metadata)
    return apply_agenda_scope_filter(validate_analysis_result(result))


def post_openai_json(payload):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI analysis failed with status {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI analysis failed: {exc.reason}") from exc


def extract_response_text(data):
    if data.get("output_text"):
        return data["output_text"]

    pieces = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                pieces.append(content["text"])
    if pieces:
        return "".join(pieces)
    raise RuntimeError("OpenAI response did not include structured output text.")


def validate_analysis_result(result):
    required_top_level = [
        "analysis_mode",
        "analysis_mode_explanation",
        "document_is_policy_related",
        "document_relevance_explanation",
        "document_warning",
        "metadata",
        "flagged_items",
        "civic_brief",
        "prepared_deliverables",
    ]
    for key in required_top_level:
        if key not in result:
            raise RuntimeError(f"OpenAI response was missing '{key}'.")
    if not isinstance(result["document_is_policy_related"], bool):
        raise RuntimeError("OpenAI response had an invalid document_is_policy_related value.")
    if not isinstance(result["flagged_items"], list):
        raise RuntimeError("OpenAI response had an invalid flagged_items value.")
    return result


def analysis_schema():
    metadata_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "document_title",
            "event_or_meeting_date",
            "jurisdiction",
            "agency_or_governing_body",
            "document_type",
            "uploaded_file_name",
        ],
        "properties": {
            "document_title": {"type": "string"},
            "event_or_meeting_date": {"type": "string"},
            "jurisdiction": {"type": "string"},
            "agency_or_governing_body": {"type": "string"},
            "document_type": {"type": "string"},
            "uploaded_file_name": {"type": "string"},
        },
    }

    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "document_is_policy_related",
            "document_relevance_explanation",
            "document_warning",
            "metadata",
            "flagged_items",
            "civic_brief",
            "prepared_deliverables",
        ],
        "properties": {
            "document_is_policy_related": {"type": "boolean"},
            "document_relevance_explanation": {"type": "string"},
            "document_warning": {"type": "string"},
            "metadata": metadata_schema,
            "flagged_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "title",
                        "item_number_or_identifier",
                        "related_issues",
                        "relevance_summary",
                        "source_excerpt",
                        "community_impact",
                        "urgency_level",
                        "suggested_follow_up",
                        "possible_public_comment_angle",
                        "confidence",
                    ],
                    "properties": {
                        "title": {"type": "string"},
                        "item_number_or_identifier": {"type": "string"},
                        "related_issues": {"type": "array", "items": {"type": "string"}},
                        "relevance_summary": {"type": "string"},
                        "source_excerpt": {"type": "string"},
                        "community_impact": {"type": "string"},
                        "urgency_level": {"type": "string", "enum": ["Low", "Medium", "High"]},
                        "suggested_follow_up": {"type": "array", "items": {"type": "string"}},
                        "possible_public_comment_angle": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["Low", "Medium", "High"]},
                    },
                },
            },
            "civic_brief": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "overall_document_summary",
                    "main_issues_found",
                    "policy_relevance",
                    "top_3_flags_to_review",
                    "recommended_next_action",
                    "suggested_audience_to_notify",
                    "important_caveats",
                ],
                "properties": {
                    "overall_document_summary": {"type": "string"},
                    "main_issues_found": {"type": "array", "items": {"type": "string"}},
                    "policy_relevance": {"type": "string"},
                    "top_3_flags_to_review": {"type": "array", "items": {"type": "string"}},
                    "recommended_next_action": {"type": "string"},
                    "suggested_audience_to_notify": {"type": "string"},
                    "important_caveats": {"type": "string"},
                },
            },
            "prepared_deliverables": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "executive_summary",
                    "priority_review_list",
                    "suggested_follow_up_questions",
                    "possible_public_comment_talking_points",
                    "suggested_outreach_or_notification_list",
                    "notes_for_future_monitoring",
                ],
                "properties": {
                    "executive_summary": {"type": "string"},
                    "priority_review_list": {"type": "array", "items": {"type": "string"}},
                    "suggested_follow_up_questions": {"type": "array", "items": {"type": "string"}},
                    "possible_public_comment_talking_points": {"type": "array", "items": {"type": "string"}},
                    "suggested_outreach_or_notification_list": {"type": "array", "items": {"type": "string"}},
                    "notes_for_future_monitoring": {"type": "string"},
                },
            },
        },
    }


def normalize_metadata(ai_metadata, fallback_metadata):
    fallback = fallback_metadata.to_dict()
    normalized = {}
    for key in [
        "document_title",
        "event_or_meeting_date",
        "jurisdiction",
        "agency_or_governing_body",
        "document_type",
        "uploaded_file_name",
    ]:
        value = (ai_metadata or {}).get(key) if isinstance(ai_metadata, dict) else None
        if not value or not str(value).strip():
            value = fallback.get(key) or "Not detected"
        normalized[key] = str(value).strip()
    normalized["uploaded_file_name"] = fallback["uploaded_file_name"]
    return normalized


def issue_context_notes(issues):
    notes = {}
    for issue in issues:
        key = issue.lower()
        if key in ISSUE_KEYWORDS:
            notes[issue] = ISSUE_KEYWORDS[key]
    return notes


def analyze_document_with_keyword_fallback(text, metadata, relevance, selected_issues):
    issues = [issue.strip() for issue in selected_issues if issue.strip()]
    if not relevance.document_is_policy_related:
        flags = []
        return {
            "analysis_mode": "Fallback keyword mode",
            "analysis_mode_explanation": "No OpenAI API key is configured, so Civic Flag used a limited local keyword fallback. Results may miss related concepts that require AI reasoning.",
            "document_is_policy_related": False,
            "document_relevance_explanation": relevance.document_relevance_explanation,
            "document_warning": relevance.document_warning or WARNING,
            "metadata": metadata.to_dict(),
            "flagged_items": flags,
            "civic_brief": {
                "overall_document_summary": "This upload does not appear to be a civic or policy document.",
                "main_issues_found": [],
                "policy_relevance": "Not policy-related based on the available text.",
                "top_3_flags_to_review": [],
                "recommended_next_action": "Upload a public agenda, staff report, board packet, policy memo, planning document, or similar civic/nonprofit material.",
                "suggested_audience_to_notify": "No audience recommended because no Civic Flags were generated.",
                "important_caveats": "Fallback mode cannot perform full semantic document review and found no reliable civic or policy basis for generating flags.",
            },
            "prepared_deliverables": build_deliverables(flags, [], False),
        }

    chunks = split_into_chunks(text)
    flags = []
    seen = set()
    for chunk in chunks:
        if looks_like_excluded_agenda_material(chunk):
            continue
        related = matching_issues(chunk, issues)
        if not related:
            continue
        if looks_like_header_only(chunk):
            continue
        title = detect_title(chunk, related)
        identifier = detect_identifier(chunk)
        key = (title.lower(), identifier)
        if key in seen:
            continue
        seen.add(key)
        flags.append(build_flag(chunk, title, identifier, related))
        if len(flags) >= 8:
            break

    flags = filter_reportable_flags(flags)
    return {
        "analysis_mode": "Fallback keyword mode",
        "analysis_mode_explanation": "No OpenAI API key is configured, so Civic Flag used a limited local keyword fallback. Results may miss related concepts that require AI reasoning.",
        "document_is_policy_related": True,
        "document_relevance_explanation": relevance.document_relevance_explanation,
        "document_warning": "",
        "metadata": metadata.to_dict(),
        "flagged_items": flags,
        "civic_brief": build_brief(text, flags),
        "prepared_deliverables": build_deliverables(flags, issues, True),
    }


def split_into_chunks(text):
    boundary = re.compile(
        r"\b((?:agenda item|item|section)\s+[A-Z]?\d+[A-Z]?[\w.-]*[:\s-]|"
        r"(?:resolution|ordinance)\s+(?:no\.?\s*)?[A-Z]?\d{2,}[\w.-]*|"
        r"meeting procedures?|public comment|approval of minutes|approve (?:the )?minutes|"
        r"call to order|roll call|adjournment)\b",
        re.IGNORECASE,
    )
    prepared_text = boundary.sub(r"\n\1", text)
    lines = [line.strip() for line in prepared_text.splitlines() if line.strip()]
    chunks = []
    current = []
    item_start = re.compile(
        r"^(item|section|agenda item|resolution|ordinance)\s+[a-z0-9.-]+|"
        r"^(meeting procedures?|public comment|approval of minutes|approve (?:the )?minutes|"
        r"call to order|roll call|adjournment)\b",
        re.IGNORECASE,
    )
    for line in lines:
        if current and (item_start.search(line) or len(" ".join(current)) > 900):
            chunks.append(" ".join(current))
            current = []
        current.append(line)
    if current:
        chunks.append(" ".join(current))
    if len(chunks) == 1:
        chunks = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [chunk.strip() for chunk in chunks if len(chunk.strip()) > 60]


def matching_issues(chunk, selected_issues):
    lowered = chunk.lower()
    related = []
    for issue in selected_issues:
        keywords = ISSUE_KEYWORDS.get(issue.lower(), [issue.lower()])
        if any(keyword in lowered for keyword in keywords):
            related.append(issue)
    return related


def detect_identifier(chunk):
    patterns = [
        r"\b(?:agenda item|item|section)\s+([A-Z]?\d+[A-Z]?[\w.-]*)",
        r"\b(?:resolution|ordinance)\s+(?:no\.?\s*)?([A-Z]?\d{2,}[\w.-]*)",
        r"\bpage\s+(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, chunk, flags=re.IGNORECASE)
        if match:
            label = match.group(0)
            return re.sub(r"\s+", " ", label).strip()
    return "Not detected"


def detect_title(chunk, related):
    item_title = re.search(
        r"^(?:agenda item|item|section)\s+[A-Z0-9.-]+:\s*(.+?)(?:\s+(?:Receive|Consider|Approve|Adopt|Authorize|The|Staff)\b|$)",
        chunk.strip(),
        flags=re.IGNORECASE,
    )
    if item_title:
        title = item_title.group(1).strip(" .:-")
        if 6 <= len(title) <= 90:
            return title
    first_sentence = re.split(r"(?<=[.!?])\s+", chunk.strip())[0]
    first_sentence = re.sub(r"^(item|section|agenda item)\s+[A-Z0-9.-]+[:\s-]*", "", first_sentence, flags=re.IGNORECASE)
    if 12 <= len(first_sentence) <= 90:
        return first_sentence
    return f"{related[0]} item for review"


def looks_like_header_only(chunk):
    lowered = chunk.lower()
    has_identifier = detect_identifier(chunk) != "Not detected"
    action_terms = ["approve", "adopt", "consider", "receive", "authorize", "report", "grant", "hearing"]
    if has_identifier:
        return False
    return len(chunk) < 160 and not any(term in lowered for term in action_terms)


def apply_agenda_scope_filter(result):
    flags = result.get("flagged_items") or []
    filtered_flags = filter_reportable_flags(flags)
    removed_count = len(flags) - len(filtered_flags)
    result["flagged_items"] = filtered_flags
    if removed_count:
        result["analysis_mode_explanation"] = append_sentence(
            result.get("analysis_mode_explanation", ""),
            AGENDA_SCOPE_CAVEAT,
        )
        result["civic_brief"] = refresh_brief_after_scope_filter(
            result.get("civic_brief"),
            filtered_flags,
            removed_count,
        )
        result["prepared_deliverables"] = refresh_deliverables_after_scope_filter(
            result.get("prepared_deliverables"),
            filtered_flags,
            removed_count,
        )
    return result


def filter_reportable_flags(flags):
    return [flag for flag in flags if not flag_looks_excluded(flag)]


def flag_looks_excluded(flag):
    if not isinstance(flag, dict):
        return False
    fields = [
        flag.get("title", ""),
        flag.get("item_number_or_identifier", ""),
        flag.get("relevance_summary", ""),
        flag.get("source_excerpt", ""),
        flag.get("community_impact", ""),
        " ".join(flag.get("suggested_follow_up", []) or []),
        flag.get("possible_public_comment_angle", ""),
    ]
    return looks_like_excluded_agenda_material(" | ".join(str(field) for field in fields if field))


def looks_like_excluded_agenda_material(text):
    lowered = normalize_scope_text(text)
    if not lowered:
        return False

    if re.search(r"\b(meeting procedures?|procedural instructions?|meeting logistics|public participation instructions?)\b", lowered):
        return True

    if re.search(r"\b(call to order|roll call|pledge of allegiance|invocation|approval of (?:the )?agenda|adjournment)\b", lowered):
        return True

    if re.search(r"\b(approval of minutes|approve (?:the )?minutes|minutes of (?:the )?(?:regular|special|adjourned)? ?meeting|previous meeting minutes|prior meeting minutes)\b", lowered):
        return True

    if "minutes" in lowered and re.search(r"\b(prior meeting|previous meeting|regular meeting held|special meeting held|meeting was called to order|motion carried|motion passed|seconded by|members present|members absent)\b", lowered):
        return True

    public_comment_logistics = (
        "public comment" in lowered
        and re.search(r"\b(submit|email|mail|speaker card|comment card|clerk|city clerk|deadline|livestream|zoom|telephone|speak at|speaking time|meeting access)\b", lowered)
    )
    if public_comment_logistics and not has_substantive_policy_context(lowered):
        return True

    ada_logistics = (
        re.search(r"\b(americans with disabilities act|reasonable modification|reasonable accommodation|ada accommodation|disability accommodation)\b", lowered)
        and re.search(r"\b(clerk|city clerk|request|contact|meeting|agenda|hours|days|email|phone|telephone|assistive listening)\b", lowered)
    )
    if ada_logistics and not has_substantive_policy_context(lowered):
        return True

    return False


def has_substantive_policy_context(lowered_text):
    return bool(
        re.search(
            r"\b(ordinance|resolution|contract|grant|funding|budget|capital project|staff report|"
            r"policy change|policy update|implementation|program|services|housing|transit|"
            r"transportation|public safety|fare|accessibility improvements|transition plan)\b",
            lowered_text,
        )
    )


def normalize_scope_text(text):
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def refresh_brief_after_scope_filter(brief, flags, removed_count):
    brief = brief.copy() if isinstance(brief, dict) else {}
    titles = [flag.get("title", "Not detected") for flag in flags[:3]]
    issues = sorted({issue for flag in flags for issue in flag.get("related_issues", [])})

    brief.setdefault("overall_document_summary", "No summary available from extracted text.")
    brief["main_issues_found"] = issues
    brief["top_3_flags_to_review"] = titles
    if not flags:
        brief["policy_relevance"] = (
            "The document appears policy-related, but no substantive current agenda items "
            "strongly matched the selected issues after excluding procedural and prior-meeting material."
        )
        brief["recommended_next_action"] = (
            "Review the current substantive agenda items or staff reports directly, or try broader issues of interest."
        )
        brief["suggested_audience_to_notify"] = "No specific audience identified from the selected issues."
    brief["important_caveats"] = append_sentence(
        brief.get("important_caveats", ""),
        f"{AGENDA_SCOPE_CAVEAT} {removed_count} non-substantive or prior-meeting item(s) were removed from the report.",
    )
    return brief


def refresh_deliverables_after_scope_filter(deliverables, flags, removed_count):
    deliverables = deliverables.copy() if isinstance(deliverables, dict) else {}
    if not flags:
        deliverables["executive_summary"] = (
            "No substantive current agenda items were flagged for the selected issues after excluding "
            "meeting procedures and prior-meeting materials."
        )
        deliverables["priority_review_list"] = []
        deliverables["suggested_follow_up_questions"] = []
        deliverables["possible_public_comment_talking_points"] = []
        deliverables["suggested_outreach_or_notification_list"] = []
    else:
        deliverables["priority_review_list"] = [
            f"{flag.get('urgency_level', 'Medium')} priority: {flag.get('title', 'Not detected')} ({flag.get('item_number_or_identifier', 'Not detected')})"
            for flag in flags[:5]
        ]
        deliverables["suggested_follow_up_questions"] = filter_excluded_strings(
            deliverables.get("suggested_follow_up_questions", [])
        ) or [
            f"What decision, deadline, implementation step, or community impact is tied to {flag.get('title', 'this item')}?"
            for flag in flags[:3]
        ]
        deliverables["possible_public_comment_talking_points"] = [
            flag.get("possible_public_comment_angle", "")
            for flag in flags
            if flag.get("possible_public_comment_angle")
        ][:4]
        deliverables["suggested_outreach_or_notification_list"] = filter_excluded_strings(
            deliverables.get("suggested_outreach_or_notification_list", [])
        )

    deliverables.setdefault("executive_summary", "A scoped review packet was prepared from the substantive current document content.")
    deliverables.setdefault("priority_review_list", [])
    deliverables.setdefault("suggested_follow_up_questions", [])
    deliverables.setdefault("possible_public_comment_talking_points", [])
    deliverables.setdefault("suggested_outreach_or_notification_list", [])
    deliverables["notes_for_future_monitoring"] = append_sentence(
        deliverables.get("notes_for_future_monitoring", ""),
        f"{AGENDA_SCOPE_CAVEAT} {removed_count} non-substantive or prior-meeting item(s) were removed.",
    )
    return deliverables


def filter_excluded_strings(values):
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if value and not looks_like_excluded_agenda_material(value)]


def append_sentence(existing, sentence):
    existing = str(existing or "").strip()
    sentence = str(sentence or "").strip()
    if not sentence or sentence in existing:
        return existing
    if not existing:
        return sentence
    separator = "" if existing.endswith((".", "!", "?")) else "."
    return f"{existing}{separator} {sentence}"


def build_flag(chunk, title, identifier, related):
    urgency = urgency_for(chunk)
    confidence = "High" if len(related) > 1 or identifier != "Not detected" else "Medium"
    excerpt = chunk[:420].strip()
    if len(chunk) > 420:
        excerpt += "..."
    return {
        "title": title,
        "item_number_or_identifier": identifier,
        "related_issues": related,
        "relevance_summary": f"This section appears relevant to {', '.join(related)} based on terms and context in the uploaded document.",
        "source_excerpt": excerpt,
        "community_impact": community_impact_for(related),
        "urgency_level": urgency,
        "suggested_follow_up": suggested_follow_up_for(related, urgency),
        "possible_public_comment_angle": public_comment_for(related),
        "confidence": confidence,
    }


def urgency_for(chunk):
    lowered = chunk.lower()
    if any(term in lowered for term in ["vote", "adopt", "approve", "deadline", "hearing", "allocation"]):
        return "High"
    if any(term in lowered for term in ["review", "update", "receive", "report"]):
        return "Medium"
    return "Low"


def community_impact_for(issues):
    lowered = " ".join(issues).lower()
    if any(term in lowered for term in ["housing", "homelessness", "accessibility", "immigrant", "lgbtq", "civil rights", "environmental justice"]):
        return "This item may affect access, equity, or service conditions for underserved or marginalized communities."
    if any(term in lowered for term in ["budget", "funding", "nonprofit"]):
        return "This item may shape which programs receive resources and which community partners can provide services."
    return "This item may affect community services, resident experience, or public agency priorities."


def suggested_follow_up_for(issues, urgency):
    base = ["Review the full staff report or attachment", "Track the item for the meeting record"]
    if urgency == "High":
        base.insert(1, "Prepare public comment or briefing notes")
    if any("community" in issue.lower() for issue in issues):
        base.append("Notify community partners or affected residents")
    return base


def public_comment_for(issues):
    if not issues:
        return ""
    return f"Ask how the agency will evaluate impacts related to {', '.join(issues)} and how affected communities can participate before final action."


def build_brief(text, flags):
    summary = summarize_text(text)
    top_flags = [flag["title"] for flag in flags[:3]]
    main_issues = sorted({issue for flag in flags for issue in flag["related_issues"]})
    if not flags:
        return {
            "overall_document_summary": summary,
            "main_issues_found": [],
            "policy_relevance": "The document appears policy-related, but no strong matches were found for the selected issues.",
            "top_3_flags_to_review": [],
            "recommended_next_action": "Try adding broader issues of interest or reviewing the document manually for context.",
            "suggested_audience_to_notify": "No specific audience identified from the selected issues.",
            "important_caveats": "Fallback keyword mode may miss policy relevance based on meaning, context, or related concepts.",
        }
    return {
        "overall_document_summary": summary,
        "main_issues_found": main_issues,
        "policy_relevance": "The document appears policy-related and contains sections that match the selected issues.",
        "top_3_flags_to_review": top_flags,
        "recommended_next_action": "Review the top flags, open the source document for full context, and decide whether partners or agency staff should be notified.",
        "suggested_audience_to_notify": "Community advocates, nonprofit partners, agency staff, board members, or affected residents depending on the flagged issue.",
        "important_caveats": "This review was produced in fallback keyword mode because no OpenAI API key is configured. It may miss semantically related items.",
    }


def build_deliverables(flags, issues, is_policy_related):
    if not is_policy_related:
        return {
            "executive_summary": "No review packet was prepared because this upload does not appear to be a policy, civic, government, or nonprofit/public-interest document.",
            "priority_review_list": [],
            "suggested_follow_up_questions": [
                "Can a public agenda, staff report, board packet, policy memo, planning document, or nonprofit program document be uploaded instead?"
            ],
            "possible_public_comment_talking_points": [],
            "suggested_outreach_or_notification_list": [],
            "notes_for_future_monitoring": "Upload a more relevant civic or policy document before setting monitoring priorities.",
        }

    if not flags:
        return {
            "executive_summary": "The document appears civic or policy-related, but fallback mode did not find strong issue matches.",
            "priority_review_list": [],
            "suggested_follow_up_questions": [
                "Are there broader issue terms that should be selected?",
                "Should the document be reviewed with AI analysis mode for semantic connections?"
            ],
            "possible_public_comment_talking_points": [],
            "suggested_outreach_or_notification_list": [],
            "notes_for_future_monitoring": "Track this document manually or rerun with AI analysis mode before deciding no action is needed.",
        }

    return {
        "executive_summary": f"Fallback mode found {len(flags)} potential Civic Flag item(s) related to {', '.join(issues) or 'the selected issues'}. Review the source excerpts before taking action.",
        "priority_review_list": [
            f"{flag['urgency_level']} priority: {flag['title']} ({flag['item_number_or_identifier']})"
            for flag in flags[:5]
        ],
        "suggested_follow_up_questions": [
            f"What decision, vote, deadline, or implementation step is tied to {flag['title']}?"
            for flag in flags[:3]
        ],
        "possible_public_comment_talking_points": [
            flag["possible_public_comment_angle"]
            for flag in flags
            if flag.get("possible_public_comment_angle")
        ][:4],
        "suggested_outreach_or_notification_list": [
            "Nonprofit partners",
            "Community advocates",
            "Agency staff",
            "Board members or decision-makers",
            "Affected residents or service users",
        ],
        "notes_for_future_monitoring": "Because this is fallback keyword mode, rerun with AI analysis mode when possible and track future agendas for related items, staff reports, votes, deadlines, or implementation updates.",
    }


def summarize_text(text):
    clean = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    summary = " ".join(sentences[:2]).strip()
    if len(summary) > 420:
        summary = summary[:417].rsplit(" ", 1)[0] + "..."
    return summary or "No summary available from extracted text."
