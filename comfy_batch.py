# -*- coding: utf-8 -*-
"""
ComfyUI batch runner for Krea2 workflow.
Reads prompts from prompts.txt, matches loras from loras.jsonl,
submits one image at a time to ComfyUI, waits for completion, repeats.

Also embeds a UI-format workflow in the PNG metadata (via extra_pnginfo)
so the generated images can be dragged back into the ComfyUI canvas and
have the Power Lora Loader / KSampler / prompt nodes populated correctly.

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

# API-format workflow (the "prompt" graph sent to /prompt)
WORKFLOW_PROMPT_PATH = Path("data/krea2_workflow_prompt.json")
# UI-format workflow (litegraph, embedded into PNG metadata as "workflow")
WORKFLOW_PATH = Path("data/krea2_workflow.json")

PROMPTS_PATH = Path("data/prompt_test.txt")
LORAS_PATH = Path("data/loras.jsonl")

# --- API-side node IDs ---
NODE_PROMPT = "3"          # CLIPTextEncode  -> inputs.text
NODE_SEED = "2"            # KSampler        -> inputs.seed
NODE_LORA = "100"          # Power Lora Loader (rgthree)
NODE_SAVE = "21"           # SaveImage       -> inputs.filename_prefix

# --- UI-side node IDs (litegraph) ---
UI_NODE_PROMPT = 49        # PrimitiveNode "Prompt"
UI_NODE_SEED = 2           # KSamplerMain
UI_NODE_LORA = 100         # Power Lora Loader (rgthree)
UI_NODE_SAVE = 21          # SaveImage

# Number of matched-lora slots the UI Power Lora Loader template has
# (i.e. lora_2 .. lora_N). Your snippet shows 4 matched slots (2..5).
UI_MATCHED_SLOTS = 4

DETAIL_LORA = "detail_slider_krea2_loraholic.safetensors"
DETAIL_STRENGTH = 5.0      # fixed strength for the always-on detail lora
MAX_MATCHED_LORAS = 3      # 3 matched + 1 detail = 4 total slots (API side)

POLL_INTERVAL = 1          # seconds between /history polls
POLL_TIMEOUT = 900         # seconds before giving up on one image

COMFY_OUTPUT_DIR = Path(r"C:\ComfyUI_windows_portable\ComfyUI")

FORCED_PAIRS = [
    ("penis_girth_krea2_loraholic.safetensors",
     "penis_size_krea2_v2_loraholic.safetensors")
]

EXCLUSIVE_GROUPS = [
    {"ass_krea2_loraholic.safetensors", "ass_v2_krea2_loraholic.safetensors"},    
    {"anal_helper_krea2_loraholic.safetensors", "self_anal_fingering.safetensors",
     "krea2-OnlyAnal_v1-step11070-k3nk.safetensors", "k_doggyadrianoanal.safetensors",
     "Krea2_fingering_V0.1.safetensors", "ShemaleHugeDildoV1"},
    {"self_anal_fingering.safetensors", "Krea2_fingering_V0.safetensors"}
]

# ----------------------------------------------------------------------------
# file helpers
# ----------------------------------------------------------------------------

def ensure_today_output_dir(base: Path = COMFY_OUTPUT_DIR) -> Path:
    """
    Create the YYYY-MM-DD subfolder ComfyUI's SaveImage node expects,
    relative to its output directory. Safe to call repeatedly; returns
    the folder path.
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
        2026-09-17/2026-09-17-143052
    ComfyUI will append '_00001_.png' (or similar) to this.
    """
    now = datetime.now()
    day = now.strftime("%Y-%m-%d")
    stamp = now.strftime("%Y-%m-%d-%H%M%S")
    return f"{day}/{stamp}"

# ----------------------------------------------------------------------------
# Loading helpers
# ----------------------------------------------------------------------------

def load_api_workflow(path: Path = WORKFLOW_PROMPT_PATH) -> dict:
    """Load the API-format workflow JSON."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_ui_workflow(path: Path = WORKFLOW_PATH) -> dict:
    """Load the UI-format (litegraph) workflow JSON."""
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

    Normalizes "activation words" (with a space) into "activation_words".
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
        if kw_l in prompt_lower:
            hits += 1
            continue
        try:
            if re.search(kw, prompt_lower, flags=re.IGNORECASE):
                hits += 1
        except re.error:
            pass
    return hits

