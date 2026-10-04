"""Workflow extraction service interface and mock implementation."""
import re
import logging
from abc import ABC, abstractmethod
from typing import Tuple, List, Optional
from fastapi import HTTPException, status
from app.core.config import settings
from app.schemas.workflow import (
    WorkflowExtractionContract,
    DecisionItem,
    OpenQuestionItem,
    ExtractedActionItem,
)

logger = logging.getLogger("meetflow.extraction")


class BaseExtractionService(ABC):
    """Abstract base class for workflow extraction services."""

    provider_name: str = "base"

    @abstractmethod
    async def extract_workflow(self, transcript: str) -> Tuple[WorkflowExtractionContract, bool]:
        """
        Extract decisions, actions, and open questions from the provided transcript.

        Returns:
            Tuple of (WorkflowExtractionContract, is_mock)
        """
        pass


def normalize_text_for_search(text: str) -> str:
    """Normalize whitespace and lower for lenient substring search."""
    return re.sub(r'\s+', ' ', text).strip().lower()


def is_evidence_grounded(evidence: str, transcript: str) -> bool:
    """Check whether evidence excerpt exists in transcript."""
    if not evidence or not evidence.strip():
        return False
    if evidence in transcript:
        return True
    norm_ev = normalize_text_for_search(evidence)
    norm_trans = normalize_text_for_search(transcript)
    if norm_ev in norm_trans:
        return True
    stripped_ev = norm_ev.strip('"\'')
    if stripped_ev and stripped_ev in norm_trans:
        return True
    return False


def validate_evidence_in_transcript(contract: WorkflowExtractionContract, transcript: str) -> None:
    """
    Ensure every extracted decision, action, and open question cites verbatim evidence
    grounded in the provided transcript. Raises ValueError on mismatch.
    """
    for dec in contract.decisions:
        if not is_evidence_grounded(dec.evidence, transcript):
            raise ValueError(f"Decision evidence excerpt not found in transcript: '{dec.evidence}'")

    for act in contract.actions:
        if not is_evidence_grounded(act.evidence, transcript):
            raise ValueError(f"Action evidence excerpt not found in transcript: '{act.evidence}'")

    for q in contract.open_questions:
        if not is_evidence_grounded(q.evidence, transcript):
            raise ValueError(f"Open question evidence excerpt not found in transcript: '{q.evidence}'")


