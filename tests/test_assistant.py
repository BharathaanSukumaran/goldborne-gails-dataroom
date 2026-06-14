from pathlib import Path
import tempfile
import unittest

from dataroom_pipeline.assistant import answer_question
from dataroom_pipeline.pipeline import run_pipeline


class AssistantTests(unittest.TestCase):
    def test_charges_answer_has_registered_charge_holders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "dataroom.sqlite"
            run_pipeline(db_path=db_path)

            result = answer_question("What charges are registered against the company?", db_path=db_path)

            self.assertIn("Glas Trust Corporation Limited", result["answer"])
            self.assertIn("0605 5393 0006", result["answer"])
            self.assertIn("0605 5393 0005", result["answer"])
            self.assertTrue(result["citations"])

    def test_unknown_question_refuses_to_invent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "dataroom.sqlite"
            run_pipeline(db_path=db_path)

            result = answer_question("What is the CEO's favourite colour?", db_path=db_path)

            self.assertIn("does not contain enough", result["answer"])
            self.assertEqual(result["route"], "unsupported")


if __name__ == "__main__":
    unittest.main()
