"""
Agent Metadata and Accountability System
Defines roles, responsibilities, and accountability for each agent in the SDLC cycle
"""

from typing import Dict, List
from dataclasses import dataclass, asdict
from enum import Enum
import json
from datetime import datetime

class AgentRole(Enum):
    """Define available agent roles"""
    ANALYZER = "Analyzer"
    GENERATOR = "Generator"
    REVIEWER = "Reviewer"
    TESTER = "Tester"
    FIXER = "Fixer"
    ORGANIZER = "Organizer"

@dataclass
class AgentMetadata:
    """Metadata for an agent in the SDLC cycle"""
    name: str
    role: AgentRole
    description: str
    responsibilities: List[str]
    success_criteria: List[str]
    failure_modes: List[str]
    timeout_seconds: int = 600
    max_retries: int = 3
    
    def to_dict(self):
        return {
            'name': self.name,
            'role': self.role.value,
            'description': self.description,
            'responsibilities': self.responsibilities,
            'success_criteria': self.success_criteria,
            'failure_modes': self.failure_modes,
            'timeout_seconds': self.timeout_seconds,
            'max_retries': self.max_retries
        }

class AgentRegistry:
    """Registry of all agents with their metadata and accountability"""
    
    AGENTS = {
        "RequirementAnalyzer": AgentMetadata(
            name="RequirementAnalyzer",
            role=AgentRole.ANALYZER,
            description="Breaks down high-level requirements into actionable, detailed technical tasks",
            responsibilities=[
                "Parse and understand business requirements",
                "Identify UI components needed",
                "Define data handling and validation rules",
                "Document technical considerations",
                "Produce clear architecture guidelines"
            ],
            success_criteria=[
                "Analysis is clear and structured",
                "All UI components identified",
                "Validation rules explicitly stated",
                "Technical considerations documented",
                "Output can guide code generation"
            ],
            failure_modes=[
                "Misunderstanding of requirements",
                "Incomplete component identification",
                "Missing validation rules",
                "Vague technical guidance",
                "Analysis too broad or too narrow"
            ]
        ),
        
        "CodeGenerator": AgentMetadata(
            name="CodeGenerator",
            role=AgentRole.GENERATOR,
            description="Generates complete, functional VB.NET Windows Forms code based on requirements",
            responsibilities=[
                "Write syntactically correct VB.NET code",
                "Implement all required UI components",
                "Add error handling and validation",
                "Follow naming conventions",
                "Include appropriate comments",
                "Ensure code is compilable"
            ],
            success_criteria=[
                "Code compiles without errors",
                "All required features implemented",
                "Proper error handling present",
                "Code is readable and commented",
                "No security vulnerabilities",
                "Follows VB.NET best practices"
            ],
            failure_modes=[
                "Syntax errors preventing compilation",
                "Missing required features",
                "No error handling",
                "Poor variable naming",
                "Unhandled edge cases",
                "Memory leaks or resource issues"
            ]
        ),
        
        "CodeReviewer": AgentMetadata(
            name="CodeReviewer",
            role=AgentRole.REVIEWER,
            description="Reviews code quality, identifies bugs, and provides constructive feedback",
            responsibilities=[
                "Check code syntax and structure",
                "Identify bugs and potential issues",
                "Review error handling",
                "Assess code readability",
                "Suggest performance improvements",
                "Rate severity of issues",
                "Provide specific, actionable feedback"
            ],
            success_criteria=[
                "All bugs clearly identified",
                "Severity levels accurate",
                "Feedback is constructive",
                "Solutions proposed for critical issues",
                "No false positives",
                "Review is thorough but efficient"
            ],
            failure_modes=[
                "Missing critical bugs",
                "False positives",
                "Vague or unclear feedback",
                "Inconsistent severity ratings",
                "No solutions proposed",
                "Reviews too harsh or too lenient"
            ]
        ),
        
        "Tester": AgentMetadata(
            name="Tester",
            role=AgentRole.TESTER,
            description="Generates comprehensive test cases and validates code functionality",
            responsibilities=[
                "Generate functional test cases",
                "Identify edge cases",
                "Create test steps and expected results",
                "Test data validation",
                "Test error conditions",
                "Document test coverage",
                "Suggest additional testing scenarios"
            ],
            success_criteria=[
                "Test cases cover main features",
                "Edge cases identified",
                "Clear step-by-step instructions",
                "Expected results specified",
                "Test cases are executable",
                "Good balance of coverage vs. practicality"
            ],
            failure_modes=[
                "Insufficient test coverage",
                "Untestable test cases",
                "Missing edge cases",
                "Vague expected results",
                "Duplicate tests",
                "Tests for non-existent features"
            ]
        ),
        
        "BugFixer": AgentMetadata(
            name="BugFixer",
            role=AgentRole.FIXER,
            description="Fixes identified bugs and implements improvements to code",
            responsibilities=[
                "Understand reported issues",
                "Provide corrected code snippets",
                "Explain the fix",
                "Suggest preventive measures",
                "Maintain code consistency",
                "Ensure fixes don't introduce new issues",
                "Document changes"
            ],
            success_criteria=[
                "All reported bugs fixed",
                "Fixes are correct and complete",
                "No new bugs introduced",
                "Code quality maintained",
                "Fixes well-documented",
                "Performance not degraded"
            ],
            failure_modes=[
                "Incomplete fixes",
                "Introducing new bugs",
                "Poor understanding of issues",
                "Breaking existing functionality",
                "Performance degradation",
                "Inconsistent coding style"
            ]
        ),
        
        "ProjectOrganizer": AgentMetadata(
            name="ProjectOrganizer",
            role=AgentRole.ORGANIZER,
            description="Organizes project deliverables and creates documentation",
            responsibilities=[
                "Create project structure",
                "Write README and documentation",
                "Organize code files logically",
                "Create changelog entries",
                "Generate project summary",
                "Create deployment guide",
                "Document all decisions made"
            ],
            success_criteria=[
                "Project structure is clear",
                "Documentation is complete",
                "README is comprehensive",
                "Project is easy to understand",
                "Files are organized logically",
                "All decisions documented"
            ],
            failure_modes=[
                "Incomplete documentation",
                "Confusing project structure",
                "Missing README",
                "Undocumented decisions",
                "Poor organization",
                "Unclear instructions"
            ]
        )
    }
    
    @classmethod
    def get_agent(cls, agent_name: str) -> AgentMetadata:
        """Get metadata for a specific agent"""
        return cls.AGENTS.get(agent_name)
    
    @classmethod
    def get_all_agents(cls) -> Dict[str, AgentMetadata]:
        """Get all registered agents"""
        return cls.AGENTS
    
    @classmethod
    def to_json(cls) -> str:
        """Export all agent metadata as JSON"""
        agents_dict = {name: agent.to_dict() for name, agent in cls.AGENTS.items()}
        return json.dumps(agents_dict, indent=2)

