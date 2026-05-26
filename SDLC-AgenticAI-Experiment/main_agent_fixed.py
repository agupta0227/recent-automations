import sys
# Force UTF-8 output on Windows so emoji in log messages don't crash
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from tools.requirement_analyzer import RequirementAnalyzer
from tools.code_generator import CodeGenerator
from tools.code_reviewer import CodeReviewer
from tools.tester import Tester
from tools.bug_fixer import BugFixer
from tools.project_organizer import ProjectOrganizer
from tools.code_formatter import CodeFormatterImproved
from tools.ticket_generator import TicketGeneratorImproved
from tools.explainability_agent import ExplainabilityAgent
from tools.human_intervention import HumanInterventionGate, ApprovalStatus
from tools.agent_metadata import AgentPerformanceTracker
from tools.realtime_logger import RealtimeLogger
from langchain_ollama import ChatOllama
from config import (
    TARGET_APP_NAME, OUTPUT_DIR, MAX_ITERATIONS,
    LLM_MODEL, TEMPERATURE, ENABLE_HUMAN_APPROVAL, AGENT_TIMEOUTS,
    REQUIREMENT, TARGET_LANGUAGE
)
import os
import time
from datetime import datetime


class AgentState(TypedDict):
    requirement: str
    analysis: str
    generated_code: str
    review_feedback: str
    review_verdict: str          # NEW: "PASS" or "FAIL" — structured, not string-matched
    test_cases: str
    fix_suggestions: str
    final_summary: str
    messages: Annotated[list, operator.add]
    iteration: int
    completed_agents: list       # NEW: tracked dynamically, not hard-coded
    language: str                # language hint from requirements.txt


