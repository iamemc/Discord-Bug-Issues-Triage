#!/usr/bin/env bash
set -euo pipefail

echo "== mod-triage installer =="

# 1. Ollama
if ! command -v ollama &> /dev/null; then
  echo "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
else
  echo "Ollama already installed."
fi

if ! pgrep -x "ollama" > /dev/null 2>&1; then
  echo "Starting Ollama server..."
  nohup ollama serve > /tmp/ollama.log 2>&1 &
  sleep 3
fi

echo "Pulling models (qwen3-coder is a large download - this can take a while)..."
ollama pull nomic-embed-text
ollama pull gemma3:4b
ollama pull qwen3-coder:30b-a3b

# 2. Python environment
if [ ! -d ".venv" ]; then
  echo "Creating virtualenv..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 3. Secrets template
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from template."
fi

# 4. Data dirs
mkdir -p data/chroma mod_files

cat <<'EOF'

Setup complete. Next steps:
  1. Edit .env - DISCORD_BOT_TOKEN, GITLAB_URL, GITLAB_TOKEN, GITLAB_WEBHOOK_SECRET
  2. Edit config.yaml - gitlab.project_id, discord.triage_channel_id, paths.mod_files_root
  3. Put your mod's files under ./mod_files/
  4. source .venv/bin/activate && python -m src.index_mod_files
  5. python scripts/dry_run.py "example bug report text"   # sanity check
  6. Add a GitLab webhook -> http://<your-host>:8000/gitlab/webhook (Merge request events)
  7. ./run.sh
EOF
