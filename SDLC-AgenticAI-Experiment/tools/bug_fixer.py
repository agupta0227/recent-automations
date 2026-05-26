from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
import sys
import os

from config import LLM_MODEL, TEMPERATURE

class BugFixer:
    def __init__(self):
        self.llm = ChatOllama(model=LLM_MODEL, temperature=TEMPERATURE)

        self.prompt = ChatPromptTemplate.from_template("""
You are an expert debugger and code fixer.
The code below may be written in any language — fix it using best practices
for whatever language it is written in.

Original Code:
{generated_code}

Issues Found:
{issues}

Your task: fix ALL issues listed above and return the COMPLETE corrected code.

IMPORTANT OUTPUT RULES:
- Return the full corrected file(s), not just snippets or diffs.
- Use the same === filename.ext === separator format as the original.
- Do NOT include explanations or commentary inside the code blocks.
- After all code blocks, add a brief **Fix Summary** section.

Output format:

=== filename.ext ===
[complete corrected file contents here]

=== filename2.ext ===
[complete corrected file contents here]

**Fix Summary:**
- [what was fixed and why]
""")

    def fix(self, generated_code: str, issues: str) -> str:
        """Fix the code based on reported issues."""
        chain = self.prompt | self.llm
        response = chain.invoke({
            "generated_code": generated_code,
            "issues": issues
        })

        print("\n=== BUG FIX OUTPUT ===")
        print(response.content)
        print("======================\n")

        return response.content


if __name__ == "__main__":
    fixer = BugFixer()
    fixer.fix(
        generated_code="def divide(a, b):\n    return a / b",
        issues="- Critical: No check for division by zero"
    )
