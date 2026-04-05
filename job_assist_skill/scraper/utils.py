"""
LinkedIn Scraper Utilities - Metadata Cleaning & Identity Extraction.

Provides a centralized MetadataCleaner to unify:
- Author name extraction from URL slugs (/in/, /posts/, /pub/)
- Organization isolation from noisy job headlines (e.g. "Recruiter at Mozn")
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class MetadataCleaner:
    """
    Centralized utility for LinkedIn identity and organization cleaning.
    """

    @staticmethod
    def clean_company_name(text: str) -> str:
        """
        Isolate the organization name from a job headline or description.
        
        Examples:
        - "Software Engineer at Mozn" -> "Mozn"
        - "Recruiter @ Qualcomm • 1mo" -> "Qualcomm"
        - "Hiring for Whitehat AI" -> "Whitehat AI"
        """
        if not text:
            return ""

        co = text.strip()

        # Phase 1: Smart Split (isolate organization from title)
        # Look for " at ", " @ ", or " for " (case-insensitive)
        if re.search(r'\s+at\s+', co, re.I):
            co = re.split(r'\s+at\s+', co, flags=re.I)[-1]
        elif ' @ ' in co:
            co = co.split(' @ ')[-1]
        elif re.search(r'\s+for\s+', co, re.I):
            co = re.split(r'\s+for\s+', co, flags=re.I)[-1]

        # Phase 2: Filter Social Noise
        # Remove connection/follower count (e.g., "400 mutual connections")
        co = re.sub(r'\d+\s*(mutual|follower|subscriber|connection)[s]?\b.*', '', co, flags=re.I)

        # Phase 3: Punctuation Cleanup
        # Split by typical LinkedIn list/separator chars
        co = re.split(r'[·•\-\(\)\|\,]', co)[0]

        return co.strip()

    @staticmethod
    def extract_name_from_url(url: str) -> str:
        """
        Extract a human-readable name from a LinkedIn profile or post URL slug.
        
        Patterns supported: /in/, /pub/, /comm/, /posts/
        """
        if not url:
            return ""

        # Pattern: /in|pub|comm|posts/slug
        match = re.search(r'/(in|pub|comm|posts)/([a-zA-Z0-9_-]+)/?', url)
        if not match:
            return ""

        username = match.group(2)
        if username in ['in', 'posts', 'pub', 'comm']:
            return ""

        # Step 1: Strip numeric tracking IDs (e.g., -787b62358)
        # LinkedIn often appends a dash then a hex/dec ID
        username = re.sub(r'-[0-9a-f]{5,15}/?$', '', username)
        username = re.sub(r'-[0-9]{5,15}/?$', '', username)

        # Step 2: Handle post slugs (e.g., hiring-ai-engineer-riyadh_...)
        # If it looks like a generic job post slug, we might not want to treat it as a name
        if 'hiring-' in username.lower() or 'now-' in username.lower():
            # For posts, the name is usually BEFORE the underscore or hiring keyword
            username = re.split(r'[_-]hiring', username, flags=re.I)[0]

        # Step 3: Format parts
        parts = username.split('-')
        # Filter out very short or purely numeric parts
        name_parts = [p for p in parts if len(p) > 1 and not p.isdigit()]

        if name_parts:
            return ' '.join(name_parts).title()
        
        return username.replace('-', ' ').replace('_', ' ').title()

    @staticmethod
    def is_generic_author(name: str) -> bool:
        """Check if an author name is a generic placeholder."""
        if not name:
            return True
        generic = [
            'linkedin member', 'recruiter', 'hiring manager', 'founder', 
            'ceo', 'cto', 'startup', 'team', 'careers'
        ]
        return name.lower().strip() in generic or len(name) < 3
