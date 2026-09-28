# mod-triage

Local, model-cascade pipeline that triages Discord bug reports for a game mod:
dedups against known issues, guesses which (static) mod files are affected,
opens a GitLab issue when it's genuinely new, and learns from every merged
fix so the knowledge base keeps improving.

Everything runs locally through Ollama.

## Features

- Automatic triage of bug reports from Discord forum channels
- Duplicate detection against known issues using AI models
- File impact analysis to guess which mod files are affected
- GitLab integration for automatic issue creation and management
- Machine learning loop that improves over time by learning from merged fixes
- All processing runs locally with Ollama - no cloud dependencies

## Architecture

The system follows a model cascade approach:

1. **Embed**: Uses `nomic-embed-text` to create embeddings for both bug reports and mod files
2. **Tier1**: Fast classifier (`gemma3:4b`) that determines if issue is duplicate or novel with confidence score
3. **Tier2**: More detailed code-aware classifier (`qwen3-coder:30b-a3b`) used when tier1 confidence is low

The system builds upon known issues and mod file embeddings to make intelligent decisions about bug reports.

## Setup

```bash
git clone <this repo> mod-triage && cd mod-triage
chmod +x install.sh run.sh
./install.sh
```

`install.sh` installs Ollama if missing, pulls the three models, creates a
virtualenv, installs Python deps, and copies `.env.example` to `.env`.

Then:

1. Fill in `.env`:
   - `DISCORD_BOT_TOKEN`
   - `GITLAB_URL`, `GITLAB_TOKEN` (a project or personal access token with API scope)
   - `GITLAB_WEBHOOK_SECRET` (any random string - you'll also paste this into GitLab's webhook config)
2. Edit `config.yaml`:
   - `gitlab.project_id`
   - `discord.triage_channel_id` (the forum channel ID where bug reports get posted)
   - `paths.mod_files_root` if your mod files live somewhere other than `./mod_files`
3. Drop your mod's files under `mod_files/` (or point `paths.mod_files_root` at them).
4. Build the file index:
   ```bash
   source .venv/bin/activate
   python -m src.index_mod_files
   ```
   Re-run this any time files are added or changed - unchanged files are skipped
   automatically via content hash, so it's cheap to re-run often.
5. In GitLab: Project Settings -> Webhooks -> add `http://<your-host>:8000/gitlab/webhook`,
   enable "Merge request events", and paste the same secret from `.env` into the
   Secret Token field. This is what feeds the learning loop.
6. Sanity-check the cascade before wiring up Discord:
   ```bash
   python scripts/dry_run.py "Player character falls through the floor near the docks"
   ```
7. Run it:
   ```bash
   ./run.sh
   ```

## How It Works

1. A new Discord thread comes in -> embedded -> checked against `known_issues`
   and `mod_files` in Chroma.
2. `gemma3:4b` (tier1) gives a duplicate/novel verdict with a confidence score.
3. Below the confidence threshold -> escalate to `qwen3-coder:30b-a3b` (tier2)
   with richer context (candidate files included).
4. Still low confidence -> flagged in-thread for a human, nothing is auto-created.
5. Confident + duplicate -> comments on the matching GitLab issue.
6. Confident + novel -> creates a GitLab issue with the likely files attached.
7. When a merge request merges, the webhook pulls the diff, summarizes it with
   tier1, and upserts `{issue text -> files actually changed}` into
   `known_issues` as ground truth - every merged fix makes future triage better,
   no fine-tuning required.

## Requirements

- Ollama (for AI models)
- Python 3.8+
- Discord Bot Token
- GitLab Personal Access Token
- GitLab Project ID
