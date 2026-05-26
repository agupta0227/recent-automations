from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
import os
import sys

from config import LLM_MODEL, TEMPERATURE

class CodeGenerator:
    def __init__(self):
        self.llm = ChatOllama(model=LLM_MODEL, temperature=TEMPERATURE)

        self.prompt = ChatPromptTemplate.from_template("""
You are an expert software developer.

The requirement analysis below specifies the language, framework, and file structure to use.
Read the "Language & Framework Decision" and "File Structure" sections carefully — use exactly
those choices. Do not switch languages or add unrequested frameworks.

Requirement Analysis:
{analysis}

Generate COMPLETE, working code for every file listed in the File Structure.

Rules:
- Write syntactically correct code for the chosen language
- Include proper error handling
- Use meaningful variable and function names
- Add brief comments explaining key sections
- Do NOT leave placeholder comments like "# TODO" or "// implement this"
- Each file must be complete and runnable/compilable on its own or as part of the set

Output format — one block per file, using this exact separator:

=== filename.ext ===
[complete file contents here]

=== filename2.ext ===
[complete file contents here]

Only output code blocks. No prose before or after.
""")

    def generate(self, requirement_analysis: str) -> str:
        """Generate code based on requirement analysis."""
        chain = self.prompt | self.llm
        response = chain.invoke({"analysis": requirement_analysis})

        print("\n=== GENERATED CODE ===")
        print(response.content)
        print("======================\n")

        return response.content


if __name__ == "__main__":
    generator = CodeGenerator()
    test_analysis = """
**Language & Framework Decision:**
- Language: Python
- Framework/Libraries: standard library only
- Reason: Simple script, no external dependencies needed.

**File Structure:**
- main.py

**Core Features:**
- Print hello world
"""
    generator.generate(test_analysis)
