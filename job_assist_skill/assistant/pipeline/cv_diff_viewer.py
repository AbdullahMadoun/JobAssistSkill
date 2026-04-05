"""
CV Diff Viewer - Shows changes between original and tailored CV.

Displays only CRITICAL changes for user approval.
Recommended and optional changes are hidden to avoid overwhelming the user.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class DiffChange:
    """A single change in the CV diff."""
    section: str
    original: str
    edited: str
    importance: str  # "critical", "recommended", "optional"
    reason: str
    keywords: List[str]


class CVDiffViewer:
    """
    Displays CV changes for user approval.
    
    Shows only CRITICAL changes - hides recommended/optional to avoid overwhelming.
    
    Usage:
        viewer = CVDiffViewer()
        diff = viewer.show_diff(
            original_cv=cv_latex,
            tailored_cv=tailored_latex,
            changes=all_changes,
            job_title="Software Engineer",
            company="Microsoft",
            score_before=72,
            score_after=89,
        )
        
        viewer.print_diff(diff)
        
        user_approved = viewer.ask_approval()
    """
    
    def __init__(self, show_critical_only: bool = True):
        """
        Initialize CVDiffViewer.
        
        Args:
            show_critical_only: If True, only show critical changes
        """
        self.show_critical_only = show_critical_only
    
    def show_diff(
        self,
        original_cv: str,
        tailored_cv: str,
        changes: List[Dict[str, Any]],
        job_title: str = "",
        company: str = "",
        score_before: int = 0,
        score_after: int = 0,
    ) -> Dict[str, Any]:
        """
        Prepare diff display data.
        
        Args:
            original_cv: Original CV LaTeX
            tailored_cv: Tailored CV LaTeX
            changes: List of change dicts from REPLACE prompt
            job_title: Job title for display
            company: Company name for display
            score_before: Score before tailoring
            score_after: Predicted score after tailoring
            
        Returns:
            Dict with diff data for display
        """
        critical = []
        recommended = []
        optional = []
        
        for change in changes:
            importance = change.get("importance", "recommended").lower()
            change_type = change.get("change_type", "keep")
            
            if change_type == "keep":
                continue
            
            diff = DiffChange(
                section=change.get("section_name", "Unknown"),
                original=change.get("original_text", ""),
                edited=change.get("edited_text", ""),
                importance=importance,
                reason=change.get("reason", ""),
                keywords=change.get("target_keywords", []),
            )
            
            if importance == "critical":
                critical.append(diff)
            elif importance == "recommended":
                recommended.append(diff)
            else:
                optional.append(diff)
        
        return {
            "job_title": job_title,
            "company": company,
            "score_before": score_before,
            "score_after": score_after,
            "score_delta": score_after - score_before,
            "critical_changes": critical,
            "recommended_changes": recommended,
            "optional_changes": optional,
            "total_critical": len(critical),
            "total_recommended": len(recommended),
            "original_cv": original_cv,
            "tailored_cv": tailored_cv,
        }
    
    def print_diff(self, diff: Dict[str, Any]) -> None:
        """
        Print the diff to console.
        
        Args:
            diff: Diff data from show_diff()
        """
        print()
        print("=" * 70)
        print(f"  CV TAILORING: {diff['job_title']} @ {diff['company']}")
        print("=" * 70)
        
        if diff["score_delta"] != 0:
            score_str = f"{diff['score_before']} → {diff['score_after']} (+{diff['score_delta']})"
        else:
            score_str = f"{diff['score_before']}"
        
        print(f"\nKeyword Match Score: {score_str}")
        
        print()
        
        if diff["critical_changes"]:
            print(f"CRITICAL CHANGES ({diff['total_critical']}):")
            print("-" * 70)
            
            for i, change in enumerate(diff["critical_changes"], 1):
                print(f"\n{i}. [{change.section}]")
                print(f"   ORIG: {self._truncate(change.original, 60)}")
                print(f"   NEW:  {self._truncate(change.edited, 60)}")
                if change.reason:
                    print(f"   WHY:  {change.reason}")
                if change.keywords:
                    print(f"   KEYWORDS: {', '.join(change.keywords)}")
            
            print()
        
        if self.show_critical_only:
            print("(Recommended and optional changes hidden)")
            print()
        
        print("-" * 70)
    
    def ask_approval(self, prompt: str = "Approve changes? (y/n/edit): ") -> str:
        """
        Ask user for approval.
        
        Args:
            prompt: Prompt to display
            
        Returns:
            User response: "y", "n", or "edit"
        """
        while True:
            response = input(prompt).strip().lower()
            if response in ["y", "yes", "n", "no", "edit"]:
                return response
            print("Please enter y, n, or edit")
    
    def format_for_llm(self, diff: Dict[str, Any]) -> str:
        """
        Format diff for LLM context.
        
        Args:
            diff: Diff data from show_diff()
            
        Returns:
            String representation of critical changes
        """
        lines = []
        lines.append(f"CV Tailoring for {diff['job_title']} @ {diff['company']}")
        lines.append(f"Score: {diff['score_before']} → {diff['score_after']}")
        lines.append("")
        
        if diff["critical_changes"]:
            lines.append(f"Critical Changes ({diff['total_critical']}):")
            for change in diff["critical_changes"]:
                lines.append(f"  - {change.section}: {change.original[:50]}...")
                lines.append(f"    → {change.edited[:50]}...")
        
        return "\n".join(lines)
    
    def get_approved_changes(
        self,
        diff: Dict[str, Any],
        user_response: str,
        edited_indices: List[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get list of changes to apply based on user response.
        
        Args:
            diff: Diff data from show_diff()
            user_response: User response from ask_approval()
            edited_indices: Indices of changes user edited (1-indexed)
            
        Returns:
            List of change dicts to apply
        """
        if user_response in ["n", "no"]:
            return []
        
        if user_response in ["y", "yes"]:
            return [
                {
                    "original_text": c.original,
                    "edited_text": c.edited,
                    "section_name": c.section,
                }
                for c in diff["critical_changes"]
            ]
        
        if user_response == "edit" and edited_indices:
            selected = []
            for i in edited_indices:
                if 0 < i <= len(diff["critical_changes"]):
                    change = diff["critical_changes"][i - 1]
                    selected.append({
                        "original_text": change.original,
                        "edited_text": change.edited,
                        "section_name": change.section,
                    })
            return selected
        
        return []
    
    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text with ellipsis."""
        if not text:
            return "(empty)"
        text = text.replace("\\n", " ").replace("\\item", "").replace("\\", "")
        if len(text) > max_len:
            return text[:max_len - 3] + "..."
        return text


def create_diff_viewer() -> CVDiffViewer:
    """Create a default CVDiffViewer instance."""
    return CVDiffViewer()
