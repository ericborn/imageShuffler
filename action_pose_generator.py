# -*- coding: utf-8 -*-
"""
Created on Thu Sep 24 16:19:01 2026

@author: eric

# if there is one giver/reciver change prompt to not be plural
# givers are changes to giver is
# clean data to remove m/f/mtf from action and details
"""

import json
import random
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Character:
    """Represents a single selected character with an assigned gender."""
    gender: str
    role: str  # "receiver" or "giver"
    index: int  # 1-based index within its role group
    character_id: str = ""  # filled in after all chars are known

    def __post_init__(self):
        self.character_id = f"{self.role[0].upper()}{self.index}"


@dataclass
class PoseResult:
    """The final result of the primary + additional workflow."""
    action: str
    additional: Optional[dict] = None  # {"secondary_action": str, "details": str}

# ---- Number -> word
_NUM_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
}


def _number_word(n: int) -> str:
    """Return 'one', 'two', ... falling back to the digit for large n."""
    return _NUM_WORDS.get(n, str(n))


def _singularize_gender(gender: str) -> str:
    """Map a gender token to its singular noun form."""
    g = gender.strip().lower()
    mapping = {
        "male": "man",
        "man": "man",
        "female": "woman",
        "woman": "woman",
        "mtf": "trans female",
    }
    return mapping.get(g, g)


def _pluralize_gender(gender: str) -> str:
    """Map a gender token to its plural noun form."""
    g = gender.strip().lower()
    mapping = {
        "male": "men",
        "man": "men",
        "female": "women",
        "woman": "women",
        "mtf": "trans women",
    }
    return mapping.get(g, g + "s")

def _capitalize_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _join_with_and(items: list[str]) -> str:
    """Join items with commas + 'and': ['a','b','c'] -> 'a, b, and c'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _format_group(genders: list[str]) -> str:
    """
    Given a list of gender tokens (e.g. ['female','female','male']),
    return a phrase like 'two women and one man'.
    Returns '' for an empty list.
    """
    if not genders:
        return ""

    # Preserve first-seen order for stable, natural phrasing.
    counts: dict[str, int] = {}
    order: list[str] = []
    for g in genders:
        key = g.strip().lower()
        if key not in counts:
            counts[key] = 0
            order.append(key)
        counts[key] += 1

    pieces: list[str] = []
    for key in order:
        n = counts[key]
        noun = _singularize_gender(key) if n == 1 else _pluralize_gender(key)
        pieces.append(f"{_number_word(n)} {noun}")

    return _join_with_and(pieces)


def _number_word(n: int) -> str:
    """Return 'one', 'two', ... falling back to the digit for large n."""
    return _NUM_WORDS.get(n, str(n))


def _singularize_gender(gender: str) -> str:
    """Map a gender token to its singular noun form."""
    g = gender.strip().lower()
    mapping = {
        "male": "man",
        "man": "man",
        "female": "woman",
        "woman": "woman",
        "mtf": "MTF",
        "ftm": "FTM",
        "nonbinary": "nonbinary person",
        "non-binary": "nonbinary person",
        "unspecified": "person",
    }
    return mapping.get(g, g)


def _pluralize_gender(gender: str) -> str:
    """Map a gender token to its plural noun form."""
    g = gender.strip().lower()
    mapping = {
        "male": "men",
        "man": "men",
        "female": "women",
        "woman": "women",
        "mtf": "MTFs",
        "ftm": "FTMs",
        "nonbinary": "nonbinary people",
        "non-binary": "nonbinary people",
        "unspecified": "people",
    }
    return mapping.get(g, g + "s")


def _capitalize_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _join_with_and(items: list[str]) -> str:
    """Join items with commas + 'and': ['a','b','c'] -> 'a, b, and c'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _format_group(genders: list[str]) -> str:
    """
    Given a list of gender tokens (e.g. ['female','female','male']),
    return a phrase like 'two women and one man'.
    Returns '' for an empty list.
    """
    if not genders:
        return ""

    # Preserve first-seen order for stable, natural phrasing.
    counts: dict[str, int] = {}
    order: list[str] = []
    for g in genders:
        key = g.strip().lower()
        if key not in counts:
            counts[key] = 0
            order.append(key)
        counts[key] += 1

    pieces: list[str] = []
    for key in order:
        n = counts[key]
        noun = _singularize_gender(key) if n == 1 else _pluralize_gender(key)
        pieces.append(f"{_number_word(n)} {noun}")

    return _join_with_and(pieces)