class AgentPerformanceTracker:
    """Track performance and accountability for each agent"""
    
    def __init__(self):
        self.metrics = {}
        for agent_name in AgentRegistry.AGENTS.keys():
            self.metrics[agent_name] = {
                'calls': 0,
                'successes': 0,
                'failures': 0,
                'total_time': 0.0,
                'avg_time': 0.0,
                'issues_found': 0,
                'issues_fixed': 0,
                'last_run': None,
                'last_error': None
            }
    
    def record_execution(self, 
                        agent_name: str, 
                        duration: float, 
                        success: bool,
                        output_length: int = 0,
                        issues_found: int = 0):
        """Record an agent execution"""
        
        if agent_name not in self.metrics:
            self.metrics[agent_name] = {
                'calls': 0,
                'successes': 0,
                'failures': 0,
                'total_time': 0.0,
                'avg_time': 0.0,
                'issues_found': 0,
                'issues_fixed': 0,
                'last_run': None,
                'last_error': None
            }
        
        m = self.metrics[agent_name]
        m['calls'] += 1
        m['total_time'] += duration
        m['avg_time'] = m['total_time'] / m['calls']
        m['last_run'] = datetime.now().isoformat()
        
        if success:
            m['successes'] += 1
        else:
            m['failures'] += 1
        
        if issues_found > 0:
            m['issues_found'] += issues_found
            m['issues_fixed'] += issues_found
    
    def record_error(self, agent_name: str, error: str):
        """Record an error for an agent"""
        if agent_name in self.metrics:
            self.metrics[agent_name]['last_error'] = error
    
    def get_report(self) -> Dict:
        """Get performance report for all agents"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'agents': {}
        }
        
        for agent_name, metrics in self.metrics.items():
            success_rate = (metrics['successes'] / metrics['calls'] * 100) if metrics['calls'] > 0 else 0
            report['agents'][agent_name] = {
                **metrics,
                'success_rate': f"{success_rate:.1f}%"
            }
        
        return report
    
    def print_report(self):
        """Print performance report to console"""
        report = self.get_report()
        
        print("\n" + "=" * 100)
        print("AGENT PERFORMANCE ACCOUNTABILITY REPORT")
        print("=" * 100)
        
        for agent_name, metrics in report['agents'].items():
            agent = AgentRegistry.get_agent(agent_name)
            print(f"\n{agent_name.upper()}")
            print(f"  Role: {agent.role.value}")
            print(f"  Executions: {metrics['calls']}")
            print(f"  Success Rate: {metrics['success_rate']}")
            print(f"  Avg Time: {metrics['avg_time']:.1f}s")
            print(f"  Issues Found: {metrics['issues_found']}")
            
            if metrics['last_error']:
                print(f"  Last Error: {metrics['last_error']}")
        
        print("\n" + "=" * 100)
    
    def export_report(self, output_path: str):
        """Export performance report to file"""
        report = self.get_report()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
