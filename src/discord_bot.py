"""Discord ingestion: listens for new threads in the configured forum
channel, runs them through the triage cascade, and acts on the verdict.
"""
import discord

from .config import load_config
from .vector_store import Store
from .triage import Triage
from .gitlab_client import GitLabClient


def build_bot(cfg, triage: Triage, gl: GitLabClient) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}")

    @client.event
    async def on_thread_create(thread: discord.Thread):
        if thread.parent_id != cfg.discord.triage_channel_id:
            return

        starter = await thread.fetch_message(thread.id)
        report_text = f"{thread.name}\n{starter.content}"

        verdict = triage.run(report_text)
        action = verdict["action"]

        if action == "flag_human":
            await thread.send(
                f"Couldn't classify this confidently (tier={verdict['tier_used']}). "
                f"Flagging for human review. Possible files: {verdict['retrieved_files']}"
            )

        elif action == "duplicate":
            gl.comment(
                verdict["matched_issue_id"],
                f"Possible duplicate reported on Discord: {thread.jump_url}",
            )
            await thread.send(f"Looks like a duplicate of issue #{verdict['matched_issue_id']}.")

        else:  # action == "create_issue"
            files = verdict["likely_files"] or verdict["retrieved_files"]
            related = verdict.get("related_issue_ids") or []
            description = (
                f"{report_text}\n\n---\n"
                f"Reported via Discord: {thread.jump_url}\n"
                f"Likely files: {files}"
            )
            if related:
                description += f"\nPossibly related issues: {related}"

            issue_iid = gl.create_issue(
                title=thread.name,
                description=description,
                labels=["from-discord"],
            )
            await thread.send(f"Created GitLab issue #{issue_iid}. Likely files: {files}")

    return client


def run():
    cfg = load_config()
    store = Store(cfg.paths.chroma_dir)
    triage = Triage(cfg, store)
    gl = GitLabClient(cfg.gitlab.url, cfg.gitlab.token, cfg.gitlab.project_id)

    bot = build_bot(cfg, triage, gl)
    bot.run(cfg.discord.token)


if __name__ == "__main__":
    run()
