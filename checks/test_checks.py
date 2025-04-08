import checks.check_codeowners
import checks.check_commit_emails
import checks.check_repo_yml
import checks.check_trufflehog

import unittest
import os
from pathlib import Path
from contextlib import contextmanager

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
            self.assertTrue(checks.check_trufflehog.check_trufflehog(
                "./trufflehog.json"))

    def test_bad(self):
        with change_dir("checks/fixtures/trufflehog/bad"):
            self.assertFalse(checks.check_trufflehog.check_trufflehog(
                "./trufflehog.json"))


    def test_override(self):
        with change_dir("checks/fixtures/trufflehog/override"):
            self.assertTrue(checks.check_trufflehog.check_trufflehog(
                "./trufflehog.json"))

    def test_mixed(self):
        with change_dir("checks/fixtures/trufflehog/mixed"):
            self.assertFalse(checks.check_trufflehog.check_trufflehog(
                "./trufflehog.json"))

    def test_two_overrides(self):
        with change_dir("checks/fixtures/trufflehog/two_overrides"):
            self.assertTrue(checks.check_trufflehog.check_trufflehog(
                "./trufflehog.json"))

class TestCommitEmails(unittest.TestCase):
    def test_good(self):
        with change_dir("checks/fixtures/emails/good"):
            self.assertTrue(checks.check_commit_emails.check_commit_emails())

    def test_bad(self):
        with change_dir("checks/fixtures/emails/bad"):
            self.assertFalse(checks.check_commit_emails.check_commit_emails())



if __name__ == '__main__':
    unittest.main()