import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literature_search import sessions


class SessionTests(unittest.TestCase):
    def test_first_save_load_and_screening_update(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "new-session-root"
            database = root / "sessions.sqlite3"
            result = {
                "created_at": "2026-07-17T00:00:00+00:00",
                "input_summary": "监管沙盒与创新的关系",
                "source_ids": ["openalex"],
                "records": [{
                    "record_id": "paper-1", "title": "Sandbox Innovation",
                    "open_access_pdf_url": "https://example.org/paper.pdf",
                    "screening_status": "unscreened", "screening_reason": None,
                }],
                "search_parameters": {
                    "research_question": "监管沙盒与创新的关系",
                    "query": "regulatory sandbox innovation",
                    "mode": "systematic", "ranking": "combined",
                },
            }
            parameters = result["search_parameters"]
            with patch.object(sessions, "SESSION_ROOT", root), patch.object(sessions, "SESSION_DB", database):
                session_id = sessions.save_session(result, parameters)
                self.assertTrue((root / f"{session_id}.json").exists())
                self.assertEqual(sessions.list_sessions()[0]["open_pdf_count"], 1)
                changed = sessions.update_screening(session_id, "paper-1", "include", "Direct evidence")
                self.assertEqual(changed["screening_status"], "include")
                loaded = sessions.load_session(session_id)
                self.assertEqual(loaded["records"][0]["screening_reason"], "Direct evidence")
                self.assertEqual(loaded["search_metrics"]["records_screened"], 1)
                self.assertEqual(loaded["search_metrics"]["records_included"], 1)

    def test_rejects_unsafe_session_id(self):
        with self.assertRaises(ValueError):
            sessions.load_session("../outside")


if __name__ == "__main__":
    unittest.main()
