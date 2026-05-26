# File: tools/explainability_agent.py

import json
from typing import Dict
from datetime import datetime
from pathlib import Path

class ExplainabilityAgent:
    """Every agent decision gets explained"""
    
    def __init__(self, llm, output_dir: str):
        self.llm = llm
        self.output_dir = Path(output_dir)
        self.decisions = []
    
    def explain_decision(self, agent_name: str, decision: str, 
                        reasoning: str, confidence: int) -> Dict:
        """Generate explanation for any agent decision"""
        
        # Generate human-friendly explanation
        prompt = f"""
        Agent: {agent_name}
        Decision: {decision}
        Technical Details: {reasoning[:200]}
        
        Explain in 2-3 sentences what was decided and why.
        Keep it simple for non-technical people.
        """
        
        try:
            explanation_response = self.llm.invoke(prompt)
            explanation = explanation_response.content if hasattr(explanation_response, 'content') else str(explanation_response)
        except:
            explanation = f"{agent_name} decided to {decision} based on analysis"
        
        decision_obj = {
            'agent': agent_name,
            'decision': decision,
            'confidence': confidence,
            'timestamp': datetime.now().isoformat(),
            'technical_reasoning': reasoning[:500],
            'explanation': explanation,
            'next_step': self._get_next_step(agent_name, decision)
        }
        
        self.decisions.append(decision_obj)
        return decision_obj
    
    def _get_next_step(self, agent_name: str, decision: str) -> str:
        """What happens after this decision"""
        
        steps = {
            ('CodeReviewer', 'REJECT'): 'Routing to BugFixer for improvements',
            ('CodeReviewer', 'APPROVE'): 'Moving to ProjectOrganizer',
            ('BugFixer', 'FIXED'): 'Re-reviewing with CodeReviewer',
            ('Tester', 'PASS'): 'Code quality acceptable',
            ('Tester', 'FAIL'): 'Looping back to BugFixer',
        }
        
        return steps.get((agent_name, decision), 'Moving to next phase')
    
    def generate_summary(self) -> str:
        """Generate executive summary of all decisions"""
        
        summary = "EXECUTION DECISIONS\n"
        summary += "=" * 50 + "\n\n"
        
        for dec in self.decisions[-10:]:  # Last 10 decisions
            summary += f"[{dec['agent']}] {dec['decision']}\n"
            summary += f"  Confidence: {dec['confidence']}%\n"
            summary += f"  {dec['explanation']}\n"
            summary += f"  Next: {dec['next_step']}\n\n"
        
        return summary
    
    def save_decisions_log(self):
        """Save all decisions"""
        output_file = self.output_dir / 'decisions_log.json'
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(self.decisions, f, indent=2)
        
        return str(output_file)