def load_jsonl(path: str, sfw_switch: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        json_list = [json.loads(line) for line in f if line.strip()]
        if sfw_switch != "any":
            output_list = []
            for group in json_list:
                if group["group"] == sfw_switch:
                    output_list.append(group)
            return output_list
        else:
            return json_list


def roll_character_counts(pose: dict) -> tuple[int, int]:
    """
    Returns (num_receivers, num_givers).

    Logic:
    - If min_num_giver == 0, no givers needed -> only roll receivers.
    - Else 50/50 roll which side rolls first.
    - First side rolls min..max. If it lands on char_cap, subtract 1
      so at least one slot remains for the other side.
    - Second side then rolls its own min..max (respecting cap).
    """
    r_min = int(pose["min_num_receiver"])
    r_max = int(pose["max_num_receiver"])
    g_min = int(pose["min_num_giver"])
    g_max = int(pose["max_num_giver"])
    cap = int(pose["char_cap"])

    # Case: no givers at all
    if g_min == 0:
        num_rec = random.randint(r_min, min(r_max, cap))
        return num_rec, 0

    first_is_receiver = random.random() < 0.5

    if first_is_receiver:
        num_rec = random.randint(r_min, r_max)
        if num_rec >= cap:
            num_rec = cap - 1  # reserve 1 slot for a giver
        # remaining slots for givers
        g_max_effective = min(g_max, cap - num_rec)
        num_giv = random.randint(g_min, g_max_effective)
    else:
        num_giv = random.randint(g_min, g_max)
        if num_giv >= cap:
            num_giv = cap - 1
        r_max_effective = min(r_max, cap - num_giv)
        num_rec = random.randint(r_min, r_max_effective)

    return num_rec, num_giv


def pick_genders(gender_field: str, count: int) -> list[str]:
    """
    gender_field is a comma-separated string like "male,female".
    Rolls individually for each character so counts can vary.
    """
    options = [g.strip() for g in gender_field.split(",") if g.strip()]
    if not options:
        return ["unspecified"] * count
    return [random.choice(options) for _ in range(count)]


def build_characters(pose: dict) -> tuple[list[Character], list[Character]]:
    num_rec, num_giv = roll_character_counts(pose)

    rec_genders = pick_genders(pose["receiver_gender"], num_rec)
    giv_genders = pick_genders(pose["giver_gender"], num_giv) if num_giv else []

    receivers = [Character(g, "receiver", i + 1) for i, g in enumerate(rec_genders)]
    givers = [Character(g, "giver", i + 1) for i, g in enumerate(giv_genders)]
    return receivers, givers


def additional_details_enabled(pose: dict) -> bool:
    """50/50 roll, but only if the pose actually allows additional details."""
    allowed = pose.get("allow_additional_details", "").strip()
    if not allowed:
        return False
    return random.random() < 0.5


def gender_overlap(selected: list[Character], allowed_field: str) -> bool:
    """True if any selected character's gender is in the allowed gender list."""
    allowed = {g.strip().lower() for g in allowed_field.split(",") if g.strip()}
    return any(c.gender.lower() in allowed for c in selected)


def filter_by_gender(pool: list[Character], allowed_field: str) -> list[Character]:
    allowed = {g.strip().lower() for g in allowed_field.split(",") if g.strip()}
    return [c for c in pool if c.gender.lower() in allowed]


def select_additional(
    pose: dict,
    receivers: list[Character],
    givers: list[Character],
    additional_list: list[dict],
) -> Optional[dict]:
    """
    Returns a dict describing the selected additional detail, or None if
    nothing applicable was found.

    NOTE: Kept for reference but no longer called by process_pose.
    """
    # Filter candidates to those linked from allow_additional_details
    allowed_names = {
        a.strip().lower()
        for a in pose.get("allow_additional_details", "").split(",")
        if a.strip()
    }
    candidates = [
        a for a in additional_list
        if a["secondary_action"].strip().lower() in allowed_names
    ]
    if not candidates:
        return None

    # Shuffle so we don't always pick the first candidate
    random.shuffle(candidates)

    for add in candidates:
        applies_to = add.get("applies_to", "").strip().lower()
        a_r_min = int(add["min_num_receiver"])
        a_r_max = int(add["max_num_receiver"])
        a_g_min = int(add["min_num_giver"])
        a_g_max = int(add["max_num_giver"])

        # ---- Applies to ALL characters (global detail) ----
        if a_r_min == 0 and a_g_min == 0:
            return {
                "secondary_action": add["secondary_action"],
                "details": add.get("additional_details", ""),
                "applies_to": "all",
                "receivers": [],
                "givers": [],
            }

        # ---- Applies to receivers only ----
        if applies_to == "receiver":
            if not gender_overlap(receivers, add["receiver_gender"]):
                continue
            eligible_rec = filter_by_gender(receivers, add["receiver_gender"])
            if not eligible_rec:
                continue
            upper = min(a_r_max, len(eligible_rec))
            if upper < a_r_min:
                continue
            n = random.randint(a_r_min, upper)
            chosen_rec = random.sample(eligible_rec, n)

            chosen_giv: list[Character] = []
            if a_g_min > 0:
                if not givers:
                    continue
                eligible_giv = filter_by_gender(givers, add["giver_gender"])
                if not eligible_giv:
                    continue
                upper_g = min(a_g_max, len(eligible_giv))
                if upper_g < a_g_min:
                    continue
                n_g = random.randint(a_g_min, upper_g)
                chosen_giv = random.sample(eligible_giv, n_g)

            return {
                "secondary_action": add["secondary_action"],
                "details": add.get("additional_details", ""),
                "applies_to": "receiver",
                "receivers": chosen_rec,
                "givers": chosen_giv,
            }

        # ---- Applies to givers only ----
        if applies_to == "giver":
            if not givers:
                continue
            if not gender_overlap(givers, add["giver_gender"]):
                continue
            eligible_giv = filter_by_gender(givers, add["giver_gender"])
            if not eligible_giv:
                continue
            upper = min(a_g_max, len(eligible_giv))
            if upper < a_g_min:
                continue
            n = random.randint(a_g_min, upper)
            chosen_giv = random.sample(eligible_giv, n)

            chosen_rec: list[Character] = []
            if a_r_min > 0:
                if not receivers:
                    continue
                eligible_rec = filter_by_gender(receivers, add["receiver_gender"])
                if not eligible_rec:
                    continue
                upper_r = min(a_r_max, len(eligible_rec))
                if upper_r < a_r_min:
                    continue
                n_r = random.randint(a_r_min, upper_r)
                chosen_rec = random.sample(eligible_rec, n_r)

            return {
                "secondary_action": add["secondary_action"],
                "details": add.get("additional_details", ""),
                "applies_to": "giver",
                "receivers": chosen_rec,
                "givers": chosen_giv,
            }

        # ---- Applies to ALL as dynamic pairing ----
        if applies_to == "all":
            everyone = receivers + givers
            if not everyone:
                continue
            # Need at least (min_rec + min_giv) distinct characters
            min_total = max(a_r_min, 1) + a_g_min
            if len(everyone) < min_total:
                continue
            shuffled = everyone[:]
            random.shuffle(shuffled)

            n_r = random.randint(max(a_r_min, 1), min(a_r_max, len(shuffled) - a_g_min))
            chosen_rec = shuffled[:n_r]
            remaining = shuffled[n_r:]
            chosen_giv = []
            if a_g_min > 0 and remaining:
                n_g = random.randint(a_g_min, min(a_g_max, len(remaining)))
                chosen_giv = remaining[:n_g]

            return {
                "secondary_action": add["secondary_action"],
                "details": add.get("additional_details", ""),
                "applies_to": "all-dynamic",
                "receivers": chosen_rec,
                "givers": chosen_giv,
            }

    return None


def pick_additional_for_prompt(
    pose: dict, additional_list: list[dict]
) -> Optional[dict]:
    """
    Picks an additional detail entry linked via allow_additional_details,
    without rolling counts or genders. Returns a simple dict with
    secondary_action + details, or None.
    """
    allowed_names = {
        a.strip().lower()
        for a in pose.get("allow_additional_details", "").split(",")
        if a.strip()
    }
    if not allowed_names:
        return None

    candidates = [
        a for a in additional_list
        if a["secondary_action"].strip().lower() in allowed_names
    ]
    if not candidates:
        return None

    add = random.choice(candidates)
    return {
        "secondary_action": add["secondary_action"],
        "details": add.get("additional_details", ""),
    }


def format_gender_list(chars: list[Character]) -> str:
    return ", ".join(c.gender for c in chars)


def format_character_refs(chars: list[Character]) -> str:
    return ", ".join(c.character_id for c in chars)


def _pluralize(role: str, gender_list: list[str]) -> str:
    """Return e.g. 'the receiver is mtf' or 'the receivers are mtf, ftm'."""
    joined = ", ".join(gender_list)
    if len(gender_list) == 1:
        return f"the {role} is {joined}"
    return f"the {role}s are {joined}"


def format_details_template(template: str, action: str,
                            receivers: list[Character],
                            givers: list[Character]) -> str:
    """
    Replace {receivers} and {givers} in a details template with a natural
    phrase built from the rolled characters. Capitalizes the first letter
    of the resulting sentence.
    """
    rec_phrase = _format_group([c.gender for c in receivers]) or "no one"
    giv_phrase = _format_group([c.gender for c in givers]) or "no one"

    text = (
        template
        .replace("{action}", action)
        .replace("{receivers}", rec_phrase)
        .replace("{givers}", giv_phrase)
    )
    return _capitalize_first(text)


def build_prompt(pose: dict, result: PoseResult,
                 receivers: list[Character] | None = None,
                 givers: list[Character] | None = None) -> str:
    
    # Build character count summary by gender
    count_parts = []
    if receivers is not None and givers is not None:
        all_chars = receivers + givers
        
        # Count each gender (case-insensitive, normalized)
        counts = {}
        gender_display = {"m": "m", "f": "f", "mtf": "MTF"}
        
        for c in all_chars:
            key = c.gender.strip().lower()
            counts[key] = counts.get(key, 0) + 1
        
        # Build list in consistent order: m, f, MTF
        for gender_key in ["m", "f", "mtf"]:
            if counts.get(gender_key, 0) > 0:
                display = gender_display[gender_key]
                count_parts.append(f"{counts[gender_key]} {display}")
    
    count_prefix = ""
    if count_parts:
        count_prefix = f"[{' | '.join(count_parts)}]\n"
    
    base = f"create a prompt related to {pose['action']}"

    pose_details = pose.get("details", "").strip()
    if pose_details:
        if receivers is not None and givers is not None:
            pose_details = format_details_template(
                pose_details, pose["action"], receivers, givers
            )
        base = f"{base}. {pose_details}"

    add = result.additional
    if not add:
        return count_prefix + base

    return (
        f"{count_prefix}{base} {add['secondary_action']} should be incorporated "
        f"into the scene. {add['details']}"
    )


def process_pose(pose: dict, additional_list: list[dict]) -> str:
    # Roll counts + genders purely to populate the details template.
    receivers, givers = build_characters(pose)

    additional = None
    if additional_details_enabled(pose):
        additional = pick_additional_for_prompt(pose, additional_list)

    result = PoseResult(
        action=pose["action"],
        additional=additional,
    )
    return build_prompt(pose, result, receivers, givers)


def run_sequential_set(poses_path: str, additional_path: str, swf_switch: str):
    """Iterate the entire action_poses file in order."""
    poses = load_jsonl(poses_path, swf_switch)
    additional = load_jsonl(additional_path, swf_switch)
    pose_output = []
    for pose in poses:
        pose_output.append(process_pose(pose, additional))
    return pose_output


def run_random_single(poses_path: str, additional_path: str, swf_switch: str):
    """Randomly sample from the pose list `total` times (with replacement)."""
    poses = load_jsonl(poses_path, swf_switch)
    additional = load_jsonl(additional_path, swf_switch)
    
    weights = [float(p.get("weight", 1)) for p in poses]
    pose = random.choices(poses, weights=weights, k=1)[0]
    
    process_pose(pose, additional)
    return process_pose(pose, additional)


def run_random_set(poses_path: str, additional_path: str, swf_switch: str, total: int):
    """Randomly sample from the pose list `total` times (with replacement)."""
    poses = load_jsonl(poses_path, swf_switch)
    additional = load_jsonl(additional_path, swf_switch)
    pose_output = []
    
    weights = [float(p.get("weight", 1)) for p in poses]
    
    for _ in range(total):
        pose = random.choices(poses, weights=weights, k=1)[0]
        pose_output.append(process_pose(pose, additional))
    return pose_output

if __name__ == "__main__":
    total_tests = 5
    POSES = "actions_poses.jsonl"
    ADDITIONAL = "actions_poses_additional.jsonl"
    random_poses = []
    for _ in range (total_tests):
        is_sex = random.random() < 0.5
    
        if is_sex:
            random_poses.append(run_random_single(POSES, ADDITIONAL, "nsfw"))
        else:
            random_poses.append(run_random_single(POSES, ADDITIONAL, "sfw"))


    # Mode 1: sequential
    sequential_poses = run_sequential_set(POSES, ADDITIONAL, "any")

    # Mode 2: random, 5 poses
    # random_poses = run_random_set(POSES, ADDITIONAL, "any", total=5)