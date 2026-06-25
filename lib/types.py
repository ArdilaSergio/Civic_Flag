from dataclasses import dataclass


NOT_DETECTED = "Not detected"


@dataclass
class DocumentMetadata:
    uploaded_file_name: str
    document_title: str = NOT_DETECTED
    event_or_meeting_date: str = NOT_DETECTED
    jurisdiction: str = NOT_DETECTED
    agency_or_governing_body: str = NOT_DETECTED
    document_type: str = NOT_DETECTED

    def to_dict(self):
        return {
            "uploaded_file_name": self.uploaded_file_name,
            "document_title": self.document_title,
            "event_or_meeting_date": self.event_or_meeting_date,
            "jurisdiction": self.jurisdiction,
            "agency_or_governing_body": self.agency_or_governing_body,
            "document_type": self.document_type,
        }


@dataclass
class DocumentRelevanceResult:
    document_is_policy_related: bool
    document_relevance_explanation: str
    document_warning: str = ""

    def to_dict(self):
        return {
            "document_is_policy_related": self.document_is_policy_related,
            "document_relevance_explanation": self.document_relevance_explanation,
            "document_warning": self.document_warning,
        }


@dataclass
class ParsedDocument:
    text: str
    metadata: DocumentMetadata
