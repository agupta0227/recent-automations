import json
import re
from pathlib import Path
from typing import List, Dict
from datetime import datetime


class TicketGeneratorImproved:
    def __init__(self, output_dir: str):
        self.output_dir     = output_dir
        self.tickets        = []
        self.ticket_counter = 1

    # ── Language-independent "is this a real issue sentence?" ─────────
    #
    # Strategy: validate the SHAPE of the text, not its content.
    # A real issue is written in plain English prose.
    # A code line performs an action in a specific syntax.
    #
    # These rules hold regardless of language (Python, VB, JS, Java...):

    # 1. Minimum length — anything under 35 chars is too short to be
    #    a meaningful issue description.
    MIN_LENGTH = 35

    # 2. Code-start characters — lines that begin with these are almost
    #    certainly code, not English prose. Language-agnostic because
    #    ALL programming languages use these at line-start for statements.
    CODE_START_CHARS = set('{}[]()<>@#/\\|`~;')

    # 3. Code-start WORDS/PATTERNS — keywords or patterns that appear at
    #    the start of a code line across virtually all languages.
    #    Note: we deliberately do NOT include any language name here.
    CODE_START_PATTERNS = re.compile(
        r'^('
        # function/method calls  e.g.  print(  console.log(  MessageBox.Show(
        r'[\w.]+\s*\('
        # assignment operators   e.g.  x =  x :=  x +=  x =>
        r'|[\w\s]+(=|:=|\+=|-=|\*=|/=|=>)'
        # common statement starters that are never English sentences
        r'|return\s|throw\s|raise\s|yield\s|await\s|assert\s'
        r'|pass$|break$|continue$|else:|elif\s|except\s|finally:'
        # comment markers that slipped through
        r"|^'{1,2}\s|^//|^/\*|^--\s|^<!-"
        # markdown section headers that are not issues
        r'|^#{1,6}\s|^\*{1,2}(Major|Minor|Critical|Trivial|Issues|Summary'
        r'|Improvements|Fixed|Note|Recommendation)\*{0,2}:?\s*$'
        # bare punctuation lines
        r'|^[-=*_]{3,}$'
        r')',
        re.IGNORECASE
    )

    # 4. Must contain PROSE INDICATORS — a real issue sentence will have
    #    at least one of these patterns (space between words, common
    #    English connectors). This filters out bare symbol lines.
    PROSE_PATTERN = re.compile(r'\b(the|a|an|is|are|was|were|should|must|'
                               r'does|do|not|no|needs?|lacks?|missing|'
                               r'consider|ensure|implement|add|fix|handle|'
                               r'improve|check|validate|use|avoid|replace|'
                               r'provide|include|make|have|this|that)\b',
                               re.IGNORECASE)

    # 5. Issue-relevance keywords — the line must relate to a problem or
    #    improvement. Language-agnostic English words only.
    ISSUE_KEYWORDS = re.compile(
        r'\b(error|bug|issue|missing|broken|fail|crash|exception|invalid|'
        r'incorrect|improper|incomplete|undefined|unhandled|leak|race|'
        r'vulnerabilit|security|performance|slow|memory|null|none|empty|'
        r'wrong|bad|poor|weak|lack|no\s+\w+|not\s+\w+|should|must|needs?|'
        r'consider|improve|refactor|simplif|clarif|document|comment|'
        r'readabilit|maintainabilit|duplicat|redundan|unused|deprecated|'
        r'hardcod|magic\s+number|todo|fixme|hack|workaround)\b',
        re.IGNORECASE
    )

    # 6. Markdown section headers we always skip
    SKIP_EXACT = {
        '**issues found:**', '**summary:**', '**improvements suggested:**',
        '**fixed code (if needed):**', '**fixed code:**', '**overall:**',
        '**note:**', '**recommendations:**', 'not required.',
        '---', '===', '```'
    }

    def extract_issues_from_review(self, feedback: str, iteration: int) -> List[Dict]:
        """
        Extract genuine issue descriptions from LLM review feedback.
        Uses language-independent heuristics — validates TEXT SHAPE, not code syntax.
        """
        new_tickets = []
        lines = feedback.split('\n')

        for line in lines:
            stripped = line.strip()

            # ── Gate 1: skip empty / exact-match headers ──────────────
            if not stripped:
                continue
            if stripped.lower() in self.SKIP_EXACT:
                continue

            # Strip leading list markers:  "- ", "* ", "1. ", "  - "
            cleaned = re.sub(r'^[\s\-\*\d\.]+', '', stripped).strip()

            # ── Gate 2: minimum length ─────────────────────────────────
            if len(cleaned) < self.MIN_LENGTH:
                continue

            # ── Gate 3: does not START with a code character ──────────
            if cleaned and cleaned[0] in self.CODE_START_CHARS:
                continue

            # ── Gate 4: does not match code-start patterns ────────────
            if self.CODE_START_PATTERNS.match(cleaned):
                continue

            # ── Gate 5: must contain prose indicators ─────────────────
            if not self.PROSE_PATTERN.search(cleaned):
                continue

            # ── Gate 6: must be relevant to an issue / improvement ────
            if not self.ISSUE_KEYWORDS.search(cleaned):
                continue

            # ── Gate 7: deduplicate — skip if very similar to a recent ticket
            if self._is_duplicate(cleaned):
                continue

            severity = self._determine_severity(cleaned)

            ticket = {
                'key':        f'SDLC-{self.ticket_counter}',
                'summary':    cleaned[:120],
                'description': cleaned,
                'severity':   severity,
                'iteration':  iteration,
                'timestamp':  datetime.now().isoformat()
            }

            new_tickets.append(ticket)
            self.tickets.append(ticket)
            self.ticket_counter += 1

        return new_tickets

    def _is_duplicate(self, text: str) -> bool:
        """
        Return True if this text is substantially similar to an already-captured ticket.
        Uses a simple word-overlap ratio — no NLP library needed.
        """
        words_new = set(re.findall(r'\b\w{4,}\b', text.lower()))
        if not words_new:
            return False
        for existing in self.tickets[-20:]:   # only check recent tickets
            words_old = set(re.findall(r'\b\w{4,}\b',
                                       existing['description'].lower()))
            if not words_old:
                continue
            overlap = len(words_new & words_old) / len(words_new | words_old)
            if overlap > 0.60:   # >60% word overlap = likely duplicate
                return True
        return False

    def _determine_severity(self, text: str) -> str:
        """
        Infer severity from plain-English severity words.
        Language-agnostic — only English adjectives / nouns used.
        """
        lower = text.lower()
        if re.search(r'\b(critical|crash|corrupt|security|vulnerabilit|'
                     r'data.loss|injection|overflow|exploit)\b', lower):
            return 'CRITICAL'
        if re.search(r'\b(major|broken|fail|exception|unhandled|invalid|'
                     r'incorrect|undefined|null.?pointer|memory.leak|'
                     r'race.condition)\b', lower):
            return 'MAJOR'
        if re.search(r'\b(minor|improve|refactor|readabilit|comment|'
                     r'naming|style|simplif|document|clarif|unused)\b', lower):
            return 'MINOR'
        return 'TRIVIAL'

    def save_tickets_json(self, filename: str = 'tickets.json'):
        """Save all tickets as JSON."""
        output_file = Path(self.output_dir) / filename
        output_file.parent.mkdir(exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.tickets, f, indent=2, ensure_ascii=False)
        return str(output_file)