def _keyword_hits_exact(prompt_lower: str, keywords: list[str]) -> int:
    """Case-insensitive whole-word match count for one lora."""
    hits = 0
    for kw in keywords:
        if not kw:
            continue
        # \b = word boundary; re.escape handles any regex-special chars in kw
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, prompt_lower, flags=re.IGNORECASE):
            hits += 1
    return hits

def _round_strength(lo: float, hi: float) -> float:
    """Random strength in [lo, hi], rounded to nearest 0.25 (round half up)."""
    if lo == hi:
        raw = float(lo)
    else:
        raw = random.uniform(lo, hi)
    return math.floor(raw * 4 + 0.5) / 4


def _expand_forced_pairs(chosen: list[dict], all_loras: list[dict]) -> list[dict]:
    """
    If a lora in FORCED_PAIRS is chosen, ensure its partner is too.
    Partner is pulled from all_loras and given a fresh random strength.
    """
    by_name = {l["filename"]: l for l in all_loras}
    present = {l["filename"] for l in chosen}

    additions = []
    for a, b in FORCED_PAIRS:
        if (a in present) ^ (b in present):
            partner_name = b if a in present else a
            partner = by_name.get(partner_name)
            if partner is not None:
                additions.append(partner)
                present.add(partner_name)

    for p in additions:
        lo, hi = p["strength"]
        p = dict(p)
        p["chosen_strength"] = _round_strength(lo, hi)
        chosen.append(p)

    return chosen


