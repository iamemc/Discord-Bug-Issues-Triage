"""GitLab webhook receiver - this is the 'learn from merged tickets' loop.

Point a GitLab project webhook (Merge request events) at
POST /gitlab/webhook. When an MR merges, this pulls the diff and the
originating issue, summarizes the fix, and upserts
{issue text -> files actually changed} into known_issues as ground truth.
"""
from fastapi import FastAPI, Request, HTTPException

from .config import load_config
from .vector_store import Store
from .gitlab_client import GitLabClient, extract_issue_iid
from .ollama_client import get_client, embed, summarize

app = FastAPI()

cfg = load_config()
store = Store(cfg.paths.chroma_dir)
gl = GitLabClient(cfg.gitlab.url, cfg.gitlab.token, cfg.gitlab.project_id)
oclient = get_client(cfg.ollama.host)


@app.post("/gitlab/webhook")
async def handle(request: Request):
    if request.headers.get("X-Gitlab-Token") != cfg.gitlab.webhook_secret:
        raise HTTPException(status_code=401, detail="bad token")

    payload = await request.json()
    if payload.get("object_kind") != "merge_request":
        return {"ignored": "not a merge_request event"}

    attrs = payload["object_attributes"]
    if attrs.get("action") != "merge":
        return {"ignored": f"action={attrs.get('action')}"}

    mr_iid = str(attrs["iid"])
    changes = gl.get_mr_changes(mr_iid)
    files_changed = [c["new_path"] for c in changes.get("changes", [])]
    diff_text = "\n".join(c.get("diff", "") for c in changes.get("changes", []))

    fix_summary = summarize(
        oclient, cfg.models.tier1, diff_text,
        instruction="Summarize this code diff's fix in one sentence.",
    )

    issue_iid = extract_issue_iid(attrs.get("description", ""))
    issue_text = gl.get_issue_text(issue_iid) if issue_iid else attrs.get("title", "")

    emb = embed(oclient, cfg.models.embed, issue_text)
    store.upsert_issue(
        id=f"mr-{mr_iid}",
        embedding=emb,
        text=issue_text,
        metadata={
            "status": "resolved",
            "files_changed": files_changed,
            "resolution": fix_summary,
        },
    )

    return {"indexed": True, "files": files_changed, "summary": fix_summary}
