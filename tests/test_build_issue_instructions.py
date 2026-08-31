import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUILD_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "build-apps.yml"
ISSUE_TEMPLATE = REPOSITORY_ROOT / ".github" / "new_container_issue_template.md"

# Expectations shared by the workflow and the checked-in template. The workflow prints
# the issue body with shell variables, the template mirrors it with `{{ env.* }}`
# placeholders, so the variable-dependent lines are asserted separately below.
COMMON_EXPECTED_TEXT = (
    # The two products must stay visually separated, each with its own heading.
    "## OpenRecon",
    "## FIRE",
    "## Release",
    # OpenRecon install routes.
    "Make sure that no protocol is open",
    "XA70 / Numaris/X VA70 and later",
    "XB10 / VB10",
    "store --install-package",
    "store --list",
    "XA60 and XA61",
    r"syngo.MR.HostInfra.OpenRecon.Watcher",
    r"OpenRecon.utr",
    # FIRE deployment options.
    "FIRE option A: chroot image on MARS",
    "FIRE option B: Docker container on another machine",
    "wip_070_fire_fire_mars_ssh.ini",
    "python-ismrmrd-server",
    "docker pull",
    "docker load -i",
    "docker run --rm -it -p 9002:9002",
    "--restart unless-stopped",
    "-v /tmp/share:/tmp/share",
    "--gpus all",
    "start_chroot=false",
    "[tunnel]",
    "open_tunnel=false",
    "open_tunnel=true",
    "local_fire_port=9003",
    "remote_fire_port=9002",
    "remote_ssh_fingerprint=",
    "auto_close_duration=900",
)


