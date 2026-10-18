# global-gh-tools

Globally required workflow to enforce:

- The use of a CODEOWNERS file.
- The use of a repo.yml file.
- The use of devrev.ai emails in commits.
- No credentials getting committed.

## Service Policy check

`.github/workflows/service-policy-check.yml` is a warn-only governance check for pull requests. It reads the repository's Service Policy projection from the DynamoDB table `service-policy-projection` in us-east-1, which a scheduled job publishes from the governance policies declared in Constellation, and runs `checks/check_service_policy.py`. When the repository's services have results for policies in warn mode (block mode is shown as warn in this version), the check posts or edits one pull request comment and emits one warning annotation per policy. Each entry lists the policy reason, the service, the team, the outcome, the owner, and the remediation link. The comment starts with the marker `<!-- service-policy-check -->` and is edited in place. When there is nothing left to show, the comment is minimized as resolved rather than deleted. If new results arrive later, the comment is edited and shown again. Policies in observe mode are never shown.

The check always succeeds. A missing or stale projection heartbeat (older than `MAX_PROJECTION_AGE_HOURS`, default 6), a credential error, an unreadable projection, or a failed comment ends with a warning that governance status is unknown.

The projection is read with GitHub OIDC through a dedicated read-only role. The role ARN in the workflow, `arn:aws:iam::162856926107:role/gh-action-service-policy-read`, is a placeholder that must be created before rollout, with `dynamodb:GetItem` on that table only and a trust policy limited to the devrev organization's pull request workflows running this check.

The rendering rules (which results are visible, the rendered hash, and the escaped comment body) live in `checks/service_policy_render.py`. That module uses the standard library only, because the job that refreshes open pull requests vendors it byte for byte; change both copies together.

## Python dependencies

Update Python dependencies with `make update-requirements`.
