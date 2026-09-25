# -*- coding: utf-8 -*-
"""
Created on Thu Sep 24 16:19:01 2026

@author: eric
"""

import json
import random
from dataclasses import dataclass, field
from typing import Optional

# if there is one giver/reciver change prompt to not be plural
# givers are changes to giver is
# clean data to remove m/f/mtf from action and details

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
    receivers: list[Character] = field(default_factory=list)
    givers: list[Character] = field(default_factory=list)
    additional: Optional[dict] = None  # {"secondary_action": str, "details": str,
                                        #  "receivers": [...], "givers": [...], "applies_to": str}


def load_jsonl(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
    
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

def format_gender_list(chars: list[Character]) -> str:
    return ", ".join(c.gender for c in chars)


def format_character_refs(chars: list[Character]) -> str:
    return ", ".join(c.character_id for c in chars)


def build_prompt(pose: dict, result: PoseResult) -> str:
    base = (
        f"create a prompt related to {pose['action']}, "
        f"the receivers are {format_gender_list(result.receivers)}, "
        f"The givers are {format_gender_list(result.givers)}"
    )

    # Normalize dangling role lists
    if not result.receivers:
        base = base.replace(
            "the receivers are , ", "there are no receivers, "
        )
    if not result.givers:
        base = base.replace(
            "The givers are ", "there are no givers. "
        ).rstrip(", ")

    # Append the pose's own details field, if present
    pose_details = pose.get("details", "").strip()
    if pose_details:
        base = f"{base}. {pose_details}"

    # Append additional details clause, if any
    add = result.additional
    if not add:
        return base

    if add["applies_to"] == "all":
        return (
            f"{base} {add['secondary_action']} should be incorporated "
            f"into the scene. {add['details']}"
        )

    rec_refs = format_character_refs(add["receivers"]) or "none"
    giv_refs = format_character_refs(add["givers"]) or "none"

    return (
        f"{base} {add['secondary_action']} should be incorporated into the "
        f"scene for character {rec_refs} as the receiver and character "
        f"{giv_refs} as the giver. {add['details']}"
    )

def process_pose(pose: dict, additional_list: list[dict]) -> str:
    receivers, givers = build_characters(pose)

    additional = None
    if additional_details_enabled(pose):
        additional = select_additional(pose, receivers, givers, additional_list)

    result = PoseResult(
        action=pose["action"],
        receivers=receivers,
        givers=givers,
        additional=additional,
    )
    return build_prompt(pose, result)


def run_sequential(poses_path: str, additional_path: str):
    """Iterate the entire action_poses file in order."""
    poses = load_jsonl(poses_path)
    additional = load_jsonl(additional_path)
    for pose in poses:
        print(process_pose(pose, additional))
        print("-" * 80)


def run_random(poses_path: str, additional_path: str, total: int):
    """Randomly sample from the pose list `total` times (with replacement)."""
    poses = load_jsonl(poses_path)
    additional = load_jsonl(additional_path)
    for _ in range(total):
        pose = random.choice(poses)
        print(process_pose(pose, additional))
        print("-" * 80)

if __name__ == "__main__":
    POSES = "actions_poses.jsonl"
    ADDITIONAL = "actions_poses_additional.jsonl"

    # Mode 1: sequential
    # run_sequential(POSES, ADDITIONAL)

    # Mode 2: random, 25 poses
    run_random(POSES, ADDITIONAL, total=5)