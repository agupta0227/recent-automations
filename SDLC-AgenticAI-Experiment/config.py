import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TOOLS_DIR  = os.path.join(BASE_DIR, "tools")
REQUIREMENTS_FILE = os.path.join(BASE_DIR, "requirements.txt")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── LLM Settings (Ollama) ──────────────────────────────────────────────────
LLM_MODEL   = "gemma2:2b"   # change to "llama3.1:8b" for better results
TEMPERATURE = 0.3
MAX_TOKENS  = 2048

# ── Agent Settings ─────────────────────────────────────────────────────────
MAX_ITERATIONS       = 5     # safe limit for small models; raise to 10 for larger ones
DEBUG_MODE           = True
ENABLE_HUMAN_APPROVAL = False

# ── Timeouts ───────────────────────────────────────────────────────────────
AGENT_TIMEOUTS = {
    'requirement_analyzer': 120,
    'code_generator':       180,
    'code_reviewer':        150,
    'tester':               180,
    'bug_fixer':            300,
    'project_organizer':    120,
}

# ── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"

# ── Requirements file parser ───────────────────────────────────────────────
def _parse_requirements_file(path: str):
    """
    Parse requirements.txt.
    Returns (language, requirement_text).
    Lines starting with # are comments and are ignored.
    LANGUAGE: <value>  sets the language hint (or "auto").
    Everything after REQUIREMENT: (on the next line) is the requirement body.
    """
    language    = "auto"
    requirement = ""

    if not os.path.exists(path):
        return language, requirement

    content = Path(path).read_text(encoding="utf-8")
    lines   = content.splitlines()

    in_requirement = False
    req_lines      = []

    for line in lines:
        stripped = line.strip()

        # Skip comment lines
        if stripped.startswith("#"):
            continue

        if stripped.upper().startswith("LANGUAGE:"):
            language = stripped.split(":", 1)[1].strip()
            in_requirement = False

        elif stripped.upper().startswith("REQUIREMENT:"):
            in_requirement = True
            # Anything after the colon on the same line counts too
            inline = stripped.split(":", 1)[1].strip()
            if inline:
                req_lines.append(inline)

        elif in_requirement:
            req_lines.append(line.rstrip())

    requirement = "\n".join(req_lines).strip()
    return language, requirement


# Parse on import so everything else can just read the constants
TARGET_LANGUAGE, REQUIREMENT = _parse_requirements_file(REQUIREMENTS_FILE)

# Normalise "auto" to a clear sentinel
if TARGET_LANGUAGE.lower() == "auto":
    TARGET_LANGUAGE = "auto"

# Legacy constant kept for any code that still references it
TARGET_APP_NAME = "GeneratedApp"

print("✅ Configuration loaded successfully!")
print(f"   Output directory : {OUTPUT_DIR}")
print(f"   LLM model        : {LLM_MODEL}")
print(f"   Language         : {TARGET_LANGUAGE}")
print(f"   Requirement      : {REQUIREMENT[:80]}{'...' if len(REQUIREMENT) > 80 else ''}")
