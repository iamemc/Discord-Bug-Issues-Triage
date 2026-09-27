"""Thin python-gitlab wrapper - just the operations this pipeline needs."""
import re

import gitlab


class GitLabClient:
    def __init__(self, url: str, token: str, project_id: str):
        self.gl = gitlab.Gitlab(url, private_token=token)
        self.project = self.gl.projects.get(project_id)

    def create_issue(self, title: str, description: str, labels=None) -> str:
        issue = self.project.issues.create({
            "title": title,
            "description": description,
            "labels": labels or [],
        })
        return str(issue.iid)

    def comment(self, issue_iid: str, body: str):
        issue = self.project.issues.get(issue_iid)
        issue.notes.create({"body": body})

    def get_issue_text(self, issue_iid: str) -> str:
        issue = self.project.issues.get(issue_iid)
        return f"{issue.title}\n{issue.description or ''}"

    def get_mr_changes(self, mr_iid: str) -> dict:
        mr = self.project.mergerequests.get(mr_iid)
        return mr.changes()


def extract_issue_iid(mr_description: str) -> str | None:
    """Pulls the issue number out of 'Closes #123' / 'Fixes #123' / 'Resolves #123'."""
    m = re.search(r"(?:closes|fixes|resolves)\s+#(\d+)", mr_description or "", re.I)
    return m.group(1) if m else None
