"""
Feedback Learning System using SQLite.

Stores user approval/rejection decisions and learns preferences
for future job candidate recommendations.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Feedback:
    """Feedback record."""
    id: int
    candidate_id: str
    action: str
    job_keywords: List[str]
    company_name: str
    timestamp: datetime
    edit_notes: Optional[str]


@dataclass
class LearnedPreference:
    """Learned preference from feedback."""
    preference_type: str
    preference_value: str
    weight: float


class FeedbackStore:
    """
    SQLite-backed feedback storage and learning system.

    Usage:
        store = FeedbackStore()
        store.record_feedback(candidate_id="job_123", action="approved", job_keywords=["python"], company_name="Microsoft")
        prefs = store.get_preferences()
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize feedback store.

        Args:
            db_path: Path to SQLite database. Defaults to storage/feedback.db
        """
        if db_path is None:
            repo_root = Path(__file__).resolve().parents[3]
            db_path = repo_root / ".job_assist" / "feedback.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('approved', 'rejected', 'edited')),
                    job_keywords TEXT,
                    company_name TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    edit_notes TEXT,
                    UNIQUE(candidate_id)
                );

                CREATE TABLE IF NOT EXISTS learned_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    preference_type TEXT NOT NULL,
                    preference_value TEXT NOT NULL,
                    weight REAL DEFAULT 0.0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(preference_type, preference_value)
                );

                CREATE TABLE IF NOT EXISTS job_context (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id TEXT NOT NULL UNIQUE,
                    job_title TEXT,
                    company TEXT,
                    location TEXT,
                    source TEXT,
                    raw_data TEXT,
                    collected_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_feedback_action ON feedback(action);
                CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp);
                CREATE INDEX IF NOT EXISTS idx_preferences_type ON learned_preferences(preference_type);
            """)

    def record_feedback(
        self,
        candidate_id: str,
        action: str,
        job_keywords: Optional[List[str]] = None,
        company_name: str = "",
        edit_notes: str = "",
    ) -> int:
        """
        Record feedback for a candidate.

        Args:
            candidate_id: Unique identifier for the job candidate
            action: 'approved', 'rejected', or 'edited'
            job_keywords: List of job keywords from the posting
            company_name: Company name
            edit_notes: Optional notes about edits made

        Returns:
            Feedback record ID
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO feedback
                (candidate_id, action, job_keywords, company_name, edit_notes, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                candidate_id,
                action,
                json.dumps(job_keywords or []),
                company_name,
                edit_notes,
                datetime.now().isoformat(),
            ))
            conn.commit()

            self._update_preferences(conn, candidate_id, action, job_keywords, company_name)

            return cursor.lastrowid

    def _update_preferences(
        self,
        conn: sqlite3.Connection,
        candidate_id: str,
        action: str,
        job_keywords: Optional[List[str]],
        company_name: str,
    ) -> None:
        """Update learned preferences based on feedback."""
        if action == 'rejected':
            delta = -1.0
        elif action == 'approved':
            delta = 1.0
        else:
            delta = 0.5

        if job_keywords:
            for keyword in job_keywords:
                self._update_single_preference(conn, 'role', keyword.lower(), delta)

        if company_name:
            self._update_single_preference(conn, 'company', company_name.lower(), delta)

    def _update_single_preference(
        self,
        conn: sqlite3.Connection,
        pref_type: str,
        value: str,
        delta: float,
    ) -> None:
        """Update a single preference weight."""
        conn.execute("""
            INSERT INTO learned_preferences (preference_type, preference_value, weight, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(preference_type, preference_value)
            DO UPDATE SET
                weight = MAX(0.0, weight + ?),
                updated_at = ?
        """, (pref_type, value, abs(delta), datetime.now().isoformat(), delta, datetime.now().isoformat()))

    def get_preferences(
        self,
        preference_type: Optional[str] = None,
        min_weight: float = 0.0,
    ) -> List[LearnedPreference]:
        """
        Get learned preferences.

        Args:
            preference_type: Filter by type ('role', 'company', 'location')
            min_weight: Minimum weight threshold

        Returns:
            List of LearnedPreference objects
        """
        with self._get_connection() as conn:
            query = "SELECT * FROM learned_preferences WHERE weight >= ?"
            params: List[Any] = [min_weight]

            if preference_type:
                query += " AND preference_type = ?"
                params.append(preference_type)

            query += " ORDER BY weight DESC"

            rows = conn.execute(query, params).fetchall()

            return [
                LearnedPreference(
                    preference_type=row['preference_type'],
                    preference_value=row['preference_value'],
                    weight=row['weight'],
                )
                for row in rows
            ]

    def get_preferred_roles(self, min_weight: float = 0.5) -> List[str]:
        """Get list of preferred roles sorted by weight."""
        prefs = self.get_preferences(preference_type='role', min_weight=min_weight)
        return [p.preference_value for p in prefs]

    def get_preferred_companies(self, min_weight: float = 0.5) -> List[str]:
        """Get list of preferred companies sorted by weight."""
        prefs = self.get_preferences(preference_type='company', min_weight=min_weight)
        return [p.preference_value for p in prefs]

    def is_candidate_approved(self, candidate_id: str) -> bool:
        """Check if a candidate was previously approved."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT action FROM feedback WHERE candidate_id = ? AND action = 'approved'",
                (candidate_id,)
            ).fetchone()
            return row is not None

    def is_candidate_rejected(self, candidate_id: str) -> bool:
        """Check if a candidate was previously rejected."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT action FROM feedback WHERE candidate_id = ? AND action = 'rejected'",
                (candidate_id,)
            ).fetchone()
            return row is not None

    def get_recent_feedback(self, limit: int = 50) -> List[Feedback]:
        """Get recent feedback records."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM feedback ORDER BY timestamp DESC LIMIT ?
            """, (limit,)).fetchall()

            return [
                Feedback(
                    id=row['id'],
                    candidate_id=row['candidate_id'],
                    action=row['action'],
                    job_keywords=json.loads(row['job_keywords'] or '[]'),
                    company_name=row['company_name'] or '',
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    edit_notes=row['edit_notes'],
                )
                for row in rows
            ]

    def store_job_context(
        self,
        candidate_id: str,
        job_title: str = "",
        company: str = "",
        location: str = "",
        source: str = "",
        raw_data: Optional[Dict] = None,
    ) -> None:
        """Store job context data for a candidate."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO job_context
                (candidate_id, job_title, company, location, source, raw_data, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                candidate_id,
                job_title,
                company,
                location,
                source,
                json.dumps(raw_data or {}),
                datetime.now().isoformat(),
            ))
            conn.commit()

    def get_job_context(self, candidate_id: str) -> Optional[Dict]:
        """Get job context for a candidate."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM job_context WHERE candidate_id = ?",
                (candidate_id,)
            ).fetchone()

            if row:
                return {
                    'job_title': row['job_title'],
                    'company': row['company'],
                    'location': row['location'],
                    'source': row['source'],
                    'raw_data': json.loads(row['raw_data'] or '{}'),
                    'collected_at': row['collected_at'],
                }
            return None

    def get_statistics(self) -> Dict:
        """Get feedback statistics."""
        with self._get_connection() as conn:
            stats = {}

            total = conn.execute("SELECT COUNT(*) as count FROM feedback").fetchone()['count']
            approved = conn.execute("SELECT COUNT(*) as count FROM feedback WHERE action = 'approved'").fetchone()['count']
            rejected = conn.execute("SELECT COUNT(*) as count FROM feedback WHERE action = 'rejected'").fetchone()['count']
            edited = conn.execute("SELECT COUNT(*) as count FROM feedback WHERE action = 'edited'").fetchone()['count']

            stats['total_feedback'] = total
            stats['approved'] = approved
            stats['rejected'] = rejected
            stats['edited'] = edited
            stats['approval_rate'] = round(approved / total * 100, 1) if total > 0 else 0

            return stats


_default_store: Optional[FeedbackStore] = None


def get_feedback_store() -> FeedbackStore:
    """Get singleton feedback store instance."""
    global _default_store
    if _default_store is None:
        _default_store = FeedbackStore()
    return _default_store
