import json
import sys
import os

# The list of allowed files in the patch. If any file outside this list is modified, the patch will be blocked.
# The list includes any file that is necessary for dependency management or build configuration.
ALLOWED_FILES = [
    ".snyk",
    "CODEOWNERS",
    "go.mod",
    "go.sum",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "pkg.config.json",
    "yarn.lock",
]

def check_patching_sla():
    if len(sys.argv) != 5:
        print("Usage: python check_patching_sla.py <blocked_repo_json> <changed_files_path> <repo_name> <comment_file>")
        sys.exit(1)

    blocked_repo_json = sys.argv[1]
    changed_files_path = sys.argv[2]
    repo_name = sys.argv[3]
    comment_file = sys.argv[4]
    with open(blocked_repo_json) as f:
        blocked_repos = json.load(f)
    if repo_name not in blocked_repos:
        print(f"Repository {repo_name} is not in the blocked repos list.")
        return True
    with open(changed_files_path) as f:
        changed_files = f.read().splitlines()
    for file in changed_files:
        filename = os.path.basename(file)
        if filename not in ALLOWED_FILES:
            with open(comment_file, 'w') as f:
                f.write(f"## ⚠️ Heads-up: This repository will be blocked from any work other than patching.\n")
                f.write(f"File {file} is not allowed to be modified in this patch.\n")
                f.write("The following vulnerability issues are past SLA:\n")
                for issue in blocked_repos[repo_name]:
                    id = issue['id']
                    overdue_days = issue['overdue_days']
                    severity = issue['severity']
                    owner_email = issue['owner_email']
                    last_checked = issue['timestamp']
                    # Extract issue number from id, it is the last part after the last slash.
                    issue_number = id.split('/')[-1]
                    f.write(f"- ISS-{issue_number}, overdue {overdue_days:.1f}d, sev {severity}, owner: {owner_email}, checked: {last_checked}\n")
                f.write("\nNote that there is significant latency in updating this list. Please reach out on #antifragile if you are in a hurry or have an emergency.\n")
            return False
    return True


if __name__ == "__main__":
    if not check_patching_sla():
        exit(1)