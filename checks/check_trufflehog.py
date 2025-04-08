import json
import os
import strictyaml

CREDS_FILE = ".devrev/creds.yml"

schema = strictyaml.Map({
    "allow": strictyaml.Seq(
        strictyaml.Map({
            "path": strictyaml.Str(),
            "lines": strictyaml.Str(),
        })
    ),
})

def get_creds_overrides():
    allowed = {}
    if not os.path.exists(CREDS_FILE):
        return allowed
    with open(CREDS_FILE) as f:
        text = f.read()
    data = strictyaml.load(text, schema)
    for override in data.data["allow"]:
        path = override["path"]
        # Decode lines string field. It can contain:
        # 1. A single line number
        # 2. A range of line numbers (e.g., "1-5")
        # 3. A comma-separated list of line number ranaged (e.g., "1,2,3-8")
        parts = override["lines"].split(",")
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
    if line_num in lines:
        return True
    return False

def check_trufflehog(json_path):
    cred_overrides = get_creds_overrides()
    with open(json_path) as f:
        for line in f.readlines():
            line = line.strip()
            if len(line) == 0:
                continue
            finding = json.loads(line)
            git_info = finding["SourceMetadata"]["Data"]["Git"]
            fn = git_info["file"]
            line_num = git_info["line"]
            if is_overridden(fn, line_num, cred_overrides):
                print(f"Skipping {fn}:{line_num} because it is in the creds.yml file")
                continue
            print(f"Found secret in {fn}:{line_num}")
            return False
    print("No secrets found")
    return True