class BuildIssueInstructionTests(unittest.TestCase):
    def test_workflow_includes_both_openrecon_installation_routes(self):
        workflow = BUILD_WORKFLOW.read_text()

        expected_text = COMMON_EXPECTED_TEXT + (
            'cd /d \"%MREDGEHOME%\"',
            r"C:\\Temp\\OR\\Packages\\${IMAGENAME}.zip",
            "${IMAGENAME}.zip",
            r"C:\Program Files\Siemens\Numaris\OperationalManagement\FileTransfer\incoming",
            "curl.exe -k -O https://openrecon.s3.us-east-2.amazonaws.com/${IMAGENAME}.zip",
            "curl -O https://openrecon.s3.us-east-2.amazonaws.com/${FIRE_IMAGENAME}.zip",
            "docker load -i ${IMAGENAME}.tar",
            "docker pull ${BASE_DOCKER_IMAGE}",
            "${DOCKER_IMAGE_TAG}",
            "${FIRE_INI_NAME}",
        )
        for text in expected_text:
            with self.subTest(text=text):
                self.assertIn(text, workflow)

        self.assertNotIn("OpenRecon_package.zip", workflow)

    def test_workflow_exports_the_variables_the_fire_docker_route_needs(self):
        workflow = BUILD_WORKFLOW.read_text()

        for text in (
            "DOCKER_IMAGE_TAG=$(printf",
            "FIRE_INI_NAME=$(basename",
            "BASE_DOCKER_IMAGE=$(",
            "echo \"DOCKER_IMAGE_TAG=$DOCKER_IMAGE_TAG\"",
            "echo \"FIRE_INI_NAME=$FIRE_INI_NAME\"",
            "echo \"BASE_DOCKER_IMAGE=$BASE_DOCKER_IMAGE\"",
        ):
            with self.subTest(text=text):
                self.assertIn(text, workflow)

    def test_checked_in_template_matches_the_installation_contract(self):
        template = ISSUE_TEMPLATE.read_text()

        expected_text = COMMON_EXPECTED_TEXT + (
            'cd /d "%MREDGEHOME%"',
            r"C:\Temp\OR\Packages\{{ env.IMAGENAME }}.zip",
            "{{ env.IMAGENAME }}.zip",
            r"C:\Program Files\Siemens\Numaris\OperationalManagement\FileTransfer\incoming",
            "curl.exe -k -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.IMAGENAME }}.zip",
            "curl -O https://openrecon.s3.us-east-2.amazonaws.com/{{ env.FIRE_IMAGENAME }}.zip",
            "docker load -i {{ env.IMAGENAME }}.tar",
            "docker pull {{ env.BASE_DOCKER_IMAGE }}",
            "{{ env.DOCKER_IMAGE_TAG }}",
            "{{ env.FIRE_INI_NAME }}",
        )
        for text in expected_text:
            with self.subTest(text=text):
                self.assertIn(text, template)

        self.assertNotIn("OpenRecon_package.zip", template)

    def test_openrecon_and_fire_instructions_do_not_bleed_into_each_other(self):
        template = ISSUE_TEMPLATE.read_text()

        openrecon_section = self.get_section(template, "## OpenRecon")
        fire_section = self.get_section(template, "## FIRE")

        # Scanner package-store installation belongs to OpenRecon only.
        self.assertIn("store --install-package", openrecon_section)
        self.assertNotIn("store --install-package", fire_section)

        # chroot/Docker/tunnel configuration belongs to FIRE only.
        for text in ("INSTALL_FIRE.txt", "start_chroot", "docker run", "[tunnel]"):
            with self.subTest(text=text):
                self.assertIn(text, fire_section)
                self.assertNotIn(text, openrecon_section)

    def test_workflow_issue_body_renders_the_checked_in_template(self):
        workflow = BUILD_WORKFLOW.read_text()
        rendered = self.render_workflow_issue_body(workflow)
        self.assertEqual(rendered, self.render_template_body())

    @staticmethod
    def get_section(template, heading):
        body = template.split(heading, 1)[1]
        next_heading = re.search(r"^## ", body, re.MULTILINE)
        return body[: next_heading.start()] if next_heading else body

    VALUES = {
        "IMAGENAME": "OpenRecon_neurodesk_qsmxt_V9.14.0",
        "FIRE_IMAGENAME": "FIRE_neurodesk_qsmxt_V9.14.0",
        "DOCKER_IMAGE_TAG": "openrecon_neurodesk_qsmxt:v9.14.0",
        "FIRE_INI_NAME": "wip_070_fire_qsmxt.ini",
        "BASE_DOCKER_IMAGE": "vnmd/qsmxt_9.14.0",
        "GITHUB_ACTOR": "example-actor",
    }

    def render_template_body(self):
        lines = ISSUE_TEMPLATE.read_text().split("\n")
        self.assertEqual(lines[0], "---")
        body = lines[lines.index("---", 1) + 1 :]
        while body and body[-1] == "":
            body.pop()

        rendered = "\n".join(body)
        for name, value in self.VALUES.items():
            rendered = rendered.replace("{{ env.%s }}" % name, value)
        self.assertNotIn("{{ env.", rendered)
        return rendered

    def render_workflow_issue_body(self, workflow):
        """Evaluate the printf lines that build issue-body.md, without running bash."""
        start_marker = "          # shellcheck disable=SC2016\n          {\n"
        end_marker = "          } > issue-body.md\n"
        start = workflow.index(start_marker) + len(start_marker)
        end = workflow.index(end_marker, start)

        rendered_lines = []
        for raw_line in workflow[start:end].split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            if line == r"printf '\n'":
                rendered_lines.append("")
                continue

            match = re.fullmatch(r"printf '%s\\n' '(.*)'", line)
            if match:
                rendered_lines.append(match.group(1).replace("'\\''", "'"))
                continue

            match = re.fullmatch(r'printf \'%s\\n\' "(.*)"', line)
            self.assertIsNotNone(match, f"unexpected printf line: {line}")
            text = match.group(1)
            text = text.replace("${{ github.actor }}", self.VALUES["GITHUB_ACTOR"])
            for name, value in self.VALUES.items():
                text = text.replace("${%s}" % name, value)
            # Undo the escaping needed inside a double-quoted shell string.
            text = re.sub(r'\\([\\"`])', r"\1", text)
            self.assertNotIn("${", text, f"unsubstituted variable in: {line}")
            rendered_lines.append(text)

        return "\n".join(rendered_lines)


if __name__ == "__main__":
    unittest.main()
