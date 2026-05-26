from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
import os
import sys

from config import LLM_MODEL, TEMPERATURE

class RequirementAnalyzer:
    def __init__(self):
        self.llm = ChatOllama(model=LLM_MODEL, temperature=TEMPERATURE)

        self.prompt = ChatPromptTemplate.from_template("""
You are an experienced software architect.

The user wants to build something. Your job is to:
1. Decide the best programming language and framework/libraries to use (unless one is specified).
2. Break the requirement down into clear, actionable technical tasks.

Language hint: {language}
(If the hint is "auto", choose the most appropriate language and framework yourself based on the requirement.)

Requirement: {requirement}

Please output in this EXACT format — do not skip any section:

**Language & Framework Decision:**
- Language: [the language you will use]
- Framework/Libraries: [framework or key libraries, or "None / standard library"]
- Reason: [one sentence explaining why this is the right choice]

**File Structure:**
- List the files that need to be created (e.g. main.py, index.js, App.java)

**UI / Interface Components:** (if applicable)
- List all UI elements, screens, or API endpoints needed
- Write "N/A" if this is a CLI tool, script, or library

**Data Handling:**
- What data needs to be stored or processed
- Validation rules
- Storage format (file, database, in-memory, etc.)

**Core Features:**
- List functional requirements in bullet points

**Technical Considerations:**
- Language-specific best practices to follow
- Error handling approach
- Any important constraints or edge cases

Be specific and practical. Think like a senior developer.
""")

    def analyze(self, requirement: str, language: str = "auto") -> str:
        """Analyze the requirement and return structured tasks including language decision."""
        chain = self.prompt | self.llm
        response = chain.invoke({
            "requirement": requirement,
            "language": language
        })

        print("\n=== REQUIREMENT ANALYSIS ===")
        print(response.content)
        print("===========================\n")

        return response.content


if __name__ == "__main__":
    analyzer = RequirementAnalyzer()
    analyzer.analyze(
        requirement="Create a CLI tool that watches a folder and auto-renames files by date.",
        language="auto"
    )
