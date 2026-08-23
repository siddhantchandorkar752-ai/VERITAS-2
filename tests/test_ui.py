from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class StreamlitWorkflowTests(unittest.TestCase):
    @patch.dict(os.environ, {"VERITAS_MODE": "demo"})
    def test_demo_workflow_renders_without_app_exception(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "ui" / "app.py"
        app = AppTest.from_file(app_path).run(timeout=20)
        self.assertFalse(app.exception)

        app.text_area[0].input("The Earth orbits the Sun.")
        app.button[0].click()
        app.run(timeout=20)

        self.assertFalse(app.exception)
        self.assertEqual("Simulated aggregation output", app.subheader[0].value)
        self.assertTrue(any("SYNTHETIC RESULT" in warning.value for warning in app.warning))
        self.assertEqual(4, len(app.metric))


if __name__ == "__main__":
    unittest.main()