class SDLC_Agent:
    def __init__(self):
        self.logger = RealtimeLogger(OUTPUT_DIR)

        # Core SDLC agents
        self.analyzer = RequirementAnalyzer()
        self.generator = CodeGenerator()
        self.reviewer = CodeReviewer()
        self.tester = Tester()
        self.fixer = BugFixer()
        self.organizer = ProjectOrganizer()

        # Supporting agents (previously orphaned — now wired in)
        self.formatter = CodeFormatterImproved(OUTPUT_DIR)
        self.ticket_gen = TicketGeneratorImproved(OUTPUT_DIR)
        self.performance = AgentPerformanceTracker()
        self.human_gate = HumanInterventionGate(enable_intervention=ENABLE_HUMAN_APPROVAL)

        # Shared LLM instance for ExplainabilityAgent
        shared_llm = ChatOllama(model=LLM_MODEL, temperature=TEMPERATURE)
        self.explainer = ExplainabilityAgent(llm=shared_llm, output_dir=OUTPUT_DIR)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _gate(self, step_name: str, content: str, context: dict = None) -> bool:
        """Request human approval if ENABLE_HUMAN_APPROVAL is True. Returns True = proceed."""
        decision = self.human_gate.request_approval(
            step_name=step_name,
            output_content=content,
            context=context
        )
        return decision.status != ApprovalStatus.REJECTED

    def _mark_complete(self, state: AgentState, agent_name: str) -> list:
        """Return an updated completed_agents list without mutating state directly."""
        existing = list(state.get("completed_agents", []))
        if agent_name not in existing:
            existing.append(agent_name)
        return existing

    # ------------------------------------------------------------------
    # NODE: analyze_requirement
    # ------------------------------------------------------------------
    def analyze_requirement(self, state: AgentState):
        start = time.time()
        self.logger.set_running_agents(['RequirementAnalyzer'])
        self.logger.log('RequirementAnalyzer', 'Starting requirement analysis...')

        try:
            analysis = self.analyzer.analyze(state["requirement"], state.get("language", "auto"))
            duration = time.time() - start
            self.performance.record_execution('RequirementAnalyzer', duration, success=True)
        except Exception as e:
            duration = time.time() - start
            self.performance.record_error('RequirementAnalyzer', str(e))
            self.performance.record_execution('RequirementAnalyzer', duration, success=False)
            raise

        self.logger.log('RequirementAnalyzer', f'Analysis complete ({duration:.1f}s)')

        # Human gate
        self._gate('analyze', analysis, context={'requirement': state["requirement"][:200]})

        # Explainability
        self.explainer.explain_decision(
            agent_name='RequirementAnalyzer',
            decision='ANALYZED',
            reasoning=analysis[:300],
            confidence=90
        )

        completed = self._mark_complete(state, 'RequirementAnalyzer')
        self.logger.set_completed_agents(completed)

        return {
            "analysis": analysis,
            "messages": [f"Requirement analyzed ({duration:.1f}s)"],
            "iteration": state.get("iteration", 0),
            "completed_agents": completed,
            "language": state.get("language", "auto")
        }

    # ------------------------------------------------------------------
    # NODE: generate_code
    # ------------------------------------------------------------------
    def generate_code(self, state: AgentState):
        start = time.time()
        self.logger.set_running_agents(['CodeGenerator'])
        self.logger.log('CodeGenerator', 'Starting code generation...')

        try:
            raw_output = self.generator.generate(state["analysis"])
            duration = time.time() - start
            self.performance.record_execution('CodeGenerator', duration, success=True)
        except Exception as e:
            duration = time.time() - start
            self.performance.record_error('CodeGenerator', str(e))
            self.performance.record_execution('CodeGenerator', duration, success=False)
            raise

        # Extract clean code blocks via CodeFormatter
        self.logger.log('CodeFormatter', 'Extracting code blocks from generator output...')
        code_blocks = self.formatter.extract_code_blocks(raw_output)

        if code_blocks:
            primary_code = None
            for filename, code in code_blocks.items():
                self.formatter.save_code_file(code, version=1, filename=filename)
                if primary_code is None:
                    primary_code = code
            generated_code = primary_code
            self.logger.log('CodeFormatter', f'Extracted {len(code_blocks)} code block(s)')
        else:
            # Fallback: use raw output if formatter finds nothing
            generated_code = raw_output
            self.logger.log('CodeFormatter', 'No structured blocks found — using raw output as fallback')

        self.logger.log('CodeGenerator', f'Code generated ({duration:.1f}s)')

        # Human gate
        self._gate('generate', generated_code, context={'analysis_preview': state["analysis"][:200]})

        # Explainability
        self.explainer.explain_decision(
            agent_name='CodeGenerator',
            decision='GENERATED',
            reasoning=f'Generated {len(generated_code)} chars of code',
            confidence=85
        )

        completed = self._mark_complete(state, 'CodeGenerator')
        completed = self._mark_complete({'completed_agents': completed}, 'CodeFormatter')
        self.logger.set_completed_agents(completed)

        return {
            "generated_code": generated_code,
            "messages": [f"Code generated ({duration:.1f}s)"],
            "completed_agents": completed
        }

    # ------------------------------------------------------------------
    # NODE: review_code
    # ------------------------------------------------------------------
    def review_code(self, state: AgentState):
        start = time.time()
        # FIX: iteration increments HERE (review), not in fix_code
        current_iteration = state.get("iteration", 0) + 1
        self.logger.set_running_agents(['CodeReviewer', 'Tester', 'BugFixer'])
        self.logger.log('CodeReviewer', f'Iteration {current_iteration}: Reviewing code...')

        try:
            feedback = self.reviewer.review(state["generated_code"])
            duration = time.time() - start
            self.performance.record_execution('CodeReviewer', duration, success=True)
        except Exception as e:
            duration = time.time() - start
            self.performance.record_error('CodeReviewer', str(e))
            self.performance.record_execution('CodeReviewer', duration, success=False)
            raise

        # FIX: structured PASS/FAIL verdict — not keyword-matched on free-form text
        verdict = self._extract_verdict(feedback)

        # Generate tickets for any issues found
        tickets = self.ticket_gen.extract_issues_from_review(feedback, iteration=current_iteration)
        if tickets:
            self.ticket_gen.save_tickets_json()
            self.logger.log('TicketGenerator', f'{len(tickets)} ticket(s) created for iteration {current_iteration}')

        self.logger.set_iteration(current_iteration)
        self.logger.log('CodeReviewer', f'Review complete — verdict: {verdict} ({duration:.1f}s)')

        # Explainability
        self.explainer.explain_decision(
            agent_name='CodeReviewer',
            decision=verdict,
            reasoning=feedback[:300],
            confidence=80
        )

        completed = self._mark_complete(state, 'CodeReviewer')
        completed = self._mark_complete({'completed_agents': completed}, 'TicketGenerator')
        self.logger.set_completed_agents(completed)

        return {
            "review_feedback": feedback,
            "review_verdict": verdict,
            "messages": [f"Code reviewed — {verdict} ({duration:.1f}s)"],
            "iteration": current_iteration,
            "completed_agents": completed
        }

    def _extract_verdict(self, feedback: str) -> str:
        """
        Derive a clean PASS/FAIL from review feedback.

        Uses explicit severity markers and positive phrases — NOT naive substring matching.
        This prevents false positives from phrases like 'No errors found' being miscounted
        as failure signals because they contain the word 'errors'.
        """
        lower = feedback.lower()

        # --- Failure markers: severity keywords NOT preceded by negation ---
        has_critical = "critical" in lower and "no critical" not in lower
        has_major = (
            ("major" in lower and "no major" not in lower)
            or ("- bug" in lower)
            or ("- error" in lower)
        )

        if has_critical or has_major:
            return "FAIL"

        # --- Pass phrases: reviewer explicitly says code is fine ---
        pass_phrases = [
            "no issues", "looks good", "well written", "clean code",
            "no bugs", "no errors found", "no critical", "overall good",
            "no major issues", "passes review", "code is correct"
        ]
        if any(phrase in lower for phrase in pass_phrases):
            return "PASS"

        # Conservative default: if we can't confirm it's clean, do one more loop
        return "FAIL"

    # ------------------------------------------------------------------
    # NODE: test_code
    # ------------------------------------------------------------------
    def test_code(self, state: AgentState):
        start = time.time()
        self.logger.log('Tester', 'Generating test cases...')

        try:
            tests = self.tester.generate_tests(state["generated_code"])
            duration = time.time() - start
            self.performance.record_execution('Tester', duration, success=True)
        except Exception as e:
            duration = time.time() - start
            self.performance.record_error('Tester', str(e))
            self.performance.record_execution('Tester', duration, success=False)
            raise

        self.logger.log('Tester', f'Tests generated ({duration:.1f}s)')

        completed = self._mark_complete(state, 'Tester')
        self.logger.set_completed_agents(completed)
        return {
            "test_cases": tests,
            "messages": [f"Tests generated ({duration:.1f}s)"],
            "completed_agents": completed
        }

    # ------------------------------------------------------------------
    # CONDITIONAL EDGE: decide_next_step
    # ------------------------------------------------------------------
    def decide_next_step(self, state: AgentState):
        current_iteration = state.get("iteration", 0)

        if current_iteration >= MAX_ITERATIONS:
            self.logger.log('Decision', f'MAX_ITERATIONS ({MAX_ITERATIONS}) reached. Finalizing.')
            self.explainer.explain_decision(
                agent_name='Router',
                decision='FORCE_FINALIZE',
                reasoning=f'Hit iteration limit of {MAX_ITERATIONS}',
                confidence=100
            )
            return "organize_project"

        # FIX: use the structured verdict stored in state — no guessing from free-form text
        verdict = state.get("review_verdict", "FAIL")

        if verdict == "FAIL":
            self.logger.log(
                'Decision',
                f'Verdict: FAIL — routing to BugFixer (iteration {current_iteration}/{MAX_ITERATIONS})'
            )
            self.explainer.explain_decision(
                agent_name='Router',
                decision='ROUTE_TO_FIX',
                reasoning=f'Review verdict was FAIL at iteration {current_iteration}',
                confidence=95
            )
            return "fix_code"
        else:
            self.logger.log('Decision', 'Verdict: PASS — no issues found. Finalizing.')
            self.explainer.explain_decision(
                agent_name='Router',
                decision='ROUTE_TO_FINALIZE',
                reasoning='Review verdict was PASS',
                confidence=95
            )
            return "organize_project"

    # ------------------------------------------------------------------
    # NODE: fix_code
    # ------------------------------------------------------------------
    def fix_code(self, state: AgentState):
        start = time.time()
        self.logger.log('BugFixer', 'Fixing bugs...')

        try:
            fix_output = self.fixer.fix(state["generated_code"], state["review_feedback"])
            duration = time.time() - start
            self.performance.record_execution('BugFixer', duration, success=True)
        except Exception as e:
            duration = time.time() - start
            self.performance.record_error('BugFixer', str(e))
            self.performance.record_execution('BugFixer', duration, success=False)
            raise

        # FIX: extract clean code from fixer output — don't overwrite generated_code with prose
        code_blocks = self.formatter.extract_code_blocks(fix_output)
        current_iteration = state.get("iteration", 0)

        if code_blocks:
            primary_code = None
            for filename, code in code_blocks.items():
                self.formatter.save_code_file(code, version=current_iteration, filename=filename)
                if primary_code is None:
                    primary_code = code
            fixed_code = primary_code
            self.logger.log('BugFixer', f'Extracted {len(code_blocks)} fixed code block(s)')
        else:
            # Fixer returned only prose — keep existing code, log a warning
            fixed_code = state["generated_code"]
            self.logger.log(
                'BugFixer',
                'WARNING: No clean code blocks in fixer output. '
                'Retaining previous code; suggestions stored in fix_suggestions.'
            )

        self.logger.log('BugFixer', f'Fix complete ({duration:.1f}s). Routing back to review.')

        # Human gate
        self._gate('fix', fixed_code, context={'issues_addressed': state["review_feedback"][:200]})

        # Explainability
        self.explainer.explain_decision(
            agent_name='BugFixer',
            decision='FIXED',
            reasoning=fix_output[:300],
            confidence=75
        )

        completed = self._mark_complete(state, 'BugFixer')
        self.logger.set_completed_agents(completed)
        return {
            "generated_code": fixed_code,
            "fix_suggestions": fix_output,      # prose/suggestions stored separately
            "messages": [f"Code fixed ({duration:.1f}s)"],
            # NOTE: iteration is NOT incremented here — it increments in review_code on the
            # next pass, which is the correct semantic (one iteration = one review cycle)
            "iteration": current_iteration,
            "completed_agents": completed
        }

    # ------------------------------------------------------------------
    # NODE: organize_project
    # ------------------------------------------------------------------
    def organize_project(self, state: AgentState):
        start = time.time()
        self.logger.set_running_agents(['ProjectOrganizer'])
        self.logger.log('ProjectOrganizer', 'Organizing project...')

        try:
            summary = self.organizer.organize(f"""
            Requirement: {state["requirement"]}
            Generated Code: {state["generated_code"]}
            Review: {state.get("review_feedback", "")}
            Test Cases: {state.get("test_cases", "")}
            """)
            duration = time.time() - start
            self.performance.record_execution('ProjectOrganizer', duration, success=True)
        except Exception as e:
            duration = time.time() - start
            self.performance.record_error('ProjectOrganizer', str(e))
            self.performance.record_execution('ProjectOrganizer', duration, success=False)
            raise

        # Human gate
        self._gate('organize', summary)

        # Explainability + save decisions log
        self.explainer.explain_decision(
            agent_name='ProjectOrganizer',
            decision='ORGANIZED',
            reasoning=summary[:300],
            confidence=90
        )
        self.explainer.save_decisions_log()

        # Export performance report
        self.performance.export_report(os.path.join(OUTPUT_DIR, 'performance_report.json'))
        self.performance.print_report()

        # Export human approval audit trail
        self.human_gate.export_audit_trail(os.path.join(OUTPUT_DIR, 'approval_audit.json'))
        if ENABLE_HUMAN_APPROVAL:
            self.human_gate.print_audit_trail()

        # FIX: completed_agents is built dynamically — not a hard-coded string list
        completed = self._mark_complete(state, 'ProjectOrganizer')
        self.logger.set_completed_agents(completed)
        self.logger.log('ProjectOrganizer', f'Project organized ({duration:.1f}s)')
        # Clear running_agents so UI shows correct final state
        self.logger.clear_on_complete()
        self.logger.log('System', '✅ Execution complete!')

        return {
            "final_summary": summary,
            "messages": [f"Project organized ({duration:.1f}s)"],
            "completed_agents": completed
        }

    # ------------------------------------------------------------------
    # BUILD & RUN GRAPH
    # ------------------------------------------------------------------
    def run(self, requirement: str):
        workflow = StateGraph(AgentState)

        workflow.add_node("analyze", self.analyze_requirement)
        workflow.add_node("generate", self.generate_code)
        workflow.add_node("review", self.review_code)
        workflow.add_node("test", self.test_code)
        workflow.add_node("fix_code", self.fix_code)
        workflow.add_node("organize_project", self.organize_project)

        workflow.set_entry_point("analyze")
        workflow.add_edge("analyze", "generate")
        workflow.add_edge("generate", "review")
        workflow.add_edge("review", "test")

        workflow.add_conditional_edges(
            "test",
            self.decide_next_step,
            {"fix_code": "fix_code", "organize_project": "organize_project"}
        )

        workflow.add_edge("fix_code", "review")
        workflow.add_edge("organize_project", END)

        chain = workflow.compile()

        initial_state = {
            "requirement": requirement,
            "analysis": "",
            "generated_code": "",
            "review_feedback": "",
            "review_verdict": "FAIL",
            "test_cases": "",
            "fix_suggestions": "",
            "final_summary": "",
            "messages": [],
            "iteration": 0,
            "completed_agents": [],
            "language": TARGET_LANGUAGE
        }

        self.logger.log('System', f'🚀 Starting SDLC execution with MAX_ITERATIONS={MAX_ITERATIONS}')
        self.logger.log('System', f'   Human approval gates: {"ON" if ENABLE_HUMAN_APPROVAL else "OFF"}')

        result = chain.invoke(initial_state)

        self.logger.log('System', f'✅ Execution complete! Total iterations: {result.get("iteration", 0)}')

        return result


if __name__ == "__main__":
    agent = SDLC_Agent()

    if not REQUIREMENT:
        print("ERROR: No requirement found in requirements.txt")
        print("Please edit requirements.txt and add your REQUIREMENT.")
        exit(1)

    print(f"Language : {TARGET_LANGUAGE}")
    print(f"Requirement: {REQUIREMENT[:120]}{'...' if len(REQUIREMENT) > 120 else ''}")
    result = agent.run(REQUIREMENT)
