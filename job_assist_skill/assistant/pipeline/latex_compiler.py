"""
LaTeX Compiler with one-page enforcement.

Compiles LaTeX to PDF and enforces one-page limit through
progressive strategies if needed.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class LaTeXCompiler:
    """
    Compiles LaTeX documents to PDF with one-page enforcement.

    Strategies for reducing page count (in order):
    1. Standard compilation
    2. Reduce spacing (parskip, itemsep adjustments)
    3. Reduce font size (11pt → 10pt → 9pt)
    4. Adjust geometry (margins)
    5. Condense bullet text

    Usage:
        compiler = LaTeXCompiler()
        result = compiler.compile_one_page(latex_content, "output.pdf")
    """

    def __init__(self, latex_cmd: str = "pdflatex", max_attempts: int = 4):
        """
        Initialize LaTeX compiler.

        Args:
            latex_cmd: LaTeX command to use (pdflatex, xelatex, lualatex)
            max_attempts: Maximum compilation attempts for one-page enforcement
        """
        self.latex_cmd = latex_cmd
        self.max_attempts = max_attempts
        self._check_latex_installation()

    def _check_latex_installation(self) -> bool:
        """Check if LaTeX is installed."""
        try:
            result = subprocess.run(
                [self.latex_cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                logger.info(f"LaTeX found: {version_line}")
                return True
        except FileNotFoundError:
            logger.warning(f"{self.latex_cmd} not found. Install a LaTeX distribution.")
        except Exception as e:
            logger.warning(f"Error checking LaTeX installation: {e}")
        return False

    def compile_one_page(
        self,
        latex_content: str,
        output_path: str,
        one_page_strict: bool = True,
    ) -> Dict:
        """
        Compile LaTeX to PDF with one-page enforcement.

        Args:
            latex_content: LaTeX source code
            output_path: Output PDF path
            one_page_strict: If True, keep trying strategies until one page

        Returns:
            Dict with keys:
                - success: bool
                - pages: int (number of pages in output)
                - pdf_path: str (path to output PDF)
                - issues: List[str] (any warnings)
                - strategy_used: str (which reduction strategy worked)
        """
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        result = self._compile_latex(latex_content, output_path)
        if not result['success']:
            return result

        pages = self._get_page_count(output_path)
        result['pages'] = pages
        result['pdf_path'] = output_path

        if pages == 1:
            result['strategy_used'] = 'none'
            return result

        if not one_page_strict:
            result['issues'] = result.get('issues', [])
            result['issues'].append(f"CV is {pages} pages (expected 1)")
            return result

        strategies = [
            self._create_tighter_spacing_version,
            self._create_smaller_font_version,
            self._create_tighter_margins_version,
            self._create_condensed_version,
        ]

        for i, strategy_fn in enumerate(strategies):
            if i >= self.max_attempts - 1:
                break

            logger.info(f"Attempting one-page strategy {i + 1}: {strategy_fn.__name__}")

            new_latex = strategy_fn(latex_content)
            if new_latex == latex_content:
                continue

            temp_output = output_path.replace('.pdf', f'_attempt{i+1}.pdf')
            result = self._compile_latex(new_latex, temp_output)

            if result['success']:
                pages = self._get_page_count(temp_output)
                if pages == 1:
                    os.replace(temp_output, output_path)
                    result['pages'] = 1
                    result['pdf_path'] = output_path
                    result['strategy_used'] = strategy_fn.__name__
                    result['issues'] = result.get('issues', [])
                    result['issues'].append(f"Reduced to 1 page using {strategy_fn.__name__}")
                    return result
                else:
                    try:
                        os.remove(temp_output)
                    except:
                        pass

        result['pages'] = self._get_page_count(output_path)
        result['issues'] = result.get('issues', [])
        result['issues'].append(f"Could not reduce to 1 page (final: {result['pages']} pages)")
        return result

    def compile(
        self,
        latex_content: str,
        output_path: str,
        runs: int = 2,
    ) -> Dict:
        """
        Compile LaTeX to PDF (standard compilation).

        Args:
            latex_content: LaTeX source code
            output_path: Output PDF path
            runs: Number of compilation runs (2 for proper TOC, etc.)

        Returns:
            Dict with success, output path, and any issues
        """
        return self._compile_latex(latex_content, output_path, runs=runs)

    def _compile_latex(
        self,
        latex_content: str,
        output_path: str,
        runs: int = 2,
    ) -> Dict:
        """Run LaTeX compilation."""
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = os.path.join(tmpdir, 'document.tex')
            Path(tex_path).write_text(latex_content, encoding='utf-8')

            for run in range(runs):
                try:
                    result = subprocess.run(
                        [self.latex_cmd, '-interaction=nonstopmode',
                         '-output-directory', tmpdir, tex_path],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )

                    if result.returncode != 0:
                        errors = self._extract_latex_errors(result.stderr)
                        return {
                            'success': False,
                            'pdf_path': None,
                            'pages': 0,
                            'issues': [f"LaTeX error (run {run + 1}): {e}" for e in errors],
                        }

                except subprocess.TimeoutExpired:
                    return {
                        'success': False,
                        'pdf_path': None,
                        'pages': 0,
                        'issues': ['LaTeX compilation timed out'],
                    }
                except FileNotFoundError:
                    return {
                        'success': False,
                        'pdf_path': None,
                        'pages': 0,
                        'issues': [f'{self.latex_cmd} not found. Install LaTeX.'],
                    }

            pdf_path = os.path.join(tmpdir, 'document.pdf')
            if os.path.exists(pdf_path):
                import shutil
                shutil.copy2(pdf_path, output_path)
                return {
                    'success': True,
                    'pdf_path': output_path,
                    'pages': self._get_page_count(output_path),
                    'issues': [],
                }
            else:
                return {
                    'success': False,
                    'pdf_path': None,
                    'pages': 0,
                    'issues': ['PDF was not generated'],
                }

    def _get_page_count(self, pdf_path: str) -> int:
        """Get number of pages in PDF."""
        try:
            import PyPDF2
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                return len(reader.pages)
        except ImportError:
            try:
                result = subprocess.run(
                    ['pdfinfo', pdf_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    match = re.search(r'Pages:\s*(\d+)', result.stdout)
                    if match:
                        return int(match.group(1))
            except:
                pass
        except Exception as e:
            logger.debug(f"Error getting page count: {e}")
        return 1

    def _extract_latex_errors(self, stderr: str) -> List[str]:
        """Extract meaningful errors from LaTeX output."""
        errors = []
        for line in stderr.split('\n'):
            if 'Error' in line or 'error' in line or '!' in line:
                cleaned = line.strip()
                if cleaned and len(cleaned) < 200:
                    errors.append(cleaned)
        return errors[:5]

    def _create_tighter_spacing_version(self, latex: str) -> str:
        """Reduce spacing between elements."""
        modifications = [
            (r'\\setlength{\\parskip}{2pt}', r'\\setlength{\\parskip}{0pt}'),
            (r'\\setlist{noitemsep, topsep=\\d+pt', r'\\setlist{noitemsep, topsep=0pt'),
            (r'\\titlespacing\\\*{\\section}{[^}]*}',
             r'\\titlespacing*{\\section}{0pt}{2pt plus 1pt minus 1pt}{1pt}'),
        ]

        new_latex = latex
        for pattern, replacement in modifications:
            new_latex = re.sub(pattern, replacement, new_latex)

        if new_latex == latex:
            new_latex = latex + '\n\\usepackage[parfill=0pt]{parskip}'

        return new_latex

    def _create_smaller_font_version(self, latex: str) -> str:
        """Reduce font size."""
        modifications = [
            (r'\\documentclass\[a4paper,10pt\]', r'\\documentclass[a4paper,9pt]'),
            (r'\\documentclass\[a4paper,11pt\]', r'\\documentclass[a4paper,10pt]'),
            (r'{\\fontsize\{20pt\}', r'{\\fontsize{18pt}'),
            (r'{\\fontsize\{10\.5pt\}', r'{\\fontsize{9pt}'),
            (r'\\large\\bfseries', r'\\normalsize\\bfseries'),
        ]

        new_latex = latex
        for pattern, replacement in modifications:
            new_latex = re.sub(pattern, replacement, new_latex)

        return new_latex

    def _create_tighter_margins_version(self, latex: str) -> str:
        """Reduce page margins."""
        if r'\usepackage[margin=0.4in' in latex:
            return latex.replace(r'margin=0.4in', r'margin=0.3in')
        elif r'\usepackage[margin=' in latex:
            return re.sub(r'margin=[\d.]+in', r'margin=0.35in', latex)
        else:
            geometry_match = re.search(r'(\\usepackage\[)([^\]]+)(\]{geometry})', latex)
            if geometry_match:
                existing = geometry_match.group(2)
                new_options = re.sub(r'margin=[\d.]+in', r'margin=0.3in', existing)
                if 'margin' not in new_options:
                    new_options += ',margin=0.3in'
                return latex.replace(geometry_match.group(0), f'{geometry_match.group(1)}{new_options}]{geometry_match.group(3)}')
        return latex

    def _create_condensed_version(self, latex: str) -> str:
        """Condense content - reduce bullet text length."""
        def shorten_item(match):
            item_text = match.group(1)
            sentences = item_text.split('. ')
            if len(sentences) > 2:
                item_text = '. '.join(sentences[:2])
                if not item_text.endswith('.'):
                    item_text += '.'
            return f'\\item {item_text}'

        new_latex = re.sub(r'\\item\s+([^\n]+)', shorten_item, latex)
        return new_latex


_default_compiler: Optional[LaTeXCompiler] = None


def get_compiler() -> LaTeXCompiler:
    """Get singleton compiler instance."""
    global _default_compiler
    if _default_compiler is None:
        _default_compiler = LaTeXCompiler()
    return _default_compiler
