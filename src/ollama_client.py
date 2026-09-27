"""Thin wrapper around Ollama's OpenAI-compatible API.

Model names are never hardcoded here - callers pass them in from config.py,
so swapping a tier's model is a config.yaml edit, not a code change.
"""
import json

from openai import OpenAI


def get_client(host: str) -> OpenAI:
    # api_key is required by the client but ignored by Ollama.
    return OpenAI(base_url=f"{host}/v1", api_key="ollama")


def embed(client: OpenAI, model: str, text: str) -> list[float]:
    resp = client.embeddings.create(model=model, input=text)
    return resp.data[0].embedding


def judge(client: OpenAI, model: str, report_text: str, candidates: list[dict],
          files: list[dict] | None = None) -> dict:
    """Classify the new report against each retrieved candidate issue, and
    guess likely affected files.

    Deliberately does NOT ask for a self-reported confidence float - an LLM's
    "0.87" isn't a calibrated probability, it's a plausible-looking token.
    Instead each candidate gets a categorical label plus concrete evidence.
    The real similarity signal (retrieval distance) already lives on each
    candidate dict from vector_store.py and is combined with the label in
    triage.py, not asked of the model.

    Returns: {classifications: [{issue_id, label, evidence: [str]}],
              likely_files: [str], reasoning: str}

    label is one of: exact_duplicate, same_underlying_bug, related,
    unrelated, insufficient_information.
    """
    candidate_block = "\n".join(
        f"- id={c['id']} status={c['metadata'].get('status', 'open')} "
        f"retrieval_distance={c['distance']:.3f}: {c['document'][:200]}"
        for c in candidates
    ) or "(none found)"

    file_block = ""
    if files:
        file_block = "\n\nCandidate files:\n" + "\n".join(
            f"- {f['metadata']['path']}: {f['document'][:150]}" for f in files
        )

    system = (
        "You triage bug reports for a game mod. For EACH known issue listed "
        "below, classify the relationship between it and the new report as "
        "exactly one of: exact_duplicate, same_underlying_bug, related, "
        "unrelated, insufficient_information. Do not invent a confidence "
        "percentage - use the categorical label, and cite concrete evidence "
        "(matching crash signature, subsystem, reproduction steps, affected "
        "version, etc). Also guess which mod files are likely affected. "
        "Respond ONLY with JSON matching this schema: "
        '{"classifications": [{"issue_id": string, "label": string, '
        '"evidence": [string]}], "likely_files": [string], "reasoning": string}'
    )
    user = f"New report:\n{report_text}\n\nKnown issues:\n{candidate_block}{file_block}"

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content)


def summarize(client: OpenAI, model: str, text: str, instruction: str) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": text[:4000]},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content.strip()
