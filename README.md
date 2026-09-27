# mod-triage

Local, model-cascade pipeline that triages Discord bug reports for a game mod:
dedups against known issues, guesses which (static) mod files are affected,
opens a GitLab issue when it's genuinely new, and learns from every merged
fix so the knowledge base keeps improving.

Everything runs locally through Ollama - no API keys, no per-token cost.

## What's inside

```
mod-triage/
├── install.sh              # one-shot setup: Ollama, models, venv, deps
├── run.sh                  # starts the bot + webhook server
├── requirements.txt
├── config.yaml             # models, thresholds, paths - edit this, not the code
├── .env.example            # secrets template (copy to .env)
├── mod_files/               # put your mod's moddable files here
├── src/
│   ├── config.py            # loads config.yaml + .env
│   ├── ollama_client.py     # embed() + judge() against Ollama's OpenAI-compatible API
│   ├── vector_store.py      # Chroma wrapper: mod_files + known_issues collections
│   ├── index_mod_files.py   # (re)indexes the static mod file tree
│   ├── triage.py            # the tier1 -> tier2 cascade
│   ├── gitlab_client.py     # python-gitlab wrapper
│   ├── discord_bot.py       # listens for new bug-report threads
│   ├── merge_webhook.py     # FastAPI receiver: learns from merged MRs
│   └── main.py              # runs the bot + webhook together
└── scripts/
    └── dry_run.py           # test the cascade from the CLI, no Discord/GitLab needed
```

## Model cascade (all via Ollama, all free/open-weight)

| Tier | Model | Role |
|---|---|---|
| embed | `nomic-embed-text` | embeddings for both retrieval indices |
| tier1 | `gemma3:4b` | fast first-pass classify (duplicate? confidence? file guess) |
| tier2 | `qwen3-coder:30b-a3b` | only runs when tier1 confidence is low; code-aware, better at scoping affected files |

Swap any of these by editing `config.yaml` - nothing in `src/` hardcodes a model name.
`qwen3-coder:30b-a3b` is a ~6GB VRAM download (MoE, 3B active params) despite the
30B label; check `ollama list` on ollama.com for anything newer if you're setting
this up a while after reading this.

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

## How the pieces fit together

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

## Notes

- `.env` holds real secrets - it's already covered by `.gitignore`, don't commit it.
- The webhook server binds `0.0.0.0:8000` by default; put it behind a reverse
  proxy with TLS if it's reachable from the internet, since GitLab needs to
  reach it to fire webhooks.
- Everything here is a working skeleton, not a hardened production service -
  add retries/logging/error handling as it earns its keep.
