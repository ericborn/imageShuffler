# -*- coding: utf-8 -*-
"""
ComfyUI batch runner for Krea2 workflow.
Reads prompts from prompts.txt, matches loras from loras.jsonl,
submits one image at a time to ComfyUI, waits for completion, repeats.

Run cells/functions from Spyder — no main() guard needed.

@author: eric
"""

import json
import time
import math
import random
import re
import copy
import requests
from pathlib import Path
from datetime import date, datetime

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
COMFY_HOST = "http://127.0.0.1:8188"
WORKFLOW_PROMPT_PATH = Path("data/krea2-python.json")
WORKFLOW_PATH = Path("data/krea2-python.json")

PROMPTS_PATH = Path("data/prompt_test.txt")
LORAS_PATH = Path("data/loras.jsonl")

NODE_PROMPT = "3"          # CLIPTextEncode  -> inputs.text
NODE_SEED = "2"            # KSampler        -> inputs.seed
NODE_LORA = "100"          # Power Lora Loader (rgthree)
NODE_SAVE = "21"           # SaveImage       -> inputs.filename_prefix

DETAIL_LORA = "detail_slider_krea2_loraholic.safetensors"
DETAIL_STRENGTH = 5.0      # fixed strength for the always-on detail lora
MAX_MATCHED_LORAS = 3      # 3 matched + 1 detail = 4 total slots

POLL_INTERVAL = 1          # seconds between /history polls
POLL_TIMEOUT = 900         # seconds before giving up on one image

COMFY_OUTPUT_DIR = Path(r"C:\ComfyUI_windows_portable\ComfyUI")

FORCED_PAIRS = [
    ("penis_girth_krea2_loraholic.safetensors",
     "penis_size_krea2_v2_loraholic.safetensors"),
]

EXCLUSIVE_GROUPS = [
    {"ass_krea2_loraholic.safetensors", "ass_v2_krea2_loraholic.safetensors"},
]

# ----------------------------------------------------------------------------
# file helpers
# ----------------------------------------------------------------------------

def ensure_today_output_dir(base: Path = COMFY_OUTPUT_DIR) -> Path:
    """
    Create the YYYY-MM-DD subfolder ComfyUI's SaveImage node expects,
    relative to its output directory. Safe to call repeatedly; returns
    the folder path. If creation fails, prints and returns the path
    anyway so the caller can decide what to do.
    """
    today = date.today().isoformat()  # yyyy-mm-dd
    folder = base / today
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[fs] could not create output dir {folder}: {e}")
    return folder

def make_filename_prefix(base: str = "output") -> str:
    """
    Return a literal filename prefix like:
        output/2026-09-17/2026-09-17-143052
    ComfyUI will append '_00001_.png' (or similar) to this.
    """
    now = datetime.now()
    day = now.strftime("%Y-%m-%d")
    stamp = now.strftime("%Y-%m-%d-%H%M%S")
    return f"{day}/{stamp}"

# ----------------------------------------------------------------------------
# Loading helpers
# ----------------------------------------------------------------------------

def load_workflow(path: Path = WORKFLOW_PROMPT_PATH) -> dict:
    """Load the API-format workflow JSON."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_prompts(path: Path = PROMPTS_PATH) -> list[str]:
    """One prompt per line, skip blank lines, strip trailing newline."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip()]


def load_loras(path: Path = LORAS_PATH) -> list[dict]:
    """
    JSONL: one object per line.
    Expected keys: filename, strength [min,max], activation words [], keywords []

    Normalizes "activation words" (with a space, as stored in the JSONL) into
    the canonical snake_case key "activation_words" used throughout this file.
    """
    loras = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[lora] skipping line {i}: {e}")
            continue

        # normalize ---------------------------------------------------------
        # accept either spelling, canonical form is snake_case
        if "activation_words" not in obj:
            obj["activation_words"] = obj.pop("activation words", [])
        else:
            obj.pop("activation words", None)

        obj.setdefault("strength", [1.0, 1.0])
        obj.setdefault("activation_words", [])
        obj.setdefault("keywords", [])
        obj.setdefault("notes", "")
        loras.append(obj)
    return loras

# ----------------------------------------------------------------------------
# Matching
# ----------------------------------------------------------------------------

def _keyword_hits(prompt_lower: str, keywords: list[str]) -> int:
    """Case-insensitive substring / regex match count for one lora."""
    hits = 0
    for kw in keywords:
        if not kw:
            continue
        kw_l = kw.lower()
        # try plain substring first (fast path)
        if kw_l in prompt_lower:
            hits += 1
            continue
        # fall back to regex (kw may be a pattern)
        try:
            if re.search(kw, prompt_lower, flags=re.IGNORECASE):
                hits += 1
        except re.error:
            pass
    return hits


def _round_strength(lo: float, hi: float) -> float:
    """Random strength in [lo, hi], rounded to nearest 0.25 (round half up)."""
    if lo == hi:
        raw = float(lo)
    else:
        raw = random.uniform(lo, hi)
    # round half up to nearest 0.25 instead of banker's rounding
    return math.floor(raw * 4 + 0.5) / 4


