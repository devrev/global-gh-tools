import io
import json
import os
import unittest
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path

import checks.check_codeowners
import checks.check_commit_emails
import checks.check_pr_description
import checks.check_repo_yml
import checks.check_service_policy
import checks.service_policy_render
import checks.check_trufflehog


@contextmanager
def change_dir(destination):
    prev_dir = Path.cwd()  # Store the current directory
    os.chdir(destination)  # Change to the new directory
    try:
        yield  # Allow code execution inside the "with" block
    finally:
        os.chdir(prev_dir)  # Revert to the original directory


class TestCodeOwners(unittest.TestCase):
    def test_without_codeowners(self):
        with change_dir("checks/fixtures/codeowners/without"):
            self.assertFalse(checks.check_codeowners.check_codeowners())

    def test_with_codeowners(self):
        with change_dir("checks/fixtures/codeowners/with"):
            self.assertTrue(checks.check_codeowners.check_codeowners())


class TestRepoYaml(unittest.TestCase):
    def test_good1_file(self):
        with change_dir("checks/fixtures/repo_yml/good1"):
            self.assertTrue(checks.check_repo_yml.check_repo_yml())

    def test_bad1_file(self):
        with change_dir("checks/fixtures/repo_yml/bad1"):
            self.assertFalse(checks.check_repo_yml.check_repo_yml())


class TestTrufflehog(unittest.TestCase):
    def test_empty(self):
        with change_dir("checks/fixtures/trufflehog/empty"):
            self.assertTrue(
                checks.check_trufflehog.check_trufflehog("./trufflehog.json")
            )

    def test_bad(self):
        with change_dir("checks/fixtures/trufflehog/bad"):
            self.assertFalse(
                checks.check_trufflehog.check_trufflehog("./trufflehog.json")
            )

    def test_override(self):
        with change_dir("checks/fixtures/trufflehog/override"):
            self.assertTrue(
                checks.check_trufflehog.check_trufflehog("./trufflehog.json")
            )

    def test_mixed(self):
        with change_dir("checks/fixtures/trufflehog/mixed"):
            self.assertFalse(
                checks.check_trufflehog.check_trufflehog("./trufflehog.json")
            )

    def test_two_overrides(self):
        with change_dir("checks/fixtures/trufflehog/two_overrides"):
            self.assertTrue(
                checks.check_trufflehog.check_trufflehog("./trufflehog.json")
            )

    def test_merge_message(self):
        with change_dir("checks/fixtures/trufflehog/merge_message"):
            self.assertTrue(
                checks.check_trufflehog.check_trufflehog("./trufflehog.json")
            )


class TestCommitEmails(unittest.TestCase):
    def test_good(self):
        with change_dir("checks/fixtures/emails/good"):
            self.assertTrue(checks.check_commit_emails.check_commit_emails())

    def test_bad(self):
        with change_dir("checks/fixtures/emails/bad"):
            self.assertFalse(checks.check_commit_emails.check_commit_emails())


class TestPRDescription(unittest.TestCase):
    def test_valid_iss_link(self):
        with open("checks/fixtures/pr_description/valid/iss_link.txt", "r") as f:
            description = f.read()
        self.assertTrue(checks.check_pr_description.check_description(description))

    def test_valid_tkt_link(self):
        with open("checks/fixtures/pr_description/valid/tkt_link.txt", "r") as f:
            description = f.read()
        self.assertTrue(checks.check_pr_description.check_description(description))

    def test_valid_task_link(self):
        with open("checks/fixtures/pr_description/valid/task_link.txt", "r") as f:
            description = f.read()
        self.assertTrue(checks.check_pr_description.check_description(description))

    def test_valid_full_url(self):
        with open("checks/fixtures/pr_description/valid/full_url.txt", "r") as f:
            description = f.read()
        self.assertTrue(checks.check_pr_description.check_description(description))

    def test_valid_generic_display_id(self):
        with open(
            "checks/fixtures/pr_description/valid/generic_display_id.txt", "r"
        ) as f:
            description = f.read()
        self.assertTrue(checks.check_pr_description.check_description(description))

    def test_valid_issue_url_display_id(self):
        with open(
            "checks/fixtures/pr_description/valid/issue_url_display_id.txt", "r"
        ) as f:
            description = f.read()
        self.assertTrue(checks.check_pr_description.check_description(description))

    def test_invalid_no_link(self):
        with open("checks/fixtures/pr_description/invalid/no_link.txt", "r") as f:
            description = f.read()
        self.assertFalse(checks.check_pr_description.check_description(description))

    def test_invalid_wrong_format(self):
        with open("checks/fixtures/pr_description/invalid/wrong_format.txt", "r") as f:
            description = f.read()
        self.assertFalse(checks.check_pr_description.check_description(description))

    def test_invalid_issue_url_lowercase_key(self):
        with open(
            "checks/fixtures/pr_description/invalid/issue_url_lowercase_key.txt", "r"
        ) as f:
            description = f.read()
        self.assertFalse(checks.check_pr_description.check_description(description))


