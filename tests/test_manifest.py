import json
import unittest

from dataroom_pipeline.models import validate_manifest
from dataroom_pipeline.paths import MANIFEST_PATH


class ManifestTests(unittest.TestCase):
    def test_manifest_is_valid(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        issues = validate_manifest(manifest)
        self.assertEqual([issue for issue in issues if issue.severity == "error"], [])

    def test_manifest_has_three_years_of_accounts(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        periods = {
            doc.get("reporting_period_end")
            for doc in manifest["documents"]
            if doc["category"] == "accounts"
        }
        self.assertGreaterEqual(len(periods), 3)


if __name__ == "__main__":
    unittest.main()