def _expand_forced_pairs(chosen: list[dict], all_loras: list[dict]) -> list[dict]:
    """
    If a lora in FORCED_PAIRS is chosen, ensure its partner is too.
    Partner is pulled from all_loras and given a fresh random strength.

    Operates on a local copy of the partner so the shared all_loras dicts
    are never mutated.
    """
    by_name = {l["filename"]: l for l in all_loras}
    present = {l["filename"] for l in chosen}

    additions = []
    for a, b in FORCED_PAIRS:
        if (a in present) ^ (b in present):  # exactly one present
            partner_name = b if a in present else a
            partner = by_name.get(partner_name)
            if partner is not None:
                additions.append(partner)
                present.add(partner_name)

    for p in additions:
        lo, hi = p["strength"]
        p = dict(p)  # defensive copy — never mutate shared list
        p["chosen_strength"] = _round_strength(lo, hi)
        chosen.append(p)

    return chosen


def _apply_exclusive_groups(chosen: list[dict]) -> list[dict]:
    """
    Within each EXCLUSIVE_GROUP, keep only one at random.
    Uses filenames for comparison (identity / equality on dicts is fragile).
    """
    for group in EXCLUSIVE_GROUPS:
        matches = [l for l in chosen if l["filename"] in group]
        if len(matches) > 1:
            keep_name = random.choice(matches)["filename"]
            chosen = [
                l for l in chosen
                if l["filename"] not in group or l["filename"] == keep_name
            ]
    return chosen


def match_loras(prompt: str, loras: list[dict]) -> list[dict]:
    """
    Return the matched loras for this prompt.
    Rules:
      - detail lora excluded from the pool
      - mutual-exclusion groups: pick one at random
      - forced pairs: if one is present, add the partner (may exceed 4 total)
      - random 3 when more than 3 match (excluding forced-pair additions)
      - strength rounded to nearest 0.25

    IMPORTANT: the returned dicts are COPIES of the entries in `loras`.
    `chosen_strength` is written only onto the copies, so the caller's
    lora list is never mutated and every call re-rolls strengths.
    """
    prompt_lower = prompt.lower()
    pool = []

    for lora in loras:
        if lora["filename"] == DETAIL_LORA:
            continue
        hits = _keyword_hits(prompt_lower, lora["keywords"])
        if hits > 0:
            pool.append((hits, lora))

    if not pool:
        return []

    # sort by hit count desc, randomize ties
    random.shuffle(pool)
    pool.sort(key=lambda t: t[0], reverse=True)

    # copy the dicts so we never mutate the shared loras list
    chosen = [dict(lora) for _, lora in pool[:MAX_MATCHED_LORAS]]
    chosen = _apply_exclusive_groups(chosen)

    # expand forced pairs AFTER the cap (they're allowed to exceed it)
    chosen = _expand_forced_pairs(chosen, loras)

    # assign strengths to anything that doesn't have one yet.
    # forced-pair additions already got a fresh roll inside _expand_forced_pairs.
    for lora in chosen:
        if "chosen_strength" in lora:
            continue
        lo, hi = lora["strength"]
        lora["chosen_strength"] = _round_strength(lo, hi)

    return chosen


def collect_activation_words(chosen_loras: list[dict]) -> list[str]:
    """Deduplicated activation words from all chosen loras, in order."""
    words = []
    for lora in chosen_loras:
        for w in lora.get("activation_words", []):
            if w and w not in words:
                words.append(w)
    return words

# ----------------------------------------------------------------------------
# Workflow mutation
# ----------------------------------------------------------------------------

def build_prompt_payload(
    workflow: dict,
    prompt: str,
    chosen_loras: list[dict],
) -> dict:
    wf = copy.deepcopy(workflow)

    # 1) prompt text  (+ activation words appended)
    activation = collect_activation_words(chosen_loras)
    full_prompt = prompt
    if activation:
        full_prompt = f"{prompt}, {', '.join(activation)}"
    wf[NODE_PROMPT]["inputs"]["text"] = full_prompt

    # 2) random 12-digit seed
    wf[NODE_SEED]["inputs"]["seed"] = random.randint(0, 999_999_999_999)

    # 3) lora slots — REBUILD the dict in the correct order
    lora_inputs = wf[NODE_LORA]["inputs"]

    # Extract the fixed widgets that must stay at the end
    header = lora_inputs.get("PowerLoraLoaderHeaderWidget")
    add_lora = lora_inputs.get("➕ Add Lora")
    model_ref = lora_inputs.get("model")
    clip_ref = lora_inputs.get("clip")

    # Rebuild the dict in the exact order ComfyUI expects:
    # header → lora_1 → lora_2 → ... → "➕ Add Lora" → model → clip
    new_inputs = {}
    if header is not None:
        new_inputs["PowerLoraLoaderHeaderWidget"] = header

    # Detail lora always in slot 1
    new_inputs["lora_1"] = {
        "on": True,
        "lora": DETAIL_LORA,
        "strength": DETAIL_STRENGTH,
    }

    # Matched loras in slots 2+
    for idx, l in enumerate(chosen_loras, start=2):
        new_inputs[f"lora_{idx}"] = {
            "on": True,
            "lora": l["filename"],
            "strength": l["chosen_strength"],
        }

    # Fixed widgets at the end
    if add_lora is not None:
        new_inputs["➕ Add Lora"] = add_lora
    if model_ref is not None:
        new_inputs["model"] = model_ref
    if clip_ref is not None:
        new_inputs["clip"] = clip_ref

    # Replace the entire inputs dict to guarantee order
    wf[NODE_LORA]["inputs"] = new_inputs

    # 4) output filename prefix
    wf[NODE_SAVE]["inputs"]["filename_prefix"] = make_filename_prefix()

    return wf