SERVICE_POLICY_FIXTURES = "checks/fixtures/service_policy"
# sha256 of checks/service_policy_render.py; see
# test_render_module_hash_matches_vendored_copy.
SERVICE_POLICY_RENDER_SHA256 = (
    "468ca589150f77848bd4bd0d794b503fdc3aacf14b11be51f79bad938a29cf2a"
)
SERVICE_POLICY_NOW = datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)


def load_service_policy_fixture(name):
    if name is None:
        return None
    with open(os.path.join(SERVICE_POLICY_FIXTURES, name + ".json")) as f:
        return json.load(f)


class FakeGitHub:
    """In-memory pull request with at most one marked comment."""

    def __init__(self, body=None, is_minimized=False):
        self.comment = None
        if body is not None:
            self.comment = {
                "id": "IC_1",
                "database_id": 1,
                "body": body,
                "is_minimized": is_minimized,
            }
        self.calls = []

    def find_marked_comment(self):
        return None if self.comment is None else dict(self.comment)

    def create_comment(self, body):
        self.calls.append("create")
        self.comment = {"id": "IC_2", "database_id": 2, "body": body, "is_minimized": False}

    def update_comment(self, comment, body):
        self.calls.append("update")
        self.comment["body"] = body

    def minimize_comment(self, comment):
        self.calls.append("minimize")
        self.comment["is_minimized"] = True

    def unminimize_comment(self, comment):
        self.calls.append("unminimize")
        self.comment["is_minimized"] = False


EARLIER_COMMENT = checks.service_policy_render.MARKER + "\n## earlier warning\n"


