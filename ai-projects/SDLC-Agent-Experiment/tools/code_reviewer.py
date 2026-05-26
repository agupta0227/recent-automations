from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
import sys
import os

from config import LLM_MODEL, TEMPERATURE

class CodeReviewer:
    def __init__(self):
        self.llm = ChatOllama(model=LLM_MODEL, temperature=TEMPERATURE)

        self.prompt = ChatPromptTemplate.from_template("""
You are an experienced senior developer doing a code review.
The code below may be written in any language — review it using best practices
for whatever language it is written in.

Code to review:
{generated_code}

Please output in this EXACT format:

**Summary:**
One sentence overall assessment.

**Issues Found:**
- List any bugs, syntax errors, or bad practices (with severity: Minor / Major / Critical)
- If there are no issues, write: "- No issues found."

**Improvements Suggested:**
- List specific improvements for readability, performance, or maintainability
- If none, write: "- None."

**Fixed Code (if needed):**
If there are Critical issues, provide the corrected version of the problematic sections.
If there are no Critical issues, write: "Not required."

Be honest but constructive. Judge the code by the standards of its own language.
""")

    def review(self, generated_code: str) -> str:
        """Review the generated code and return feedback."""
        chain = self.prompt | self.llm
        response = chain.invoke({"generated_code": generated_code})

        print("\n=== CODE REVIEW FEEDBACK ===")
        print(response.content)
        print("============================\n")

        return response.content


if __name__ == "__main__":
    reviewer = CodeReviewer()
    reviewer.review("""
def add(a, b):
    return a + b
print(add(1, 2))
""")