# ----------------------------------------------------------------------------
# ComfyUI submission / polling
# ----------------------------------------------------------------------------

def queue_prompt(workflow: dict, client_id: str = "spyder-batch") -> str | None:
    """POST to /prompt, return prompt_id or None on failure."""
    payload = {"prompt": workflow, "client_id": client_id}
    try:
        r = requests.post(f"{COMFY_HOST}/prompt", json=payload, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[queue] request failed: {e}")
        return None

    data = r.json()
    if "prompt_id" not in data:
        print(f"[queue] unexpected response: {data}")
        return None
    return data["prompt_id"]


def wait_for_completion(prompt_id: str, timeout: int = POLL_TIMEOUT) -> bool:
    """
    Poll /history/<id> until the job reports success or error, or until
    we time out.

    A non-empty history entry is NOT sufficient — ComfyUI can insert a
    partial entry while the job is still queued/running. Only treat
    explicit success/completed as done.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{COMFY_HOST}/history/{prompt_id}", timeout=10)
            r.raise_for_status()
            hist = r.json()
        except requests.RequestException as e:
            print(f"[poll] request failed: {e}")
            time.sleep(POLL_INTERVAL)
            continue

        if prompt_id in hist:
            entry = hist[prompt_id]
            status = entry.get("status", {}) if isinstance(entry, dict) else {}
            status_str = status.get("status_str")

            if status.get("completed") or status_str == "success":
                return True
            if status_str == "error":
                print(f"[poll] comfy reported error: {status}")
                return False
            # queued / running / unknown — keep polling

        time.sleep(POLL_INTERVAL)

    print(f"[poll] timed out after {timeout}s waiting for {prompt_id}")
    return False

# ----------------------------------------------------------------------------
# testing section
# running a single prompt at a time to evaluate
# ----------------------------------------------------------------------------

# workflow = load_workflow()
# prompts = load_prompts()
# loras = load_loras()

# print(f"[batch] {len(prompts)} prompts, {len(loras)} loras loaded")

# i = 2
# chosen = match_loras(prompts[i], loras)
# if chosen:
#     names = ", ".join(f"{l['filename']}@{l['chosen_strength']}" for l in chosen)
#     print(f"[batch] loras: {names}")
# else:
#     print("[batch] no loras matched (detail only)")

# payload = None
# try:
#     payload = build_prompt_payload(workflow, prompts[i], chosen)
# except Exception as e:
#     print(f"[batch] failed to build payload: {e}")

# if payload is None:
#     print("[batch] skipping — no payload")
# else:
#     ensure_today_output_dir()
#     prompt_id = queue_prompt(payload)
#     if prompt_id is None:
#         print("[batch] submission failed — skipping")
#     else:
#         print(f"[batch] queued as {prompt_id}, waiting...")
#         ok = wait_for_completion(prompt_id)
#         if not ok:
#             print(f"[batch] generation failed for prompt {i}")
#         else:
#             print("[batch] done")

# print("\n[batch] all prompts processed")

# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------

def run_batch():
    workflow = load_workflow()
    prompts = load_prompts()
    loras = load_loras()

    print(f"[batch] {len(prompts)} prompts, {len(loras)} loras loaded")

    for i, prompt in enumerate(prompts, 1):
        print(f"\n[batch] ({i}/{len(prompts)}) {prompt[:80]}...")

        chosen = match_loras(prompt, loras)
        if chosen:
            names = ", ".join(f"{l['filename']}@{l['chosen_strength']}" for l in chosen)
            print(f"[batch] loras: {names}")
        else:
            print("[batch] no loras matched (detail only)")

        try:
            ensure_today_output_dir()
            payload = build_prompt_payload(workflow, prompt, chosen)
        except Exception as e:
            print(f"[batch] failed to build payload: {e}")
            continue

        prompt_id = queue_prompt(payload)
        if prompt_id is None:
            print("[batch] submission failed — skipping")
            continue

        print(f"[batch] queued as {prompt_id}, waiting...")
        ok = wait_for_completion(prompt_id)
        if not ok:
            print(f"[batch] generation failed for prompt {i}")
            continue

        print("[batch] done")

    print("\n[batch] all prompts processed")

run_batch()