#!/usr/bin/env python3
"""
Check Dockerfiles for ECR base images and update tags.
Replaces 'stable' tags with '1.0.0' and checks for newer versions.
"""

import os
import re
import sys
import json
import boto3
from typing import List, Dict, Tuple, Optional


class ECRImageChecker:
    def __init__(self):
        """Initialize ECR checker."""
        self.ecr_registry = "173672169127.dkr.ecr.us-east-1.amazonaws.com"
        self.ecr_pattern = re.compile(
            r'173672169127\.dkr\.ecr\.us-east-1\.amazonaws\.com/devrev/(base|build)-([^:\s]+)(:([^\s]+))?'
        )
        self.ecr_client = boto3.client('ecr', region_name='us-east-1')

    def find_dockerfiles(self, root_path: str = '.') -> List[str]:
        """Find all Dockerfile paths in the repository."""
        dockerfiles = []
        for root, dirs, files in os.walk(root_path):
            # Skip .git and other hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for file in files:
                if file == 'Dockerfile' or file.startswith('Dockerfile.'):
                    dockerfiles.append(os.path.join(root, file))

        return dockerfiles

    def parse_dockerfile(self, dockerfile_path: str) -> List[Dict]:
        """Parse Dockerfile and extract ECR image references."""
        ecr_images = []

        try:
            with open(dockerfile_path, 'r') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {dockerfile_path}: {e}")
            return ecr_images

        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            line = line.strip()

            # Only process lines that contain our ECR registry
            if self.ecr_registry not in line:
                continue

            # Check FROM statements and other image references
            if line.upper().startswith('FROM ') or self.ecr_registry in line:
                matches = self.ecr_pattern.findall(line)
                for match in matches:
                    image_type = match[0]  # base or build
                    image_name = match[1]
                    tag = match[3] if match[3] else 'latest'

                    ecr_images.append({
                        'file': dockerfile_path,
                        'line': line_num,
                        'line_content': line,
                        'image_type': image_type,
                        'image_name': image_name,
                        'current_tag': tag,
                        'repository_name': f'devrev/{image_type}-{image_name}'
                    })

        return ecr_images

    def get_latest_tag(self, repository_name: str) -> Optional[str]:
        """Get the latest semantic version tag from ECR repository."""
        try:
            response = self.ecr_client.describe_images(
                repositoryName=repository_name,
                imageDetails=[{'imageTag': tag} for tag in ['1.0.0', '1.0.1', '1.1.0', '2.0.0']]
            )

            # Get all semantic version tags
            tags = []
            for image in response.get('imageDetails', []):
                for tag in image.get('imageTags', []):
                    # Match semantic version pattern (x.y.z)
                    if re.match(r'^\d+\.\d+\.\d+$', tag):
                        tags.append(tag)

            if not tags:
                return None

            # Sort tags by semantic version (simple string sort works for most cases)
            tags.sort(reverse=True)
            return tags[0]

        except Exception as e:
            print(f"Error checking ECR repository {repository_name}: {e}")
            return None

    def check_and_update_images(self) -> List[Dict]:
        """Check all Dockerfiles and determine necessary updates."""

        dockerfiles = self.find_dockerfiles()
        updates_needed = []

        for dockerfile in dockerfiles:
            ecr_images = self.parse_dockerfile(dockerfile)

            for image in ecr_images:
                current_tag = image['current_tag']
                repository_name = image['repository_name']

                # Case 1: stable tag -> update to 1.0.0
                if current_tag == 'stable':
                    updates_needed.append({
                        **image,
                        'update_type': 'stable_to_version',
                        'new_tag': '1.0.0',
                        'reason': 'Replace stable tag with 1.0.0'
                    })

                # Case 2: already on version -> check for newer
                elif re.match(r'^\d+\.\d+\.\d+$', current_tag):
                    latest_tag = self.get_latest_tag(repository_name)

                    if latest_tag and latest_tag != current_tag:
                        # Simple version comparison (works for most semantic versions)
                        current_parts = [int(x) for x in current_tag.split('.')]
                        latest_parts = [int(x) for x in latest_tag.split('.')]

                        if latest_parts > current_parts:
                            updates_needed.append({
                                **image,
                                'update_type': 'version_upgrade',
                                'new_tag': latest_tag,
                                'reason': f'Newer version available: {current_tag} -> {latest_tag}'
                            })

        return updates_needed

    def create_pr_changes(self, updates: List[Dict]) -> Dict[str, List[Tuple[int, str, str]]]:
        """Create file changes for PR creation."""
        changes_by_file = {}

        for update in updates:
            file_path = update['file']
            line_num = update['line']
            old_content = update['line_content']
            current_tag = update['current_tag']
            new_tag = update['new_tag']

            # Create the new line content
            new_content = old_content.replace(f':{current_tag}', f':{new_tag}')

            if file_path not in changes_by_file:
                changes_by_file[file_path] = []

            changes_by_file[file_path].append((line_num, old_content, new_content))

        return changes_by_file


def main():
    """Main function to run ECR image checks."""
    checker = ECRImageChecker()

    try:
        updates = checker.check_and_update_images()

        if not updates:
            print("✅ No ECR image updates needed")
            return

        print(f"🔄 Found {len(updates)} ECR image updates needed:")

        for update in updates:
            print(f"  - {update['file']}:{update['line']}")
            print(f"    {update['repository_name']}: {update['current_tag']} -> {update['new_tag']}")
            print(f"    Reason: {update['reason']}")

        # Create PR changes
        changes = checker.create_pr_changes(updates)

        # Save changes to JSON for the workflow to process
        with open('ecr_updates.json', 'w') as f:
            json.dump({
                'updates': updates,
                'changes': changes
            }, f, indent=2)

        print(f"\n💾 Changes saved to ecr_updates.json")

        # Set GitHub Actions output
        if os.environ.get('GITHUB_ACTIONS'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"updates_needed={'true' if updates else 'false'}\n")
                f.write(f"num_updates={len(updates)}\n")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()