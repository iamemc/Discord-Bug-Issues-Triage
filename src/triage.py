"""The dedup/triage cascade: embed -> retrieve -> judge (tier1) -> maybe
escalate (tier2) -> deterministic decision. Callers (discord_bot.py,
scripts/dry_run.py) act on verdict["action"] - this module only decides,
it never acts.

The decision is made here in plain Python, not by asking a model to output
a single verdict. The model's job is narrower: classify the new report
against each retrieved candidate with a category and evidence. Whether that
adds up to "duplicate", "new issue", or "flag a human" is a deterministic
rule over those categories plus the real retrieval distance - never a
self-reported confidence number.
"""
from .ollama_client import get_client, embed, judge

# Priority order when picking the "best" (most specific) classification
# across all retrieved candidates - lower rank wins.
_LABEL_RANK = {
    "exact_duplicate": 0,
    "same_underlying_bug": 1,
    "related": 2,
    "insufficient_information": 3,
    "unrelated": 4,
}
_DUPLICATE_LABELS = {"exact_duplicate", "same_underlying_bug"}


def _best_classification(classifications: list[dict]) -> dict | None:
    if not classifications:
        return None
    return min(classifications, key=lambda c: _LABEL_RANK.get(c.get("label"), 99))


class Triage:
    def __init__(self, cfg, store):
        self.cfg = cfg
        self.client = get_client(cfg.ollama.host)
        self.store = store

    def run(self, report_text: str) -> dict:
        emb = embed(self.client, self.cfg.models.embed, report_text)

        issues = self.store.query(self.store.known_issues, emb, k=self.cfg.thresholds.top_k)
        files = self.store.query(self.store.mod_files, emb, k=self.cfg.thresholds.top_k)

        result = judge(self.client, self.cfg.models.tier1, report_text, issues)
        tier_used = "tier1"
        best = _best_classification(result.get("classifications", []))

        # Escalate on a real signal of ambiguity - tier1 couldn't commit to
        # anything more specific than "insufficient_information" - not on a
        # threshold applied to a number the model made up about itself.
        if best is None or best.get("label") == "insufficient_information":
            result = judge(self.client, self.cfg.models.tier2, report_text, issues, files)
            tier_used = "tier2"
            best = _best_classification(result.get("classifications", []))

        verdict = {
            "tier_used": tier_used,
            "classifications": result.get("classifications", []),
            "likely_files": result.get("likely_files") or [],
            "retrieved_files": [f["metadata"]["path"] for f in files],
            "reasoning": result.get("reasoning", ""),
        }

        if best is None or best.get("label") == "insufficient_information":
            verdict["action"] = "flag_human"

        elif best["label"] in _DUPLICATE_LABELS:
            verdict["action"] = "duplicate"
            verdict["matched_issue_id"] = best["issue_id"]
            # Attach the real retrieval signal for logging and future
            # calibration - this is measured, not self-reported.
            match = next((c for c in issues if c["id"] == best["issue_id"]), None)
            verdict["retrieval_distance"] = match["distance"] if match else None

        else:  # "related" or "unrelated" candidates only -> genuinely new
            verdict["action"] = "create_issue"
            verdict["related_issue_ids"] = [
                c["issue_id"] for c in result.get("classifications", [])
                if c.get("label") == "related"
            ]

        return verdict
