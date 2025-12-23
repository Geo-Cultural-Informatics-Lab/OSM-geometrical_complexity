"""
Resume Manager - Unified Progress Tracking

This module provides a unified interface for tracking analysis progress
and enabling resume capability across all analysis types.
"""

import os
import json
import pandas as pd
from datetime import datetime


class ResumeManager:
    """Unified progress tracking for all analysis types."""

    def __init__(self, output_dir, task_id):
        """
        Initialize resume manager.

        Args:
            output_dir: Directory to store status file
            task_id: Unique identifier for this task
        """
        self.output_dir = output_dir
        self.task_id = task_id
        self.status_file = os.path.join(output_dir, f".status_{task_id}.json")
        self.status = self._load()

    def _load(self):
        """Load existing progress from status file."""
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            'completed': [],
            'failed': [],
            'progress': 0,
            'total': 0,
            'timestamp': datetime.now().isoformat()
        }

    def _save(self):
        """Persist current status to file."""
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            self.status['timestamp'] = datetime.now().isoformat()

            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(self.status, f, indent=2)
        except Exception:
            pass  # Silent fail for status save

    def set_total(self, total):
        """Set total number of items to process."""
        self.status['total'] = total
        self._update_progress()

    def mark_completed(self, item_id):
        """Mark item as completed."""
        if item_id not in self.status['completed']:
            self.status['completed'].append(item_id)
            self._update_progress()

    def mark_failed(self, item_id, error=None):
        """Mark item as failed."""
        failure_record = {'id': item_id}
        if error:
            failure_record['error'] = str(error)

        if failure_record not in self.status['failed']:
            self.status['failed'].append(failure_record)
            self._save()

    def is_completed(self, item_id):
        """Check if item already completed."""
        return item_id in self.status['completed']

    def _update_progress(self):
        """Update progress percentage and save."""
        if self.status['total'] > 0:
            self.status['progress'] = len(self.status['completed']) / self.status['total']
        self._save()

    def get_progress(self):
        """Get completion percentage (0-1)."""
        return self.status.get('progress', 0)

    def get_completed_count(self):
        """Get number of completed items."""
        return len(self.status['completed'])

    def get_failed_count(self):
        """Get number of failed items."""
        return len(self.status['failed'])

    def get_summary(self):
        """Get summary dict of progress."""
        return {
            'total': self.status['total'],
            'completed': len(self.status['completed']),
            'failed': len(self.status['failed']),
            'progress': self.status['progress'],
            'timestamp': self.status['timestamp']
        }

    def cleanup(self):
        """Remove status file after successful completion."""
        if os.path.exists(self.status_file):
            try:
                os.remove(self.status_file)
            except Exception:
                pass
