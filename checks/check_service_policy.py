"""Service Policy check: warn-only pull request comment from the projection.

Reads this repository's Service Policy projection from DynamoDB, renders its
warn-mode results (block is rendered as warn in this version) as one pull
request comment found by its marker, and emits one warning annotation per
policy. When there is nothing to show, an earlier comment is minimized as
resolved rather than deleted.

The check always exits 0. Any failure, including a missing or stale
heartbeat, an unreadable projection, a credential error, or a failed GitHub
call, ends with a note that governance status is unknown.

Environment:
  GITHUB_REPOSITORY         owner/repo, for example devrev/flow
  PR_NUMBER                 pull request number
  GITHUB_TOKEN              the workflow token (pull-requests: write)
  GITHUB_API_URL            optional, default https://api.github.com
  PROJECTION_TABLE_NAME     optional, default service-policy-projection
  MAX_PROJECTION_AGE_HOURS  optional, default 6
  AWS_DEFAULT_REGION        optional, default us-east-1
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

try:  # Run as a script from the workflow: the script's own directory.
    import service_policy_render as render
except ImportError:  # Imported as checks.check_service_policy in tests.
    from checks import service_policy_render as render

HEARTBEAT_KEY = "__heartbeat__"
DEFAULT_TABLE = "service-policy-projection"
DEFAULT_MAX_AGE_HOURS = 6
UNKNOWN_PREFIX = "Service Policy: governance status unknown"


class GovernanceUnknown(Exception):
    """The projection cannot be trusted for this run."""


# Projection --------------------------------------------------------------


def read_projection(repo_name, table_name, region_name):
    """Return (heartbeat_item, repository_item); either may be None."""
    import boto3

    table = boto3.resource("dynamodb", region_name=region_name).Table(table_name)
    heartbeat = table.get_item(Key={"repo_name": HEARTBEAT_KEY}).get("Item")
    item = table.get_item(Key={"repo_name": repo_name}).get("Item")
    return heartbeat, item


def parse_time(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def visible_results_from(heartbeat, item, now, max_age_hours):
    """Return the visible results, or raise GovernanceUnknown."""
    if not heartbeat or not heartbeat.get("produced_at"):
        raise GovernanceUnknown("the projection heartbeat is missing")
    age = now - parse_time(heartbeat["produced_at"])
    if age > timedelta(hours=max_age_hours):
        raise GovernanceUnknown(
            "the projection is older than its allowed age of "
            f"{max_age_hours} hours"
        )
    if not item:
        return []
    return render.visible_results(item.get("results"))


# GitHub ------------------------------------------------------------------


class GitHub:
    """The few GitHub REST and GraphQL calls the check needs."""

    def __init__(self, token, repo, pr_number, api_url="https://api.github.com"):
        self.token = token
        self.owner, self.name = repo.split("/", 1)
        self.pr_number = int(pr_number)
        self.api_url = api_url.rstrip("/")

    def _request(self, method, path, body=None):
        request = urllib.request.Request(
            self.api_url + path,
            method=method,
            data=None if body is None else json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b"null")

    def _graphql(self, query, variables):
        data = self._request("POST", "/graphql", {"query": query, "variables": variables})
        if data.get("errors"):
            raise RuntimeError("GitHub GraphQL error: " + json.dumps(data["errors"]))
        return data["data"]

    def find_marked_comment(self):
        """Return {"id", "database_id", "body", "is_minimized"} or None."""
        query = """
        query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
          repository(owner: $owner, name: $name) {
            pullRequest(number: $number) {
              comments(first: 100, after: $cursor) {
                nodes { id databaseId body isMinimized }
                pageInfo { hasNextPage endCursor }
              }
            }
          }
        }"""
        cursor = None
        while True:
            data = self._graphql(
                query,
                {"owner": self.owner, "name": self.name,
                 "number": self.pr_number, "cursor": cursor},
            )
            comments = data["repository"]["pullRequest"]["comments"]
            for node in comments["nodes"]:
                if (node.get("body") or "").split("\n", 1)[0].strip() == render.MARKER:
                    return {
                        "id": node["id"],
                        "database_id": node["databaseId"],
                        "body": node["body"],
                        "is_minimized": node["isMinimized"],
                    }
            if not comments["pageInfo"]["hasNextPage"]:
                return None
            cursor = comments["pageInfo"]["endCursor"]

    def create_comment(self, body):
        path = f"/repos/{self.owner}/{self.name}/issues/{self.pr_number}/comments"
        self._request("POST", path, {"body": body})

    def update_comment(self, comment, body):
        path = f"/repos/{self.owner}/{self.name}/issues/comments/{comment['database_id']}"
        self._request("PATCH", path, {"body": body})

    def minimize_comment(self, comment):
        self._graphql(
            "mutation($id: ID!) { minimizeComment(input: "
            "{subjectId: $id, classifier: RESOLVED}) { clientMutationId } }",
            {"id": comment["id"]},
        )

    def unminimize_comment(self, comment):
        self._graphql(
            "mutation($id: ID!) { unminimizeComment(input: "
            "{subjectId: $id}) { clientMutationId } }",
            {"id": comment["id"]},
        )


def sync_comment(github, visible):
    """Edit or create the marked comment, or minimize it as resolved."""
    comment = github.find_marked_comment()
    if not visible:
        if comment and not comment["is_minimized"]:
            github.minimize_comment(comment)
        return
    body = render.render_comment(visible)
    if comment is None:
        github.create_comment(body)
        return
    if comment["body"] != body:
        github.update_comment(comment, body)
    if comment["is_minimized"]:
        github.unminimize_comment(comment)


# Annotations -------------------------------------------------------------


def escape_command_value(value):
    """Escape a workflow command message and break any `::` inside it."""
    text = "" if value is None else str(value)
    text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return render.neutralize_commands(text)


def annotation_lines(visible):
    """Return one ::warning:: line per policy, in first-seen order."""
    by_policy = {}
    for result in visible:
        policy = result.get("policy") or {}
        by_policy.setdefault(policy.get("slug"), (policy, []))[1].append(result)
    lines = []
    for policy, results in by_policy.values():
        services = ", ".join(
            f"{r.get('service')} {render.OUTCOME_LABELS.get(r.get('outcome'), r.get('outcome'))}"
            for r in results
        )
        message = (
            f"Service Policy: {policy.get('reason')} (owner {policy.get('owner')}): "
            f"{services}. Remediation: {policy.get('remediation_url')}"
        )
        lines.append("::warning::" + escape_command_value(message))
    return lines


def unknown_line(reason):
    return "::warning::" + escape_command_value(f"{UNKNOWN_PREFIX}: {reason}.")


# Entry point -------------------------------------------------------------


def run_check(repo_name, reader, github, now, max_age_hours, out=None):
    """Run the check and return its exit code, which is always 0."""
    out = out or sys.stdout
    try:
        heartbeat, item = reader(repo_name)
        visible = visible_results_from(heartbeat, item, now, max_age_hours)
    except GovernanceUnknown as exc:
        print(unknown_line(str(exc)), file=out)
        return 0
    except Exception as exc:  # Credentials, network, malformed data.
        print(unknown_line(f"the projection could not be read ({type(exc).__name__})"), file=out)
        return 0

    for line in annotation_lines(visible):
        print(line, file=out)
    try:
        sync_comment(github, visible)
    except Exception as exc:
        print(unknown_line(f"the pull request comment could not be updated ({type(exc).__name__})"), file=out)
    return 0


def main():
    try:
        repo_name = os.environ["GITHUB_REPOSITORY"]
        table = os.environ.get("PROJECTION_TABLE_NAME") or DEFAULT_TABLE
        region = os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
        max_age = float(os.environ.get("MAX_PROJECTION_AGE_HOURS") or DEFAULT_MAX_AGE_HOURS)
        github = GitHub(
            os.environ["GITHUB_TOKEN"],
            repo_name,
            os.environ["PR_NUMBER"],
            os.environ.get("GITHUB_API_URL") or "https://api.github.com",
        )
    except Exception as exc:
        print(unknown_line(f"the check is misconfigured ({type(exc).__name__})"))
        return 0
    return run_check(
        repo_name,
        lambda repo: read_projection(repo, table, region),
        github,
        datetime.now(timezone.utc),
        max_age,
    )


if __name__ == "__main__":
    sys.exit(main())
