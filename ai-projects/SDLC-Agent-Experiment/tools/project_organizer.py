from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
import sys
import os

# Import config
from config import LLM_MODEL, TEMPERATURE

class ProjectOrganizer:
    def __init__(self):
        self.llm = ChatOllama(
            model=LLM_MODEL,
            temperature=TEMPERATURE
        )
        
        self.prompt = ChatPromptTemplate.from_template("""
You are an experienced technical writer and project organizer.

Given the following:
- Original requirement
- Generated code
- Code review feedback
- Test cases

Create a clean, professional project structure summary and a README.md content.

Input:
{input_data}

Output a complete README.md content that includes:
- Project title and description
- Features
- How to run the application
- File structure
- Any known limitations
- Setup instructions

Make it clear and suitable for a GitHub repository.
""")

    def organize(self, input_data: str):
        """Generate project organization and README content"""
        chain = self.prompt | self.llm
        response = chain.invoke({"input_data": input_data})
        
        print("\n=== PROJECT ORGANIZER OUTPUT ===")
        print(response.content)
        print("================================\n")
        
        return response.content

# For testing
if __name__ == "__main__":
    organizer = ProjectOrganizer()
    
    test_input = """
Requirement: Create a simple sales data entry form.
Generated Code: [dummy code]
Review: Minor naming issues, add error handling.
Test Cases: 5 test cases generated.
"""
    
    organizer.organize(test_input)