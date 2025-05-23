import re
import sys

def check_description(description):
    """
    Checks if the PR description contains a work item link.
    Returns True if valid, False otherwise.
    """
    regex = r"(^|\s)(https:\/\/app\.devrev\.ai\/devrev\/works\/)?(ISS|TKT|TASK)-\d+\b"
    return bool(re.search(regex, description))

def check_description_cli(description):
    """
    CLI version that prints messages and exits.
    """
    if not check_description(description):
        print("PR description must include a link to the work item (e.g., ISS-123, TKT-456, TASK-789, or a full https://app.devrev.ai/devrev/works/ISS-123 link).")
        sys.exit(1)
    print("PR description contains a valid work item link.")
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_pr_description.py \"<description>\"")
        sys.exit(1)
    
    pr_description = sys.argv[1]
    check_description_cli(pr_description)
