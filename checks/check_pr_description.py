import re
import sys

def check_description(description):
    """
    Checks if the PR description contains a work item link.
    """
    regex = r"(^|\s)(https:\/\/app\.devrev\.ai\/devrev\/works\/)?(ISS|TKT|TASK)-\d+\b"
    if not re.search(regex, description):
        print("PR description must include a link to the work item (e.g., ISS-123, TKT-456, TASK-789, or a full https://app.devrev.ai/devrev/works/ISS-123 link).")
        sys.exit(1)
    print("PR description contains a valid work item link.")
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_pr_description.py \"<description>\"")
        sys.exit(1)
    
    pr_description = sys.argv[1]
    check_description(pr_description)