def _apply_exclusive_groups(chosen: list[dict]) -> list[dict]:
    """Within each EXCLUSIVE_GROUP, keep only one at random."""
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
    Return the matched loras for this prompt. Returned dicts are COPIES,
    so the caller's lora list is never mutated and every call re-rolls
    strengths.
    """
    prompt_lower = prompt.lower()
    pool = []

    for lora in loras:
        if lora["filename"] == DETAIL_LORA:
            continue
        hits = _keyword_hits(prompt_lower, lora["fuzzywords"])        
        hits += _keyword_hits_exact(prompt_lower, lora["keywords"])
        if hits > 0:
            pool.append((hits, lora))

    if not pool:
        return []

    random.shuffle(pool)
    pool.sort(key=lambda t: t[0], reverse=True)

    chosen = [dict(lora) for _, lora in pool[:MAX_MATCHED_LORAS]]
    chosen = _apply_exclusive_groups(chosen)
    chosen = _expand_forced_pairs(chosen, loras)

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
# API workflow mutation
# ----------------------------------------------------------------------------

def build_api_payload(
    api_workflow: dict,
    prompt: str,
    chosen_loras: list[dict],
    seed: int,
) -> dict:
    """
    Produce the API-format graph for submission. Seed is passed in so the
    UI graph can be patched to match.
    """
    wf = copy.deepcopy(api_workflow)

    # 1) prompt text (+ activation words appended)
    activation = collect_activation_words(chosen_loras)
    full_prompt = prompt
    if activation:
        full_prompt = f"{prompt}, {', '.join(activation)}"
    wf[NODE_PROMPT]["inputs"]["text"] = full_prompt

    # 2) seed
    wf[NODE_SEED]["inputs"]["seed"] = seed

    # 3) lora slots — rebuild the dict in the exact order ComfyUI expects
    lora_inputs = wf[NODE_LORA]["inputs"]
    header = lora_inputs.get("PowerLoraLoaderHeaderWidget")
    add_lora = lora_inputs.get("➕ Add Lora")
    model_ref = lora_inputs.get("model")
    clip_ref = lora_inputs.get("clip")

    new_inputs = {}
    if header is not None:
        new_inputs["PowerLoraLoaderHeaderWidget"] = header

    new_inputs["lora_1"] = {
        "on": True,
        "lora": DETAIL_LORA,
        "strength": DETAIL_STRENGTH,
    }

    for idx, l in enumerate(chosen_loras, start=2):
        new_inputs[f"lora_{idx}"] = {
            "on": True,
            "lora": l["filename"],
            "strength": l["chosen_strength"],
        }

    if add_lora is not None:
        new_inputs["➕ Add Lora"] = add_lora
    if model_ref is not None:
        new_inputs["model"] = model_ref
    if clip_ref is not None:
        new_inputs["clip"] = clip_ref

    wf[NODE_LORA]["inputs"] = new_inputs

    # 4) output filename prefix
    wf[NODE_SAVE]["inputs"]["filename_prefix"] = make_filename_prefix()

    return wf

# ----------------------------------------------------------------------------
# UI workflow mutation
# ----------------------------------------------------------------------------

def find_ui_node(ui_workflow: dict, node_id: int) -> dict | None:
    """UI workflows store nodes under workflow['nodes']."""
    for n in ui_workflow.get("nodes", []):
        # UI ids can be int or str depending on export; compare as int
        try:
            if int(n.get("id")) == int(node_id):
                return n
        except (TypeError, ValueError):
            continue
    return None


def _patch_ui_widgets(node: dict, index: int, named_key: str, value) -> None:
    """Write to both widgets_values[index] and widgets_values_named[named_key]."""
    wv = node.get("widgets_values")
    if isinstance(wv, list) and len(wv) > index:
        wv[index] = value
    named = node.get("widgets_values_named")
    if isinstance(named, dict):
        named[named_key] = value


def patch_ui_prompt_text(ui_workflow: dict, node_id: int, text: str) -> None:
    node = find_ui_node(ui_workflow, node_id)
    if node is None:
        print(f"[ui] prompt node {node_id} not found")
        return
    _patch_ui_widgets(node, 0, "value", text)


def patch_ui_ksampler_seed(ui_workflow: dict, node_id: int, seed: int) -> None:
    node = find_ui_node(ui_workflow, node_id)
    if node is None:
        print(f"[ui] ksampler node {node_id} not found")
        return
    _patch_ui_widgets(node, 0, "seed", seed)


def patch_ui_power_lora(
    ui_workflow: dict,
    node_id: int,
    chosen_loras: list[dict],
) -> None:
    """
    Patch both widgets_values and widgets_values_named on the Power Lora
    Loader node so a PNG reload reconstructs the same lora configuration.

    Layout (from the saved workflow):
      widgets_values = [
        {} (divider),
        {"type": "PowerLoraLoaderHeaderWidget"},
        lora_1 (detail, always on),
        lora_2..lora_{1+UI_MATCHED_SLOTS},
        {} (add-lora widget),
        "" (trailing)
      ]
    """
    node = find_ui_node(ui_workflow, node_id)
    if node is None:
        print(f"[ui] power lora node {node_id} not found")
        return

    detail_slot = {
        "on": True,
        "lora": DETAIL_LORA,
        "strength": DETAIL_STRENGTH,
        "strengthTwo": None,
    }

    # Build up to UI_MATCHED_SLOTS entries. Pad with disabled placeholders
    # so the frontend still renders the same number of rows.
    slots = []
    for l in chosen_loras[:UI_MATCHED_SLOTS]:
        slots.append({
            "on": True,
            "lora": l["filename"],
            "strength": l["chosen_strength"],
            "strengthTwo": None,
        })

    # Determine a "filler" lora name to use for the disabled padding slots.
    # Prefer whatever is already in the template so we don't introduce
    # nonexistent files.
    existing_names = []
    wv = node.get("widgets_values")
    if isinstance(wv, list):
        for item in wv:
            if isinstance(item, dict) and "lora" in item and item["lora"]:
                existing_names.append(item["lora"])
    filler_lora = None
    for name in existing_names:
        if name != DETAIL_LORA:
            filler_lora = name
            break
    if filler_lora is None:
        filler_lora = DETAIL_LORA  # last resort

    while len(slots) < UI_MATCHED_SLOTS:
        slots.append({
            "on": False,
            "lora": filler_lora,
            "strength": 1.0,
            "strengthTwo": None,
        })

    # ---- positional form ----
    if isinstance(wv, list):
        # Ensure the list is long enough: header + detail + N slots + 2 trailing
        needed = 2 + 1 + UI_MATCHED_SLOTS + 2
        while len(wv) < needed:
            wv.append({})
        wv[0] = {}
        wv[1] = {"type": "PowerLoraLoaderHeaderWidget"}
        wv[2] = detail_slot
        for i, slot in enumerate(slots):
            wv[3 + i] = slot
        # trailing widgets
        wv[3 + UI_MATCHED_SLOTS] = {}
        wv[4 + UI_MATCHED_SLOTS] = ""
        node["widgets_values"] = wv

    # ---- named form ----
    named = node.get("widgets_values_named")
    if isinstance(named, dict):
        named["divider"] = {}
        named["PowerLoraLoaderHeaderWidget"] = {
            "type": "PowerLoraLoaderHeaderWidget"
        }
        named["lora_1"] = detail_slot
        for i, slot in enumerate(slots, start=2):
            named[f"lora_{i}"] = slot
        named["➕ Add Lora"] = ""
        node["widgets_values_named"] = named


def patch_ui_save_prefix(ui_workflow: dict, node_id: int, prefix: str) -> None:
    node = find_ui_node(ui_workflow, node_id)
    if node is None:
        # SaveImage node id may differ between API/UI exports; not fatal.
        print(f"[ui] save node {node_id} not found (prefix not patched)")
        return
    _patch_ui_widgets(node, 0, "filename_prefix", prefix)


def build_ui_payload(
    ui_workflow: dict,
    prompt: str,
    chosen_loras: list[dict],
    seed: int,
    filename_prefix: str,
) -> dict:
    """Deep-copy the UI workflow and patch it to match the API submission."""
    ui = copy.deepcopy(ui_workflow)

    activation = collect_activation_words(chosen_loras)
    full_prompt = prompt
    if activation:
        full_prompt = f"{prompt}, {', '.join(activation)}"

    patch_ui_prompt_text(ui, UI_NODE_PROMPT, full_prompt)
    patch_ui_ksampler_seed(ui, UI_NODE_SEED, seed)
    patch_ui_power_lora(ui, UI_NODE_LORA, chosen_loras)
    patch_ui_save_prefix(ui, UI_NODE_SAVE, filename_prefix)

    return ui

# ----------------------------------------------------------------------------
# ComfyUI submission / polling
# ----------------------------------------------------------------------------

def queue_prompt(
    api_workflow: dict,
    ui_workflow: dict,
    client_id: str = "spyder-batch",
) -> str | None:
    """
    POST to /prompt with the API graph plus the UI graph in extra_pnginfo
    so SaveImage writes it into the PNG's `workflow` metadata chunk.
    """
    payload = {
        "prompt": api_workflow,
        "client_id": client_id,
        "extra_data": {
            "extra_pnginfo": {
                "workflow": ui_workflow,
            }
        },
    }
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
    we time out. A non-empty history entry is NOT sufficient — ComfyUI can
    insert a partial entry while the job is still queued/running.
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

        time.sleep(POLL_INTERVAL)

    print(f"[poll] timed out after {timeout}s waiting for {prompt_id}")
    return False

# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------

def run_batch():
    api_workflow = load_api_workflow()
    ui_workflow = load_ui_workflow()
    prompts = load_prompts()
    loras = load_loras()

    print(f"[batch] {len(prompts)} prompts, {len(loras)} loras loaded")
    print(f"[batch] UI nodes: {len(ui_workflow.get('nodes', []))}")

    for i, prompt in enumerate(prompts, 1):
        print(f"\n[batch] ({i}/{len(prompts)}) {prompt[:80]}...")

        chosen = match_loras(prompt, loras)
        if chosen:
            names = ", ".join(
                f"{l['filename']}@{l['chosen_strength']}" for l in chosen
            )
            print(f"[batch] loras: {names}")
        else:
            print("[batch] no loras matched (detail only)")

        # Roll the seed once so API and UI stay in sync
        seed = random.randint(0, 999_999_999_999)
        filename_prefix = make_filename_prefix()

        try:
            ensure_today_output_dir()
            api_payload = build_api_payload(
                api_workflow, prompt, chosen, seed
            )
            ui_payload = build_ui_payload(
                ui_workflow, prompt, chosen, seed, filename_prefix
            )
        except Exception as e:
            print(f"[batch] failed to build payload: {e}")
            continue

        prompt_id = queue_prompt(api_payload, ui_payload)
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
