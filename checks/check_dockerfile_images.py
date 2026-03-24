#!/usr/bin/env python3
"""
Check all Dockerfiles in the repository and validate that all FROM statements
use only approved image registries.
"""

import os
import sys
import re
from typing import List, Tuple


# Allowed image prefixes - add or remove as needed
ALLOWED_PREFIXES = [
    "173672169127.dkr.ecr.us-east-1.amazonaws.com/devrev/",
    "cgr.dev/",
    # Example: cypress/
]

# Images to ignore completely - add or remove as needed
IGNORED_IMAGES = [
    "scratch",
]


def find_dockerfiles(root_path: str = ".") -> List[str]:
    """Find all files with 'Dockerfile' in their filename."""
    dockerfiles = []
    for root, dirs, files in os.walk(root_path):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for file in files:
            if "Dockerfile" in file:
                dockerfiles.append(os.path.join(root, file))
    return dockerfiles


def extract_from_statements(dockerfile_path: str) -> List[Tuple[int, str]]:
    """Extract all FROM statements from a Dockerfile. Returns list of (line_num, image)."""
    from_statements = []
    try:
        with open(dockerfile_path, "r") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ Error reading {dockerfile_path}: {e}")
        sys.exit(1)

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        # Match FROM statements (case insensitive), ignore comments
        if stripped.upper().startswith("FROM ") and not stripped.startswith("#"):
            # Extract image name (FROM <image> [AS <name>])
            parts = stripped.split()
            if len(parts) >= 2:
                image = parts[1]
                from_statements.append((line_num, image))

    return from_statements


def is_allowed(image: str) -> bool:
    """Check if image starts with one of the allowed prefixes or is ignored."""
    if image.lower() in IGNORED_IMAGES:
        return True
    for prefix in ALLOWED_PREFIXES:
        if image.startswith(prefix):
            return True
    return False

def main():
    """Main function to validate all Dockerfile FROM statements."""
    print("🔍 Checking Dockerfiles for approved image registries...")
    print(f"Allowed prefixes:")
    for prefix in ALLOWED_PREFIXES:
        print(f"  - {prefix}")
    print()

    dockerfiles = find_dockerfiles()

    if not dockerfiles:
        print("✅ No Dockerfiles found in repository")
        sys.exit(0)

    print(f"Found {len(dockerfiles)} Dockerfile(s) to check\n")

    violations = []

    for dockerfile in dockerfiles:
        from_statements = extract_from_statements(dockerfile)

        for line_num, image in from_statements:
            if not is_allowed(image):
                violations.append((dockerfile, line_num, image))

    if violations:
        print("❌ Unapproved images found in Dockerfiles:\n")
        for dockerfile, line_num, image in violations:
            print(f"  {dockerfile}:{line_num} → {image}")
        print(f"\nAll FROM statements must use one of the approved prefixes:")
        for prefix in ALLOWED_PREFIXES:
            print(f"  - {prefix}")
        sys.exit(1)
    else:
        print("✅ All Dockerfile FROM statements use approved image registries")
        sys.exit(0)


if __name__ == "__main__":
    main()
