#!/usr/bin/env python3
"""
Create PR with ECR image updates based on check_ecr_images.py output.
"""

import os
import sys
import json
import subprocess
from typing import Dict, List, Tuple


def run_command(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run shell command and return result."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if check and result.returncode != 0:
        print(f"Command failed with return code {result.returncode}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)

    return result


def apply_file_changes(changes_by_file: Dict[str, List[Tuple[int, str, str]]]):
    """Apply the file changes to update Dockerfiles."""
    for file_path, changes in changes_by_file.items():
        print(f"Updating {file_path}")

        # Read current file content
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue

        # Sort changes by line number in descending order to avoid line number shifts
        changes.sort(key=lambda x: x[0], reverse=True)

        # Apply changes
        for line_num, old_content, new_content in changes:
            if line_num <= len(lines):
                # Check if the line still matches (in case file was modified)
                current_line = lines[line_num - 1].rstrip('\n')
                if current_line.strip() == old_content.strip():
                    lines[line_num - 1] = new_content + '\n'
                    print(f"  Line {line_num}: Updated image tag")
                else:
                    print(f"  Line {line_num}: Warning - content changed, skipping")
            else:
                print(f"  Line {line_num}: Warning - line number out of range")

        # Write updated content
        try:
            with open(file_path, 'w') as f:
                f.writelines(lines)
        except Exception as e:
            print(f"Error writing {file_path}: {e}")


def create_pr_description(updates: List[Dict]) -> str:
    """Create PR description based on updates."""
    description = "## 🐳 ECR Docker Image Updates\n\n"
    description += "This automated PR updates ECR images to newer versions.\n\n"

    # Group updates by type
    stable_updates = [u for u in updates if u['update_type'] == 'stable_to_version']
    version_updates = [u for u in updates if u['update_type'] == 'version_upgrade']

    if stable_updates:
        description += "### 📌 Stable Tag Replacements\n"
        description += "Replaced `stable` tags with `1.0.0`:\n\n"
        for update in stable_updates:
            description += f"- `{update['repository_name']}`: `{update['current_tag']}` → `{update['new_tag']}`\n"
        description += "\n"

    if version_updates:
        description += "### ⬆️ Version Upgrades\n"
        description += "Updated to newer available versions:\n\n"
        for update in version_updates:
            description += f"- `{update['repository_name']}`: `{update['current_tag']}` → `{update['new_tag']}`\n"
        description += "\n"

    description += "### 📁 Files Changed\n"
    files = set(update['file'] for update in updates)
    for file_path in sorted(files):
        description += f"- `{file_path}`\n"

    description += "\n---\n"
    description += "*This PR was automatically created by the global ECR image update workflow.*"

    return description


def get_existing_pr(branch_name: str) -> int | None:
    """Check if a PR already exists for the given branch. Returns PR number or None."""
    result = run_command(
        f'gh pr list --head {branch_name} --base main --state open --json number',
        check=False
    )
    if result.returncode == 0 and result.stdout.strip():
        prs = json.loads(result.stdout)
        if prs:
            return prs[0]['number']
    return None

def changes_already_in_remote(branch_name: str, changes_by_file: Dict) -> bool:
    """Check if remote branch already has the same file changes."""
    run_command(f"git fetch origin {branch_name}", check=False)
    
    for file_path, changes in changes_by_file.items():
        result = run_command(f"git show origin/{branch_name}:{file_path}", check=False)
        if result.returncode != 0:
            return False
        remote_lines = result.stdout.splitlines()
        for line_num, old_content, new_content in changes:
            if remote_lines[line_num - 1].strip() != new_content.strip():
                return False
    return True

def main():
    """Main function to create PR with ECR updates."""
    branch_name = "automated/ecr-image-updates"
    # Load updates data from stdin
    try:
        stdin_content = sys.stdin.read().strip()

        if not stdin_content:
            print("❌ No input data provided")
            sys.exit(1)

        data = json.loads(stdin_content)
        updates = data.get('updates', [])
        changes_by_file = data.get('changes', {})

        if not updates:
            print("✅ No updates needed")
            existing_pr_number = get_existing_pr(branch_name)
            if existing_pr_number:
                print(f"Closing PR #{existing_pr_number} as no updates needed...")
                run_command(f'gh pr close {existing_pr_number} --comment "All ECR images are already up to date, closing PR automatically."')
                run_command(f"git push origin --delete {branch_name}", check=False)
                print(f"✅ Closed PR #{existing_pr_number} and deleted branch")
            else:
                print("✅ No open PR found, nothing to do")
            return

    except Exception as e:
        print(f"❌ Error loading input data: {e}")
        sys.exit(1)

    # Get repository name
    repo_name = os.environ.get('GITHUB_REPOSITORY')
    if not repo_name:
        print("❌ GITHUB_REPOSITORY environment variable not set")
        sys.exit(1)

    print(f"🔄 Processing {len(updates)} ECR image updates for {repo_name}")

    # Configure git
    run_command("git config user.name 'ECR Image Updates'")
    run_command("git config user.email 'noreply@devrev.ai'")

    # Check if PR already exists
    existing_pr_number = get_existing_pr(branch_name)

    # Delete local branch if it exists
    result = run_command(f"git rev-parse --verify {branch_name}", check=False)
    if result.returncode == 0:
        print(f"Local branch {branch_name} already exists, deleting...")
        run_command(f"git branch -D {branch_name}")

    # Create and checkout new branch
    run_command(f"git checkout -b {branch_name}")

    # Apply file changes
    apply_file_changes(changes_by_file)

    # Stage and commit changes (exclude tooling directory)
    run_command("git add --all")
    run_command("git reset .global-checks-tooling", check=False)
    run_command("git reset ecr_data.json", check=False)
    run_command("git reset ecr_updates.json", check=False)
    run_command("git reset pr_description.md", check=False)

    commit_message = f"chore: update ECR Docker images\n\n"
    commit_message += f"- Updated {len(updates)} image references\n"

    stable_count = len([u for u in updates if u['update_type'] == 'stable_to_version'])
    version_count = len([u for u in updates if u['update_type'] == 'version_upgrade'])

    if stable_count > 0:
        commit_message += f"- Replaced {stable_count} stable tags with 1.0.0\n"
    if version_count > 0:
        commit_message += f"- Upgraded {version_count} images to newer versions\n"

    run_command(f'git commit -m "{commit_message}"')    

    if existing_pr_number:
        # PR exists → check if remote branch already has same changes
        if changes_already_in_remote(branch_name, changes_by_file):
            print(f"PR #{existing_pr_number} already has these changes, skipping force push...")
            return
        # Changes are different → force push to update it
        print(f"PR #{existing_pr_number} already exists, force pushing updates...")
        run_command(f"git push origin {branch_name} --force")
        print(f"✅ Updated existing PR #{existing_pr_number}")
    else:
        # No PR exists → push and create new PR
        run_command(f"git push origin {branch_name} --force")

        pr_description = create_pr_description(updates)
        pr_title = "chore: update ECR Docker images"

        with open('pr_description.md', 'w') as f:
            f.write(pr_description)

        run_command(f'gh pr create --title "{pr_title}" --body-file pr_description.md --base main')
        print(f"✅ Created PR: {pr_title}")

        os.remove('pr_description.md')


if __name__ == "__main__":
    main()