from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
import sys
import os

from config import LLM_MODEL, TEMPERATURE

class Tester:
    def __init__(self):
        self.llm = ChatOllama(model=LLM_MODEL, temperature=TEMPERATURE)

        self.prompt = ChatPromptTemplate.from_template("""
You are an experienced QA engineer.
The code below may be written in any language — generate practical test cases
appropriate for that language and type of application.

Code:
{generated_code}

Please output in this EXACT format:

**Test Cases:**

1. **Test Name:** [Short name]
   **Description:** [What this test checks]
   **Steps:**
   - Step 1...
   - Step 2...
   **Expected Result:** [What should happen]

2. **Test Name:** ...
   ...

**Edge Cases to Consider:**
- Invalid inputs
- Empty or null values
- Boundary conditions
- Error conditions

Focus on the most important tests for this specific code.
If the code is a script or CLI tool, describe manual test steps.
If the code has functions, describe unit test scenarios.
""")

    def generate_tests(self, generated_code: str) -> str:
        """Generate test cases for the code."""
        chain = self.prompt | self.llm
        response = chain.invoke({"generated_code": generated_code})

        print("\n=== GENERATED TEST CASES ===")
        print(response.content)
        print("============================\n")

        return response.content


if __name__ == "__main__":
    tester = Tester()
    tester.generate_tests("""
def divide(a, b):
    return a / b
""")
