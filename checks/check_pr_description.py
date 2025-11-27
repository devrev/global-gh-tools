import re
import sys

def check_description(description):
    """
    Checks if the PR description contains a work item link.
    Returns True if valid, False otherwise.
    """
    # More flexible regex that handles markdown formatting
    regex = r"(?:^|[\s\[\(\-\*\>\.]|:\s)(https:\/\/app\.devrev\.ai\/devrev\/works\/)?(ISS|TKT|TASK)-\d+\b"
    return bool(re.search(regex, description, re.IGNORECASE))

def check_description_cli(description):
    """
    CLI version that prints messages and exits.
    """
    print(f"Checking PR description: {description}")
    if not check_description(description):
        print("❌ VALIDATION FAILED")
        print("")
        print("Reason: PR description must include a work item link")
        print("")
        print("Valid formats: ISS-123, TKT-456, TASK-789, or https://app.devrev.ai/devrev/works/ISS-123")
        print("Note: Use 'work-item: ISS-123' (space after colon), not 'work-item:ISS-123'")
        sys.exit(1)
    
    print("✅ VALIDATION PASSED - PR description contains a valid work item link")
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_pr_description.py \"<description>\"")
        sys.exit(1)
    
    pr_description = sys.argv[1]
    check_description_cli(pr_description)