class TestServicePolicyCheck(unittest.TestCase):
    def run_check(self, item, heartbeat="heartbeat_fresh", github=None, reader=None):
        github = github or FakeGitHub()
        if reader is None:
            heartbeat_item = load_service_policy_fixture(heartbeat)
            repo_item = load_service_policy_fixture(item)

            def reader(repo_name):
                return heartbeat_item, repo_item

        out = io.StringIO()
        code = checks.check_service_policy.run_check(
            "devrev/example-repo", reader, github, SERVICE_POLICY_NOW, 6, out=out
        )
        return code, out.getvalue(), github

    def test_two_warn_policies_render_with_own_owners_and_links(self):
        code, out, github = self.run_check("two_warn_policies")
        self.assertEqual(code, 0)
        body = github.comment["body"]
        self.assertTrue(body.startswith(checks.service_policy_render.MARKER + "\n"))
        self.assertIn("Service Policy check (warning only)", body)
        cost, freeze = body.split("Example team freeze")
        self.assertIn("Example cost ceiling", cost)
        self.assertIn("example\\-finops", cost)
        self.assertIn("[remediation](https://example.com/cost)", cost)
        self.assertIn("Outcome: status unknown", cost)
        self.assertIn("example\\-program", freeze)
        self.assertIn("[remediation](https://example.com/freeze)", freeze)
        self.assertIn("Outcome: violates", freeze)
        self.assertIn("example\\-team\\-one", body)
        self.assertNotIn("observe policy", body)
        self.assertEqual(len([l for l in out.splitlines() if l.startswith("::warning::")]), 2)
        self.assertEqual(github.calls, ["create"])

    def test_observe_only_renders_nothing_and_resolves_earlier_comment(self):
        github = FakeGitHub(body=EARLIER_COMMENT)
        code, out, github = self.run_check("observe_only", github=github)
        self.assertEqual(code, 0)
        self.assertEqual(github.calls, ["minimize"])
        self.assertTrue(github.comment["is_minimized"])
        self.assertEqual(github.comment["body"], EARLIER_COMMENT)
        self.assertEqual(out, "")

    def test_block_mode_renders_as_warning(self):
        code, out, github = self.run_check("block_mode")
        self.assertEqual(code, 0)
        self.assertIn("Example block policy", github.comment["body"])
        self.assertIn("Service Policy check (warning only)", github.comment["body"])
        self.assertIn("[remediation](https://example.com/block)", github.comment["body"])
        self.assertEqual(github.calls, ["create"])
        self.assertTrue(out.startswith("::warning::Service Policy: Example block policy"))

    def test_stale_projection_reports_unknown_and_succeeds(self):
        github = FakeGitHub(body=EARLIER_COMMENT)
        code, out, github = self.run_check("two_warn_policies", heartbeat="heartbeat_stale", github=github)
        self.assertEqual(code, 0)
        self.assertIn("governance status unknown", out)
        self.assertIn("older than its allowed age", out)
        self.assertEqual(github.calls, [])

    def test_missing_item_with_fresh_heartbeat_resolves_earlier_comment(self):
        github = FakeGitHub(body=EARLIER_COMMENT)
        code, out, github = self.run_check(None, github=github)
        self.assertEqual(code, 0)
        self.assertEqual(github.calls, ["minimize"])
        self.assertNotIn("unknown", out)

    def test_missing_item_with_stale_heartbeat_reports_unknown(self):
        code, out, github = self.run_check(None, heartbeat="heartbeat_stale")
        self.assertEqual(code, 0)
        self.assertIn("governance status unknown", out)
        self.assertEqual(github.calls, [])

    def test_missing_heartbeat_reports_unknown(self):
        code, out, github = self.run_check(None, heartbeat=None)
        self.assertEqual(code, 0)
        self.assertIn("governance status unknown", out)

    def test_resolved_comment_with_new_result_ends_up_visible(self):
        github = FakeGitHub(body=EARLIER_COMMENT, is_minimized=True)
        code, out, github = self.run_check("block_mode", github=github)
        self.assertEqual(code, 0)
        self.assertEqual(github.calls, ["update", "unminimize"])
        self.assertFalse(github.comment["is_minimized"])
        self.assertIn("Example block policy", github.comment["body"])

    def test_markdown_and_workflow_commands_render_as_literal_text(self):
        code, out, github = self.run_check("hostile_fields")
        self.assertEqual(code, 0)
        body = github.comment["body"]
        self.assertIn("\\*\\*Bold\\*\\*", body)
        self.assertIn("\\[click\\]\\(https", body)
        self.assertIn("\\<b\\>", body)
        self.assertNotIn("<b>", body)
        self.assertNotIn("](https://evil.example)", body)
        self.assertNotIn("::", body)
        self.assertNotIn("](javascript", body)
        self.assertIn("javascript\\:alert\\(1\\) (not a link", body)
        lines = out.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("::warning::"))
        self.assertNotIn("::", lines[0][len("::warning::"):])
        self.assertIn("%0A", lines[0])

    def test_credential_failure_succeeds_with_unknown_note(self):
        from botocore.exceptions import NoCredentialsError

        def reader(repo_name):
            raise NoCredentialsError()

        github = FakeGitHub(body=EARLIER_COMMENT)
        code, out, github = self.run_check(None, github=github, reader=reader)
        self.assertEqual(code, 0)
        self.assertIn("governance status unknown", out)
        self.assertIn("NoCredentialsError", out)
        self.assertEqual(github.calls, [])

    def test_failed_comment_succeeds_with_unknown_note(self):
        github = FakeGitHub()

        def broken(body):
            raise OSError("comment refused")

        github.create_comment = broken
        code, out, github = self.run_check("block_mode", github=github)
        self.assertEqual(code, 0)
        self.assertIn("comment could not be updated", out)

    def test_unchanged_visible_comment_is_left_alone(self):
        visible = checks.service_policy_render.visible_results(
            load_service_policy_fixture("block_mode")["results"]
        )
        github = FakeGitHub(body=checks.service_policy_render.render_comment(visible))
        code, out, github = self.run_check("block_mode", github=github)
        self.assertEqual(github.calls, [])

    def test_rendered_hash(self):
        render = checks.service_policy_render
        self.assertEqual(render.rendered_hash([]), "")
        visible = render.visible_results(
            load_service_policy_fixture("two_warn_policies")["results"]
        )
        self.assertEqual(len(visible), 2)
        import hashlib

        expected = hashlib.sha256(
            json.dumps(visible, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(render.rendered_hash(visible), expected)
        self.assertEqual(
            render.rendered_hash(render.visible_results(
                load_service_policy_fixture("observe_only")["results"]
            )),
            "",
        )

    def test_render_module_uses_standard_library_only(self):
        import ast

        with open("checks/service_policy_render.py") as f:
            tree = ast.parse(f.read())
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module.split(".")[0])
        self.assertTrue(modules <= {"hashlib", "json", "re", "urllib"}, modules)


    def test_render_module_hash_matches_vendored_copy(self):
        # devrev/security-tools vendors this file byte for byte as
        # cron-jobs/post-service-policy/src/service_policy_render.py, and its
        # tests/test_refresh_prs.py asserts the same hash (RENDER_SHA256 in
        # src/refresh_prs.py there). A change here must be re-vendored there and
        # both constants updated together.
        import hashlib

        with open("checks/service_policy_render.py", "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(digest, SERVICE_POLICY_RENDER_SHA256)


class TestServicePolicyGitHub(unittest.TestCase):
    def make(self, responses):
        github = checks.check_service_policy.GitHub(
            "token", "devrev/example-repo", "7"
        )
        sent = []

        def request(method, path, body=None):
            sent.append((method, path, body))
            return responses.pop(0)

        github._request = request
        return github, sent

    def test_finds_comment_by_marker_and_minimizes_as_resolved(self):
        marker = checks.service_policy_render.MARKER
        page = {"data": {"repository": {"pullRequest": {"comments": {
            "nodes": [
                {"id": "IC_a", "databaseId": 10, "body": "unrelated " + marker, "isMinimized": False},
                {"id": "IC_b", "databaseId": 11, "body": marker + "\nbody", "isMinimized": False},
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        }}}}}
        github, sent = self.make([page, {"data": {}}])
        checks.check_service_policy.sync_comment(github, [])
        self.assertEqual(sent[1][1], "/graphql")
        self.assertIn("classifier: RESOLVED", sent[1][2]["query"])
        self.assertEqual(sent[1][2]["variables"], {"id": "IC_b"})

    def test_edits_by_database_id_and_unminimizes(self):
        marker = checks.service_policy_render.MARKER
        page = {"data": {"repository": {"pullRequest": {"comments": {
            "nodes": [{"id": "IC_b", "databaseId": 11, "body": marker + "\nold", "isMinimized": True}],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        }}}}}
        github, sent = self.make([page, {}, {"data": {}}])
        visible = checks.service_policy_render.visible_results(
            load_service_policy_fixture("block_mode")["results"]
        )
        checks.check_service_policy.sync_comment(github, visible)
        self.assertEqual(sent[1][:2], ("PATCH", "/repos/devrev/example-repo/issues/comments/11"))
        self.assertIn("unminimizeComment", sent[2][2]["query"])


if __name__ == "__main__":
    unittest.main()
