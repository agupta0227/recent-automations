import re
from pathlib import Path
from typing import Dict
from datetime import datetime

class CodeFormatterImproved:
    """
    Extracts code blocks from LLM output and saves them as files.
    Language-agnostic: works with any language the LLM produces.
    """

    # Generic code indicators that are language-agnostic
    GENERIC_INDICATORS = [
        # structure keywords
        'def ', 'class ', 'function ', 'func ', 'sub ', 'void ',
        'public ', 'private ', 'protected ', 'import ', 'require(',
        'include ', 'package ', 'module ',
        # common patterns
        'return ', 'if ', 'for ', 'while ', 'switch ', 'case ',
        '() {', '() =>', ') {', ') =',
        # string/comment markers
        '//', '/*', '#!', '"""', "'''",
    ]

    # Things that indicate the block is a template placeholder, not real code
    TEMPLATE_MARKERS = ['###', 'PLACEHOLDER', '[full code here]', '[complete']

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.versions   = []

    def extract_code_blocks(self, text: str) -> Dict[str, str]:
        """
        Extract code blocks from LLM output.

        Tries five patterns in order of preference, stopping at the first that yields results.
        This aggressive approach handles the fact that small models like gemma2:2b often
        ignore the requested output format and produce code in their own style.

          1. === filename.ext === separator  (our preferred format)
          2. ``` fenced blocks with a language tag  (e.g. ```python)
          3. ``` fenced blocks without a language tag
          4. Indented blocks that look like code (4+ spaces or tab-indented)
          5. Whole-text fallback — if the entire response looks like code
        """
        code_blocks = {}

        # ── Pattern 1: === filename.ext === ─────────────────────────
        pattern1 = r'===\s*([^\n=]+?)\s*===\s*\n(.*?)(?====|\Z)'
        for match in re.finditer(pattern1, text, re.DOTALL):
            filename = match.group(1).strip()
            code     = match.group(2).strip()
            if self._is_valid_code(code) and self._looks_like_filename(filename):
                code_blocks[filename] = code

        if code_blocks:
            return code_blocks

        # ── Pattern 2: ```lang fenced blocks ────────────────────────
        pattern2 = r'```([a-zA-Z][a-zA-Z0-9]*)\s*\n(.*?)```'
        for i, match in enumerate(re.finditer(pattern2, text, re.DOTALL)):
            lang = match.group(1).strip()
            code = match.group(2).strip()
            if self._is_valid_code(code):
                ext      = self._detect_extension(code) or f'.{lang}'
                filename = f'generated_{i}{ext}'
                code_blocks[filename] = code

        if code_blocks:
            return code_blocks

        # ── Pattern 3: ``` fenced blocks (no language tag) ──────────
        pattern3 = r'```\s*\n(.*?)```'
        for i, match in enumerate(re.finditer(pattern3, text, re.DOTALL)):
            code = match.group(1).strip()
            if self._is_valid_code(code):
                ext      = self._detect_extension(code)
                filename = f'generated_{i}{ext}'
                code_blocks[filename] = code

        if code_blocks:
            return code_blocks

        # ── Pattern 4: strip prose and extract code-looking lines ───
        # Split on blank lines, keep chunks that are mostly code
        chunks = re.split(r'\n{2,}', text)
        code_chunks = []
        for chunk in chunks:
            lines = chunk.strip().splitlines()
            if len(lines) < 3:
                continue
            # Count lines that start with typical code characters
            code_line_count = sum(
                1 for l in lines
                if l.startswith(('    ', '\t', 'def ', 'class ', 'import ',
                                  'function ', 'public ', 'private ', '//', '#',
                                  'const ', 'let ', 'var ', 'return ', 'if ',
                                  'for ', 'while ', '}', '{'))
            )
            if code_line_count / len(lines) > 0.4:  # >40% code-like lines
                code_chunks.append(chunk.strip())

        if code_chunks:
            combined = '\n\n'.join(code_chunks)
            if self._is_valid_code(combined):
                ext = self._detect_extension(combined)
                code_blocks[f'generated{ext}'] = combined
                return code_blocks

        # ── Pattern 5: whole-text fallback ──────────────────────────
        stripped = text.strip()
        if self._is_valid_code(stripped):
            ext = self._detect_extension(stripped)
            code_blocks[f'generated{ext}'] = stripped

        return code_blocks

    def _looks_like_filename(self, text: str) -> bool:
        """Basic check — does the text look like a filename with an extension?"""
        return bool(re.match(r'^[\w\-. ]+\.\w{1,10}$', text.strip()))

    def _is_valid_code(self, code: str) -> bool:
        """Return True if the text looks like real code rather than prose or a template."""
        if len(code) < 30:
            return False
        if any(marker in code for marker in self.TEMPLATE_MARKERS):
            return False
        lower = code.lower()
        return any(ind.lower() in lower for ind in self.GENERIC_INDICATORS)

    def _detect_extension(self, code: str) -> str:
        """
        Guess a file extension from code content.
        Returns '.txt' as a safe fallback if nothing matches.
        """
        lower = code.lower()
        checks = [
            ('.py',   ['def ',   'import ', 'print(', '#!/usr/bin/env python']),
            ('.js',   ['function ', 'const ', 'let ', 'var ', '=>', 'require(']),
            ('.ts',   ['interface ', ': string', ': number', ': boolean', 'typescript']),
            ('.java', ['public class', 'system.out', 'void main']),
            ('.cs',   ['using system', 'namespace ', 'console.writeline']),
            ('.go',   ['package main', 'func main()', 'fmt.println']),
            ('.rb',   ['def ', 'puts ', 'require ', 'end\n']),
            ('.rs',   ['fn main()', 'println!', 'let mut ']),
            ('.cpp',  ['#include', 'std::', 'cout <<']),
            ('.c',    ['#include', 'printf(', 'int main(']),
            ('.vb',   ['public class', 'private sub', 'end class', 'end sub']),
            ('.html', ['<!doctype', '<html', '<body', '<div']),
            ('.css',  ['{', 'margin:', 'padding:', 'color:']),
            ('.sql',  ['select ', 'insert ', 'create table', 'drop ']),
            ('.sh',   ['#!/bin/bash', 'echo ', 'fi\n', 'done\n']),
        ]
        for ext, signals in checks:
            if any(s in lower for s in signals):
                return ext
        return '.txt'

    def save_code_file(self, code: str, version: int, filename: str = 'generated.txt'):
        """Save code to output dir with a version header comment."""
        ext     = Path(filename).suffix.lower()
        comment = self._comment_style(ext)
        header  = (
            f"{comment} {'='*72}\n"
            f"{comment} FILE    : {filename}\n"
            f"{comment} VERSION : {version}\n"
            f"{comment} CREATED : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{comment} {'='*72}\n\n"
        )
        full_code   = header + code
        output_file = self.output_dir / filename
        output_file.write_text(full_code, encoding='utf-8')

        # Save versioned copy
        stem         = Path(filename).stem
        version_file = self.output_dir / 'versions' / f'{stem}_v{version:02d}{ext}'
        version_file.parent.mkdir(exist_ok=True)
        version_file.write_text(full_code, encoding='utf-8')

        self.versions.append((version, filename, len(code)))
        return str(output_file)

    def _comment_style(self, ext: str) -> str:
        """Return the single-line comment prefix for the given extension."""
        hash_langs  = {'.py', '.rb', '.sh', '.r', '.pl', '.yaml', '.yml'}
        slash_langs = {'.js', '.ts', '.java', '.cs', '.go', '.rs', '.cpp',
                       '.c', '.swift', '.kt', '.scala', '.php'}
        if ext in hash_langs:
            return '#'
        if ext in slash_langs:
            return '//'
        if ext == '.vb':
            return "'"
        if ext in {'.html', '.xml'}:
            return '<!--'
        if ext == '.sql':
            return '--'
        return '#'   # safe default
