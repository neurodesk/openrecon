import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUILD_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "build-apps.yml"
ISSUE_TEMPLATE = REPOSITORY_ROOT / ".github" / "new_container_issue_template.md"


class BuildIssueInstructionTests(unittest.TestCase):
    def test_workflow_includes_both_openrecon_installation_routes(self):
        workflow = BUILD_WORKFLOW.read_text()

        expected_text = (
            "Make sure that no protocol is open",
            "XA70 / Numaris/X VA70 and later",
            "XB10 / VB10",
            'cd /d \"%MREDGEHOME%\"',
            "store --install-package",
            r"C:\\Temp\\OR\\Packages\\${IMAGENAME}.zip",
            "${IMAGENAME}.zip",
            "store --list",
            "XA60 and XA61",
            r"C:\Program Files\Siemens\Numaris\OperationalManagement\FileTransfer\incoming",
            "curl.exe -k -O https://openrecon.s3.us-east-2.amazonaws.com/${IMAGENAME}.zip",
            r"syngo.MR.HostInfra.OpenRecon.Watcher",
            r"OpenRecon.utr",
            "For FIRE:",
        )
        for text in expected_text:
            with self.subTest(text=text):
                self.assertIn(text, workflow)

        self.assertNotIn("OpenRecon_package.zip", workflow)

    def test_checked_in_template_matches_the_installation_contract(self):
        template = ISSUE_TEMPLATE.read_text()

        expected_text = (
            "Make sure that no protocol is open",
            "XA70 / Numaris/X VA70 and later",
            "XB10 / VB10",
            'cd /d "%MREDGEHOME%"',
            "store --install-package",
            r"C:\Temp\OR\Packages\{{ env.IMAGENAME }}.zip",
            "{{ env.IMAGENAME }}.zip",
            "store --list",
            "XA60 and XA61",
            r"C:\Program Files\Siemens\Numaris\OperationalManagement\FileTransfer\incoming",
            "curl.exe -k -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.IMAGENAME }}.zip",
            r"syngo.MR.HostInfra.OpenRecon.Watcher",
            r"OpenRecon.utr",
            "For FIRE:",
        )
        for text in expected_text:
            with self.subTest(text=text):
                self.assertIn(text, template)

        self.assertNotIn("OpenRecon_package.zip", template)


if __name__ == "__main__":
    unittest.main()