class MockExtractionService(BaseExtractionService):
    """
    Deterministic, conservative mock workflow extraction service.
    Analyzes the actual transcript lines passed to it and extracts exact evidence.
    Never invents unstated owners, deadlines, or decisions.
    """

    provider_name: str = "mock"

    async def extract_workflow(self, transcript: str) -> Tuple[WorkflowExtractionContract, bool]:
        """Process transcript lines and extract verifiable workflow items."""
        if not transcript or not transcript.strip():
            return WorkflowExtractionContract(
                summary="Empty meeting transcript with no actionable content.",
                decisions=[],
                actions=[],
                open_questions=[],
            ), True

        lines = [line.strip() for line in transcript.splitlines() if line.strip()]

        decisions: List[DecisionItem] = []
        actions: List[ExtractedActionItem] = []
        open_questions: List[OpenQuestionItem] = []
        speakers = set()

        for line in lines:
            # Skip synthetic banners
            if line.startswith("[SYNTHETIC SAMPLE TRANSCRIPT") or line.startswith("[NOTE:"):
                continue

            # Parse line speaker and body
            # Matches formats like: "[00:01:23] Sarah: text" or "Sarah: text"
            speaker_match = re.search(r'(?:\[\d{2}:\d{2}:\d{2}\]\s*)?([A-Za-z0-9_\-\s]+?):\s*(.+)', line)
            speaker = None
            body = line
            if speaker_match:
                speaker = speaker_match.group(1).strip()
                body = speaker_match.group(2).strip()
                if speaker:
                    speakers.add(speaker)

            # 1. Decision Detection
            decision_match = self._extract_decision(body, line)
            if decision_match:
                decisions.append(decision_match)

            # 2. Action / Task Detection
            action_match = self._extract_action(body, line, speaker)
            if action_match:
                actions.append(action_match)

            # 3. Open Question Detection
            question_match = self._extract_open_question(body, line)
            if question_match:
                open_questions.append(question_match)

        # Generate summary reflecting actual content
        if speakers:
            speaker_str = ", ".join(sorted(speakers))
            summary = f"Meeting discussion involving {speaker_str}. Key agreements and next steps were discussed."
        else:
            summary = "Meeting transcript reviewed with decisions and proposed action items."

        contract = WorkflowExtractionContract(
            summary=summary,
            decisions=decisions,
            actions=actions,
            open_questions=open_questions,
        )

        return contract, True

    def _extract_decision(self, body: str, raw_line: str) -> Optional[DecisionItem]:
        """Detect explicit agreement or decision phrases."""
        # Avoid quoted questions, hypothetical comments, or speculative queries
        if re.search(r'\b(?:wondered|asked|check|doubt|unsure|not\s+sure)\s+(?:if|whether)\b', body, re.IGNORECASE):
            return None
        if re.search(r'(?:asked|said|wondered)\s*["\'].*["\']', body, re.IGNORECASE):
            return None

        decision_patterns = [
            r'(?:we\s+(?:explicitly\s+)?decided\s+to|have\s+decided\s+to)\s+([^.]+)',
            r'(?:we\s+agreed\s+to|team\s+agreed\s+to)\s+([^.]+)',
            r'decision\s*:\s*([^.]+)',
        ]

        for pat in decision_patterns:
            m = re.search(pat, body, re.IGNORECASE)
            if m:
                desc = m.group(1).strip()
                desc = desc[0].upper() + desc[1:] if desc else "Agreed decision."
                return DecisionItem(description=desc, evidence=raw_line)
        return None

    def _extract_action(self, body: str, raw_line: str, current_speaker: Optional[str]) -> Optional[ExtractedActionItem]:
        """Detect actionable commitments, assigned tasks, or requested emails."""
        # Commitment pattern: "I will <do something>"
        i_will_match = re.search(r'\bI\s+will\s+([^.]+)', body, re.IGNORECASE)
        # Direct assignment: "<Name>, please <do something>" or "please <do something>"
        addressed_match = re.search(r'(?:([A-Za-z0-9_\-]+),\s*)?please\s+([^.]+)', body, re.IGNORECASE)
        # Explicit task marker
        task_marker_match = re.search(r'(?:task|action\s*item|action)\s*:\s*([^.]+)', body, re.IGNORECASE)

        action_text = None
        owner = None
        needs_clarification = False

        if i_will_match:
            action_text = i_will_match.group(1).strip()
            owner = current_speaker
        elif addressed_match:
            # Check if a conversational greeting or non-task query like "please give us an update?"
            candidate = addressed_match.group(2).strip()
            if candidate.lower().startswith("give us an update") or candidate.lower().startswith("let's begin"):
                return None
            action_text = candidate
            owner = addressed_match.group(1) or current_speaker
            if not addressed_match.group(1) and not current_speaker:
                owner = None
                needs_clarification = True
        elif task_marker_match:
            action_text = task_marker_match.group(1).strip()
            owner = current_speaker
            if not owner:
                needs_clarification = True
        elif re.search(r'\bsomeone\s+(?:needs\s+to|should|please)\s+([^.]+)', body, re.IGNORECASE):
            m = re.search(r'\bsomeone\s+(?:needs\s+to|should|please)\s+([^.]+)', body, re.IGNORECASE)
            action_text = m.group(1).strip()
            owner = None
            needs_clarification = True

        if not action_text:
            return None

        # Clean description
        action_text = action_text.rstrip(".")
        description = action_text[0].upper() + action_text[1:] if action_text else "Task item."

        # Detect deadline in the line
        deadline_text = self._extract_deadline(body)

        # Detect action type
        action_type = "task"
        draft_subject = None
        draft_body = None
        recipient_email = None

        # Extract explicit email address if present
        email_addr_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', body)
        if email_addr_match:
            recipient_email = email_addr_match.group(0)

        if "email" in action_text.lower():
            action_type = "email"
            draft_subject = "Meeting Summary / Follow-up"
            draft_body = f"Hi,\n\nFollowing up on our meeting discussion regarding: {description}.\n\nBest regards,\nMeetFlow"

        return ExtractedActionItem(
            type=action_type,
            description=description,
            owner=owner,
            deadline_text=deadline_text,
            recipient_email=recipient_email,
            draft_subject=draft_subject,
            draft_body=draft_body,
            evidence=raw_line,
            confidence="high" if owner and not needs_clarification else "medium",
            needs_clarification=needs_clarification or (owner is None),
            approval_status="pending",
        )

    def _extract_deadline(self, text: str) -> Optional[str]:
        """Detect relative spoken deadline text."""
        deadline_patterns = [
            r'\bby\s+(?:Friday|Monday|Tuesday|Wednesday|Thursday|Saturday|Sunday)(?:\s+(?:morning|afternoon|evening|EOD))?\b',
            r'\bnext\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)?\b',
            r'\bby\s+(?:tomorrow|tonight|next\s+week|end\s+of\s+day|EOD)\b',
            r'\bbefore\s+(?:Friday|Monday|Tuesday|Wednesday|Thursday|the\s+weekend|5\s*PM)\b',
        ]
        for pat in deadline_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(0).strip()
        return None

    def _extract_open_question(self, body: str, raw_line: str) -> Optional[OpenQuestionItem]:
        """
        Conservative open question detection.
        Only extracts genuine unresolved topics; excludes conversational queries
        or quoted speech questions.
        """
        # Exclude quoted questions like: She asked "is it done?"
        if re.search(r'(?:asked|said|wondered)\s*["\'].*\?.*["\']', body, re.IGNORECASE):
            return None

        # Exclude procedural / polite questions
        conversational_phrases = [
            r'could\s+you\s+give\s+us\s+an\s+update',
            r'can\s+you\s+hear\s+me',
            r'how\s+are\s+you',
            r'is\s+everyone\s+ready',
            r'do\s+you\s+mind',
            r'shall\s+we\s+begin',
        ]
        for cp in conversational_phrases:
            if re.search(cp, body, re.IGNORECASE):
                return None

        # Genuine unresolved question indicators
        open_question_patterns = [
            r'(?:did\s+we\s+(?:finalize|decide)\s+)(whether\s+[^?]+|if\s+[^?]+)',
            r'([^.]*remains?\s+an\s+open\s+question[^.]*)',
            r'([^.]*still\s+an\s+open\s+question[^.]*)',
            r'([^.]*still\s+unresolved[^.]*)',
            r'([^.]*we\s+still\s+need\s+to\s+decide[^.]*)',
        ]

        for pat in open_question_patterns:
            m = re.search(pat, body, re.IGNORECASE)
            if m:
                q_text = m.group(1).strip()
                if not q_text.endswith("?"):
                    q_text = f"{q_text}?"
                q_text = q_text[0].upper() + q_text[1:] if q_text else "Open question."
                return OpenQuestionItem(question=q_text, evidence=raw_line)

        return None


