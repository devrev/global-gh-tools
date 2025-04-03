import os

CODEOWNERS_FILE = ".github/CODEOWNERS"

def check_codeowners():
    """
    Check if the CODEOWNERS file exists and is not empty.
    """
    if not os.path.exists(CODEOWNERS_FILE):
        print(f"Error: {CODEOWNERS_FILE} file does not exist.")
        return False

    if os.path.getsize(CODEOWNERS_FILE) == 0:
        print(f"Error: {CODEOWNERS_FILE} file is empty.")
        return False

    print(f"{CODEOWNERS_FILE} file exists and is not empty.")
    return True

if __name__ == "__main__":
    if not check_codeowners():
        print("Please add a CODEOWNERS file to the repository.")
        exit(1)
    else:
        print("CODEOWNERS file check passed.")