import json
import sys
import os
import boto3
from botocore.exceptions import ClientError

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
    "Package.swift",
    "Package.resolved",
    "project.pbxproj",
    "uv.lock"
]

def query_dynamodb_vulns(repo_name):
    """
    Query DynamoDB for vulnerability information by repo_name.

    Args:
        repo_name: The repository name to query

    Returns:
        The content of the "vulns" field if found, None otherwise
    """
    endpoint_url = os.environ.get(
        "AWS_ENDPOINT_URL", "https://dynamodb.us-east-1.amazonaws.com"
    )
    region_name = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    table_name = os.environ.get("DYNAMODB_TABLE_NAME", "blocked-repos")

    dynamodb = boto3.resource('dynamodb', endpoint_url=endpoint_url, region_name=region_name)
    table = dynamodb.Table(table_name)

    response = table.get_item(Key={'repo_name': repo_name})

    if 'Item' in response and 'vulns' in response['Item']:
        return response['Item']['vulns']
    return None

def check_patching_sla():
    if len(sys.argv) != 4:
        print("Usage: python check_patching_sla.py <changed_files_path> <repo_name> <comment_file>")
        sys.exit(1)

    changed_files_path = sys.argv[1]
    repo_name = sys.argv[2]
    comment_file = sys.argv[3]
    vulns = query_dynamodb_vulns(repo_name)
    if not vulns:
        print(f"Repository {repo_name} is not in the blocked repos list.")
        return True
    with open(changed_files_path) as f:
        changed_files = f.read().splitlines()
    for file in changed_files:
        filename = os.path.basename(file)
        if filename not in ALLOWED_FILES:
            print(f"Repository {repo_name} is in the blocked repos list. Please see PR comment for details.")
            with open(comment_file, 'w') as f:
                f.write(f"## ⚠️ Heads-up: This repository will be blocked from any work other than patching.\n")
                f.write(f"File {file} is not allowed to be modified in this patch.\n")
                f.write("The following vulnerability issues are past SLA:\n")
                for issue in vulns:
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