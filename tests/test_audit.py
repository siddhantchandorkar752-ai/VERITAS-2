from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from audit.audit_logger import AuditLogger, load_trace
from core.schemas import DomainMode, Verdict


class AuditPersistenceTests(unittest.TestCase):
    def test_round_trip_writes_fingerprints_without_raw_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audit = AuditLogger(
                claim_id="claim-1",
                session_id="session-1",
                domain_mode=DomainMode.GENERAL,
                log_dir=directory,
            )
            audit.log_step("example", {"private": "input"}, {"private": "output"})
            trace = audit.finalise(Verdict.UNCERTAIN)
            loaded = load_trace(trace.trace_id, directory)
            files = "\n".join(
                path.read_text(encoding="utf-8")
                for path in Path(directory).iterdir()
                if path.is_file()
            )

        self.assertEqual(trace.trace_id, loaded.trace_id)
        self.assertEqual(Verdict.UNCERTAIN, loaded.final_verdict)
        self.assertNotIn('"private": "input"', files)
        self.assertNotIn('"private": "output"', files)

    def test_trace_id_path_traversal_is_rejected(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValueError, "UUID"),
        ):
            load_trace("../../outside", directory)