class GemmaExtractionService(BaseExtractionService):
    """
    Production Gemma workflow extraction provider powered by Google's Gemini API.
    Analyzes meeting transcripts using Google-hosted Gemma models (default: gemma-4-26b-a4b-it).
    Enforces strict grounding, evidence verification, and schema validation.
    """

    provider_name: str = "gemma"

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = (api_key if api_key is not None else getattr(settings, "GEMINI_API_KEY", "")).strip()
        configured_model = (model_name if model_name is not None else getattr(settings, "GEMMA_MODEL", "gemma-4-26b-a4b-it")).strip()
        self.model_name = configured_model if configured_model else "gemma-4-26b-a4b-it"

    async def extract_workflow(self, transcript: str) -> Tuple[WorkflowExtractionContract, bool]:
        """
        Analyze transcript with Gemma model via Gemini API.
        Extracts structured summary, decisions, actions, and open questions.
        Fails fast if unconfigured or on API error; never silently falls back to mock.

        Returns:
            Tuple of (WorkflowExtractionContract, is_mock=False)
        """
        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Gemini API key is not configured. Set GEMINI_API_KEY in the backend environment.",
            )

        if not transcript or not transcript.strip():
            return WorkflowExtractionContract(
                summary="Empty meeting transcript with no actionable content.",
                decisions=[],
                actions=[],
                open_questions=[],
            ), False

        system_instruction = (
            "You are an expert workplace meeting assistant. Your task is to analyze meeting transcripts "
            "and extract structured workflow items strictly based on what was explicitly stated.\n\n"
            "CRITICAL GROUNDING AND SAFETY RULES:\n"
            "1. Use ONLY facts directly stated in the transcript. Do NOT hallucinate, infer, or invent information.\n"
            "2. For every decision, action item, and open question, you MUST provide an exact, verbatim excerpt from the transcript in the 'evidence' field.\n"
            "3. If an action's owner, deadline, or recipient is not explicitly stated or is ambiguous, mark 'needs_clarification': true and leave the unknown field as null.\n"
            "4. Do NOT turn suggestions or thoughts into commitments. Only extract genuine commitments, requested actions, or tasks.\n"
            "5. For tasks, owner must be the person explicitly assigned or committing. If not explicitly assigned, owner is null and needs_clarification is true.\n"
            "6. For emails, recipient_email must be explicitly stated in the transcript. If missing, recipient_email is null and needs_clarification is true.\n"
            "7. For reminders, if deadline is missing, deadline_text is null and needs_clarification is true.\n"
            "8. Never approve or execute actions. All extracted actions MUST have 'approval_status': 'pending'.\n"
            "9. Output strictly valid JSON conforming to the requested schema."
        )

        user_prompt = (
            f"Analyze the following meeting transcript and extract the workflow:\n\n"
            f"--- TRANSCRIPT ---\n{transcript}\n--- END TRANSCRIPT ---\n\n"
            f"Provide a concise summary, all agreed decisions, open/unresolved questions, and actionable tasks, email drafts, or reminders."
        )

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=WorkflowExtractionContract,
            )

            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=config,
            )
        except Exception as exc:
            logger.exception(f"Gemma API request failed: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemma API request failed: {str(exc)}",
            )

        if not response or not response.text:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gemma API returned an empty response.",
            )

        raw_text = response.text.strip()
        # Clean markdown code fences if wrapped
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        try:
            contract = WorkflowExtractionContract.model_validate_json(raw_text)
        except Exception as parse_err:
            logger.warning(f"Gemma response validation error: {parse_err}. Response text: {raw_text[:200]}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemma returned invalid or malformed structured output: {str(parse_err)}",
            )

        # Enforce safety invariants post-validation
        for action in contract.actions:
            # Gemma only proposes actions; never approve or execute
            action.approval_status = "pending"

            # Enforce clarification rules for missing critical fields
            if action.type == "task" and not action.owner:
                action.needs_clarification = True
            elif action.type == "email" and not action.recipient_email:
                action.needs_clarification = True
            elif action.type == "reminder" and not action.deadline_text:
                action.needs_clarification = True

        # Verify evidence grounding in the provided transcript
        try:
            validate_evidence_in_transcript(contract, transcript)
        except ValueError as ground_err:
            logger.warning(f"Gemma evidence grounding validation failed: {ground_err}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemma extraction grounding check failed: {str(ground_err)}",
            )

        return contract, False


def get_extraction_service() -> BaseExtractionService:
    """
    Factory function resolving the configured extraction provider.
    Strictly checks EXTRACTION_PROVIDER and never silently falls back to mock.
    """
    provider = getattr(settings, "EXTRACTION_PROVIDER", "mock").lower()

    if provider == "mock":
        return MockExtractionService()
    elif provider in ("gemma", "gemini", "google"):
        return GemmaExtractionService()

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Extraction provider '{provider}' is not supported.",
    )
