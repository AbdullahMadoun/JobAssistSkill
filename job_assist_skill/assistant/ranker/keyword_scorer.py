"""
Keyword Scorer - Ranks jobs by keyword match score.

Ranks jobs based on keyword_match score from the ANALYZE_ALIGNMENT prompt.
Keyword match is the primary ranking metric (40% weight in overall score).
"""

import re
from typing import Any, Dict, List, Optional, Set


class KeywordScorer:
    """
    Ranks jobs by keyword_match score.
    
    Compares user's skills against job's required/preferred skills
    to calculate a relevance score for ranking.
    
    Usage:
        scorer = KeywordScorer(user_skills=["Python", "AWS", "Docker"])
        score = scorer.score_job(parsed_job)
        
        # Rank multiple jobs
        ranked = scorer.rank_jobs([job1, job2, job3])
    """
    
    def __init__(self, user_skills: Optional[List[str]] = None):
        """
        Initialize KeywordScorer.
        
        Args:
            user_skills: List of user's skills from CV
        """
        self.user_skills = user_skills or []
        self._user_skills_lower = set(s.lower() for s in self.user_skills)
    
    def update_user_skills(self, skills: List[str]) -> None:
        """Update user's skills list."""
        self.user_skills = skills
        self._user_skills_lower = set(s.lower() for s in skills)
    
    def score_job(self, parsed_job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score a single job by keyword match.
        
        Args:
            parsed_job: Parsed job requirements from JobParser
                Expected keys: required_skills, preferred_skills
                
        Returns:
            Dict with:
                - match_score: 0-100 percentage of required keywords matched
                - matched_skills: List of matched required skills
                - missing_skills: List of required skills not found
                - preferred_match_score: 0-100 percentage of preferred keywords matched
                - matched_preferred: List of matched preferred skills
                - missing_preferred: List of preferred skills not found
        """
        required = parsed_job.get("required_skills", []) or []
        preferred = parsed_job.get("preferred_skills", []) or []
        
        required = [r for r in required if isinstance(r, str)] if required else []
        preferred = [p for p in preferred if isinstance(p, str)] if preferred else []
        
        matched_req, missing_req = self._match(required)
        matched_pref, missing_pref = self._match(preferred)
        
        req_score = self._calc_score(len(matched_req), len(required))
        pref_score = self._calc_score(len(matched_pref), len(preferred))
        
        return {
            "match_score": req_score,
            "matched_skills": matched_req,
            "missing_skills": missing_req,
            "preferred_match_score": pref_score,
            "matched_preferred": matched_pref,
            "missing_preferred": missing_pref,
            "total_required": len(required),
            "total_preferred": len(preferred),
        }
    
    def rank_jobs(
        self,
        parsed_jobs: List[Dict[str, Any]],
        sort_by: str = "match_score",
    ) -> List[Dict[str, Any]]:
        """
        Rank multiple jobs by keyword match score.
        
        Args:
            parsed_jobs: List of parsed job requirements
            sort_by: Which score to sort by ('match_score' or 'preferred_match_score')
            
        Returns:
            List of jobs with scores, sorted by match_score descending
        """
        scored = []
        for job in parsed_jobs:
            score = self.score_job(job)
            scored.append({
                "job": job,
                "score": score,
                "match_score": score.get(sort_by, 0),
            })
        
        scored.sort(key=lambda x: x["match_score"], reverse=True)
        
        for i, item in enumerate(scored):
            item["rank"] = i + 1
        
        return scored
    
    def _match(self, keywords: List[str]) -> tuple:
        """
        Match keywords against user skills.
        
        Returns:
            (matched, missing) tuple of skill lists
        """
        matched = []
        missing = []
        
        for kw in keywords:
            kw_lower = kw.lower()
            if any(self._skills_overlap(kw_lower, skill) for skill in self._user_skills_lower):
                matched.append(kw)
            else:
                missing.append(kw)
        
        return matched, missing
    
    def _skills_overlap(self, kw1: str, skill: str) -> bool:
        """Check if keyword and skill overlap."""
        kw_parts = set(re.findall(r'\w+', kw1.lower()))
        skill_parts = set(re.findall(r'\w+', skill.lower()))
        return bool(kw_parts & skill_parts) or kw1 in skill or skill in kw1
    
    def _calc_score(self, matched: int, total: int) -> int:
        """Calculate match percentage score."""
        if total == 0:
            return 0
        return min(100, int((matched / total) * 100))


class JobRanker:
    """
    High-level job ranking with multiple signals.
    
    Ranks jobs using keyword match as primary signal,
    with additional heuristics for seniority, location, etc.
    """
    
    def __init__(
        self,
        user_skills: Optional[List[str]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ):
        self.keyword_scorer = KeywordScorer(user_skills)
        self.preferences = user_preferences or {}
    
    def rank(
        self,
        parsed_jobs: List[Dict[str, Any]],
        user_cv_text: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Rank jobs by overall relevance.
        
        Args:
            parsed_jobs: List of parsed job requirements
            user_cv_text: User's CV text for additional context
            
        Returns:
            Ranked list of jobs with scores
        """
        keyword_ranked = self.keyword_scorer.rank_jobs(parsed_jobs)
        
        for item in keyword_ranked:
            job = item["job"]
            score = item["score"]
            
            seniority_bonus = self._seniority_bonus(job)
            location_bonus = self._location_bonus(job)
            
            item["overall_score"] = (
                score["match_score"] * 0.6 +
                seniority_bonus * 0.2 +
                location_bonus * 0.2
            )
            
            item["breakdown"] = {
                "keyword_score": score["match_score"],
                "seniority_bonus": seniority_bonus,
                "location_bonus": location_bonus,
            }
        
        keyword_ranked.sort(key=lambda x: x["overall_score"], reverse=True)
        
        for i, item in enumerate(keyword_ranked):
            item["rank"] = i + 1
        
        return keyword_ranked
    
    def _seniority_bonus(self, job: Dict[str, Any]) -> int:
        """Calculate seniority match bonus."""
        seniority = job.get("seniority", "").lower()
        if not seniority or seniority == "unknown":
            return 50
        
        return 50
    
    def _location_bonus(self, job: Dict[str, Any]) -> int:
        """Calculate location preference bonus."""
        prefs = self.preferences
        locations = job.get("locations", [])
        
        if not prefs or not locations:
            return 50
        
        preferred = set(l.lower() for l in prefs.get("preferred_locations", []))
        avoided = set(l.lower() for l in prefs.get("avoided_locations", []))
        
        job_locs = set(l.lower() for l in locations if l)
        
        if avoided & job_locs:
            return 0
        
        if preferred & job_locs:
            return 100
        
        return 50


def get_keyword_scorer(user_skills: List[str] = None) -> KeywordScorer:
    """Get a KeywordScorer instance."""
    return KeywordScorer(user_skills)


def get_job_ranker(
    user_skills: List[str] = None,
    user_preferences: Dict[str, Any] = None,
) -> JobRanker:
    """Get a JobRanker instance."""
    return JobRanker(user_skills, user_preferences)
