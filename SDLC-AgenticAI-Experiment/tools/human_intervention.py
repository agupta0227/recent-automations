"""
Human-in-the-Loop Intervention System
Allows human approval/rejection at each step of the SDLC cycle
Similar to quality gates in a car assembly line
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json

class ApprovalStatus(Enum):
    """Status of an approval decision"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPROVED_WITH_CHANGES = "APPROVED_WITH_CHANGES"
    SKIPPED = "SKIPPED"

@dataclass
class ApprovalDecision:
    """Records a human approval decision"""
    step_name: str
    timestamp: str
    status: ApprovalStatus
    reviewer: str
    comments: str = ""
    suggested_changes: str = ""
    
    def to_dict(self):
        return {
            'step_name': self.step_name,
            'timestamp': self.timestamp,
            'status': self.status.value,
            'reviewer': self.reviewer,
            'comments': self.comments,
            'suggested_changes': self.suggested_changes
        }

class HumanInterventionGate:
    """Quality gate for human intervention"""
    
    def __init__(self, enable_intervention: bool = False):
        self.enabled = enable_intervention
        self.decisions: Dict[str, ApprovalDecision] = {}
        self.approval_history = []
    
    def request_approval(self, 
                        step_name: str,
                        output_content: str,
                        context: Dict[str, Any] = None,
                        auto_approve: bool = False) -> ApprovalDecision:
        """Request human approval for a step"""
        
        if not self.enabled or auto_approve:
            # Auto-approve if intervention disabled
            decision = ApprovalDecision(
                step_name=step_name,
                timestamp=datetime.now().isoformat(),
                status=ApprovalStatus.SKIPPED if not self.enabled else ApprovalStatus.APPROVED,
                reviewer="SYSTEM"
            )
        else:
            # Request human review
            decision = self._prompt_for_approval(step_name, output_content, context)
        
        self.decisions[step_name] = decision
        self.approval_history.append(decision)
        
        return decision
    
    def _prompt_for_approval(self,
                           step_name: str,
                           output_content: str,
                           context: Dict = None) -> ApprovalDecision:
        """Prompt human for approval (interactive)"""
        
        print("\n" + "=" * 100)
        print(f"🔍 HUMAN APPROVAL GATE: {step_name}")
        print("=" * 100)
        
        if context:
            print("\nContext:")
            for key, value in context.items():
                if isinstance(value, str):
                    print(f"  {key}: {value[:100]}...")
                else:
                    print(f"  {key}: {value}")
        
        print("\nOutput Preview (first 500 chars):")
        print("-" * 100)
        print(output_content[:500])
        if len(output_content) > 500:
            print(f"\n... ({len(output_content) - 500} more characters)")
        print("-" * 100)
        
        print("\nOptions:")
        print("  1. APPROVE (continue to next step)")
        print("  2. REJECT (stop and return to previous step)")
        print("  3. APPROVE WITH CHANGES (approve but with notes)")
        print("  4. SKIP (auto-approve without review)")
        
        while True:
            try:
                choice = input("\nEnter choice (1-4): ").strip()
                
                if choice == "1":
                    status = ApprovalStatus.APPROVED
                    comments = ""
                    break
                elif choice == "2":
                    status = ApprovalStatus.REJECTED
                    comments = input("Reason for rejection: ").strip()
                    break
                elif choice == "3":
                    status = ApprovalStatus.APPROVED_WITH_CHANGES
                    comments = input("Approval comments: ").strip()
                    break
                elif choice == "4":
                    status = ApprovalStatus.SKIPPED
                    comments = ""
                    break
                else:
                    print("Invalid choice. Please enter 1-4.")
            except KeyboardInterrupt:
                print("\nApproval cancelled by user.")
                status = ApprovalStatus.REJECTED
                comments = "Cancelled by user"
                break
        
        reviewer = input("Reviewer name (or press Enter for 'HUMAN_REVIEWER'): ").strip() or "HUMAN_REVIEWER"
        
        decision = ApprovalDecision(
            step_name=step_name,
            timestamp=datetime.now().isoformat(),
            status=status,
            reviewer=reviewer,
            comments=comments
        )
        
        return decision
    
    def was_approved(self, step_name: str) -> bool:
        """Check if a step was approved"""
        if step_name not in self.decisions:
            return True  # Default to approved if not reviewed
        
        status = self.decisions[step_name].status
        return status in [ApprovalStatus.APPROVED, ApprovalStatus.APPROVED_WITH_CHANGES]
    
    def was_rejected(self, step_name: str) -> bool:
        """Check if a step was rejected"""
        if step_name not in self.decisions:
            return False
        
        return self.decisions[step_name].status == ApprovalStatus.REJECTED
    
    def get_decision(self, step_name: str) -> Optional[ApprovalDecision]:
        """Get approval decision for a step"""
        return self.decisions.get(step_name)
    
    def get_all_decisions(self) -> Dict[str, ApprovalDecision]:
        """Get all decisions"""
        return self.decisions
    
    def print_audit_trail(self):
        """Print approval audit trail"""
        print("\n" + "=" * 100)
        print("APPROVAL AUDIT TRAIL")
        print("=" * 100)
        
        for i, decision in enumerate(self.approval_history, 1):
            print(f"\n{i}. Step: {decision.step_name}")
            print(f"   Timestamp: {decision.timestamp}")
            print(f"   Status: {decision.status.value}")
            print(f"   Reviewer: {decision.reviewer}")
            if decision.comments:
                print(f"   Comments: {decision.comments}")
        
        print("\n" + "=" * 100)
    
    def export_audit_trail(self, output_path: str):
        """Export approval audit trail to JSON"""
        trail = {
            'total_approvals': len(self.approval_history),
            'decisions': [d.to_dict() for d in self.approval_history],
            'summary': {
                'approved': sum(1 for d in self.approval_history if d.status == ApprovalStatus.APPROVED),
                'rejected': sum(1 for d in self.approval_history if d.status == ApprovalStatus.REJECTED),
                'approved_with_changes': sum(1 for d in self.approval_history if d.status == ApprovalStatus.APPROVED_WITH_CHANGES),
                'skipped': sum(1 for d in self.approval_history if d.status == ApprovalStatus.SKIPPED),
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(trail, f, indent=2)

class ApprovalGateConfig:
    """Configuration for which steps require approval"""
    
    GATE_CONFIG = {
        # Step name -> (require_approval, description)
        'analyze': (True, 'Review requirement analysis'),
        'generate': (True, 'Review generated code'),
        'review': (False, 'Skip code review approval'),
        'test': (False, 'Skip test case approval'),
        'fix': (True, 'Review bug fixes'),
        'organize': (True, 'Review final deliverables'),
    }
    
    @classmethod
    def requires_approval(cls, step_name: str) -> bool:
        """Check if step requires human approval"""
        return cls.GATE_CONFIG.get(step_name, (False, ''))[0]
    
    @classmethod
    def get_description(cls, step_name: str) -> str:
        """Get description of what to approve"""
        return cls.GATE_CONFIG.get(step_name, ('', 'Review output'))[1]
    
    @classmethod
    def update_gate(cls, step_name: str, require_approval: bool):
        """Update gate requirement for a step"""
        if step_name in cls.GATE_CONFIG:
            desc = cls.GATE_CONFIG[step_name][1]
            cls.GATE_CONFIG[step_name] = (require_approval, desc)

class AssemblyLineSimulator:
    """Simulates a quality control assembly line with human inspection points"""
    
    INSPECTION_POINTS = {
        'analyze': '🔵 QUALITY CHECK 1: Requirement Analysis',
        'generate': '🟡 QUALITY CHECK 2: Code Generation',
        'review': '🟢 QUALITY CHECK 3: Code Review',
        'test': '🔵 QUALITY CHECK 4: Testing',
        'fix': '🟡 QUALITY CHECK 5: Bug Fixes',
        'organize': '🟢 QUALITY CHECK 6: Project Organization',
    }
    
    def __init__(self):
        self.gate = HumanInterventionGate()
    
    def stop_at_inspection_point(self, step_name: str, output: str, context: Dict = None) -> bool:
        """Simulate a quality control inspection point on assembly line"""
        
        if not ApprovalGateConfig.requires_approval(step_name):
            return True  # Continue
        
        inspection_name = self.INSPECTION_POINTS.get(step_name, step_name)
        print(f"\n⏹️  ASSEMBLY LINE PAUSE - {inspection_name}")
        print("Worker: Please inspect the quality before it moves to the next station.")
        
        decision = self.gate.request_approval(
            step_name=step_name,
            output_content=output,
            context=context
        )
        
        if decision.status == ApprovalStatus.REJECTED:
            print(f"\n❌ REJECTION: {decision.comments}")
            print("Product returned for rework.")
            return False
        elif decision.status == ApprovalStatus.APPROVED_WITH_CHANGES:
            print(f"\n⚠️  APPROVED WITH NOTES: {decision.comments}")
            print("Moving to next station with special handling.")
            return True
        else:
            print("\n✅ APPROVAL: Product meets quality standards. Moving to next station.")
            return True
