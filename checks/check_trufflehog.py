import json
import os
import sys

import strictyaml

CREDS_FILE = ".devrev/creds.yml"

schema = strictyaml.Map(
    {
        "allow": strictyaml.Seq(
            strictyaml.Map(
                {
                    "path": strictyaml.Str(),
                    "lines": strictyaml.Str(),
                }
            )
        ),
    }
)


def get_creds_overrides():
    allowed = {}
    if not os.path.exists(CREDS_FILE):
        return allowed
    with open(CREDS_FILE) as f:
        text = f.read()
    data = strictyaml.load(text, schema)
    for override in data["allow"]:
        path = override["path"].text
        # Decode lines string field. It can contain:
        # 1. A single line number
        # 2. A range of line numbers (e.g., "1-5")
        # 3. A comma-separated list of line number ranaged (e.g., "1,2,3-8")
        parts = override["lines"].text.split(",")
        lines = set()
        for part in parts:
            if "-" in part:
                start, end = part.split("-")
                start = int(start)
                end = int(end)
                lines.update(range(start, end + 1))
            else:
                lines.add(int(part))
        # Add the lines to the dictionary
        if path not in allowed:
            allowed[path] = set()
        allowed[path].update(lines)

    return allowed


def is_overridden(filename, line_num, creds_overrides):
    lines = creds_overrides.get(filename)
    if lines is None:
        return False
    return line_num in lines


COMMENT_MARKER = "<!-- trufflehog-advisory -->"


def get_findings(json_path):
    """
    Parse trufflehog JSON output and return the findings that are not ignored.

    Each finding is a dict with keys: detector, file, line, commit, verified.
    Duplicate findings (same detector, file, line and commit) are reported once.
    """
    cred_overrides = get_creds_overrides()
    findings = []
    seen = set()
    with open(json_path) as f:
        for line in f:
            line = line.strip()
            if len(line) == 0:
                continue
            finding = json.loads(line)
            detector_name = finding["DetectorName"]
            git_info = finding["SourceMetadata"]["Data"]["Git"]
            fn = git_info.get("file")
            line_num = git_info["line"]

            # Special handling for github tokens in commit messages:
            if detector_name == "Github" and fn is None:
                print(
                    f"Skipping {detector_name} finding because detection is in commit message"
                )
                continue
            # go.sum files only contain Go module checksums, which detectors can mistake for secrets.
            if os.path.basename(fn or "") == "go.sum":
                print(
                    f"Skipping {fn}:{line_num} because go.sum files contain no secrets"
                )
                continue
            if is_overridden(fn, line_num, cred_overrides):
                print(f"Skipping {fn}:{line_num} because it is in the creds.yml file")
                continue

            commit = git_info.get("commit")
            key = (detector_name, fn, line_num, commit)
            if key in seen:
                continue
            seen.add(key)
            if fn is None:
                # Clarify that the finding is in a commit message.
                print("<commit message>")
            print(f"Found secret in {fn}:{line_num}")
            findings.append(
                {
                    "detector": detector_name,
                    "file": fn,
                    "line": line_num,
                    "commit": commit,
                    "verified": finding.get("Verified", False),
                }
            )
    if not findings:
        print("No secrets found")
    return findings


def format_comment(findings, repo_name=None):
    """
    Format findings as a markdown PR comment. The secret values themselves are
    never included in the comment.
    """
    lines = [COMMENT_MARKER]
    if not findings:
        lines.append("## ✅ TruffleHog: no potential secrets found")
        lines.append("")
        lines.append("Findings reported earlier on this PR are no longer present.")
        return "\n".join(lines) + "\n"

    lines.append(f"## ⚠️ TruffleHog: {len(findings)} potential secret(s) found")
    lines.append("")
    lines.append(
        "This check is **advisory** and does not block merging. "
        "Please review each finding and rotate any real credential that was committed."
    )
    lines.append("")
    lines.append("| Detector | Location | Commit | Verified |")
    lines.append("| --- | --- | --- | --- |")
    for finding in findings:
        commit = finding["commit"] or ""
        short_commit = commit[:7]
        if finding["file"] is None:
            location = "_commit message_"
        else:
            location = f"`{finding['file']}:{finding['line']}`"
            if repo_name and commit:
                url = f"https://github.com/{repo_name}/blob/{commit}/{finding['file']}#L{finding['line']}"
                location = f"[{location}]({url})"
        verified = "✅ yes" if finding["verified"] else "no"
        lines.append(
            f"| {finding['detector']} | {location} | `{short_commit}` | {verified} |"
        )
    lines.append("")
    lines.append(
        f"If a finding is a false positive, add it to `{CREDS_FILE}` to suppress it:"
    )
    lines.append("")
    lines.append("```yaml")
    lines.append("allow:")
    lines.append('  - path: "path/to/file"')
    lines.append('    lines: "12,40-42"')
    lines.append("```")
    return "\n".join(lines) + "\n"


def check_trufflehog(json_path):
    return not get_findings(json_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python check_trufflehog.py <output.json> [comment_file] [repo_name]"
        )
        sys.exit(1)

    json_path = sys.argv[1]
    findings = get_findings(json_path)
    if len(sys.argv) >= 3:
        repo_name = sys.argv[3] if len(sys.argv) >= 4 else None
        with open(sys.argv[2], "w") as f:
            f.write(format_comment(findings, repo_name))
    sys.exit(0 if not findings else 1)
