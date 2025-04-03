import os

EMAILS_PATH = ".global-checks-tooling/committers.txt"

# Check that the emails in the file are from @devrev.ai.
def check_commit_emails():
    """
    Check if the committers.txt file exists and contains valid emails.
    """
    if not os.path.exists(EMAILS_PATH):
        print(f"Error: {EMAILS_PATH} file does not exist.")
        return False

    with open(EMAILS_PATH, "r") as f:
        emails = f.readlines()

    for email in emails:
        email = email.strip()
        if not email.endswith("@devrev.ai"):
            print(f"Error: Non devrev.ai email {email} in committers list.")
            return False

    print(f"{EMAILS_PATH} file exists and contains valid emails.")
    return True