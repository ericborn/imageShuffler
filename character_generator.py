# -*- coding: utf-8 -*-
"""
Character Generation Pipeline
Created on Thu Sep 10 13:24:05 2026

@author: eric
"""
import re
import random
import lmstudio as lms
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

# ============================================================================
# CONFIGURATION
# ============================================================================

# This must be the *first* convenience API interaction
lms.configure_default_client("localhost:1234")

# Now this will use the explicitly configured client
with lms.Client() as client:
    model = client.llm.model()


@dataclass
class PathConfig:
    """Configuration for file paths."""
    sys_character_builder: Path
    generated_characters: Path
    character_output: Path


@dataclass
class ProcessingConfig:
    """Configuration for processing parameters."""
    split_pattern: str = r"__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_[a-fA-F0-9]+__"
    prompt_prefix: str = "generate a {gender} character in the type of "
    verbose: bool = True


# ============================================================================
# FILE I/O
# ============================================================================

def load_lines_from_file(file_path: Path) -> List[str]:
    """Load non-empty, stripped lines from a text file (one entry per line)."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def load_system_prompt(file_path: Path) -> str:
    """Load a system prompt from a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def save_lines_to_file(lines: List[str], file_path: Path) -> None:
    """Save a list of strings to a text file, one per line."""
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            # Collapse internal newlines so each entry stays on a single line
            f.write(" ".join(line.split()))
            f.write("\n")
    print(f"Saved to: {file_path.absolute()}")


# ============================================================================
# RESPONSE CLEANUP
# ============================================================================

def clean_response(response: str, split_pattern: str) -> str:
    """Extract the final response by removing chain-of-thought reasoning."""
    return re.split(split_pattern, response)[-1].strip()


# ============================================================================
# CORE PROCESSING (single prompt per context window)
# ============================================================================

def process_prompt_isolated(
    model: lms.LLM,
    system_prompt: str,
    user_prompt: str,
    split_pattern: str,
) -> str:
    """
    Process a single prompt in a fresh context window.
    Prevents cross-prompt contamination between responses.
    """
    chat = lms.Chat(system_prompt)
    chat.add_user_message(user_prompt)
    result = model.respond(chat)
    return clean_response(result.content, split_pattern)


def process_prompts_isolated(
    model: lms.LLM,
    system_prompt: str,
    prompts: List[str],
    split_pattern: str,
    verbose: bool = True,
    progress_label: str = "",
) -> List[str]:
    """
    Process every prompt in its own fresh context window.

    Returns:
        List of generated responses, one per input prompt, in order
    """
    generated: List[str] = []
    total = len(prompts)

    if verbose:
        label = f" [{progress_label}]" if progress_label else ""
        print(f"Processing {total} prompts{label} (fresh context per prompt)...")

    for i, prompt in enumerate(prompts, 1):
        try:
            cleaned = process_prompt_isolated(
                model=model,
                system_prompt=system_prompt,
                user_prompt=prompt,
                split_pattern=split_pattern,
            )
            generated.append(cleaned)
            if verbose:
                preview = cleaned[:60].replace("\n", " ")
                print(f"  [{i}/{total}] {preview}...")
        except Exception as e:
            # Preserve list alignment
            generated.append(f"[ERROR processing prompt {i}: {e}]")
            if verbose:
                print(f"  [{i}/{total}] ERROR: {e}")

    if verbose:
        print(f"Done. Processed {total} prompts.")

    return generated


# ============================================================================
# HIGH-LEVEL PIPELINE
# ============================================================================

def run_character_pipeline(
    characters_file_path: Path,
    output_file_path: Path,
    system_prompt_path: Path,
    split_pattern: str,
    prompt_prefix: str = "generate a {gender} character in the type of ",
    verbose: bool = True,
) -> List[str]:
    """
    Complete pipeline: load character genres, roll gender per prompt,
    process each in its own context, save generated characters.
    """
    if verbose:
        print(f"\nLoading character genres from: {characters_file_path}")

    genres = load_lines_from_file(characters_file_path)
    system_prompt = load_system_prompt(system_prompt_path)
    model = lms.llm()

    generated: List[str] = []
    total = len(genres)

    if verbose:
        print(f"Processing {total} prompts (fresh context per prompt, "
              f"gender rolled per prompt)...")

    for i, genre in enumerate(genres, 1):
        # Roll gender fresh for THIS prompt
        gender = roll_gender()
        user_prompt = prompt_prefix.format(gender=gender) + genre

        try:
            cleaned = process_prompt_isolated(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                split_pattern=split_pattern,
            )
            generated.append(cleaned)
            if verbose:
                preview = cleaned[:60].replace("\n", " ")
                print(f"  [{i}/{total}] ({gender}) {preview}...")
        except Exception as e:
            generated.append(f"[ERROR processing prompt {i}: {e}]")
            if verbose:
                print(f"  [{i}/{total}] ({gender}) ERROR: {e}")

    save_lines_to_file(generated, output_file_path)
    return generated

# ============================================================================
# HELPERS
# ============================================================================

def roll_gender(threshold: int = 5) -> str:
    """Roll 1-10. >threshold => 'male', else 'female'."""
    return "trans female" if random.randint(1, 10) > threshold else "cis female"

# ============================================================================
# MAIN
# ============================================================================

def main():
    paths = PathConfig(
        sys_character_builder=Path("E:/Images/txt2img-images/data/sys_prompt_character_builder.txt"),
        generated_characters=Path("E:/Images/txt2img-images/data/character_types.txt"),
        character_output=Path("E:/Images/txt2img-images/data/character_output.txt"),
    )

    config = ProcessingConfig(
        split_pattern=r"__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_[a-fA-F0-9]+__",
        prompt_prefix="generate a {gender} character in the type of ",
        verbose=True,
    )

    print("\n" + "=" * 60)
    print("PROCESSING CHARACTER GENERATION")
    print("=" * 60)

    generated_characters = run_character_pipeline(
        characters_file_path=paths.generated_characters,
        output_file_path=paths.character_output,
        system_prompt_path=paths.sys_character_builder,
        split_pattern=config.split_pattern,
        prompt_prefix=config.prompt_prefix,
        verbose=config.verbose,
    )

    print(f"\nAll done. Generated characters: {len(generated_characters)}")
    print(f"Output saved to: {paths.character_output.absolute()}")


if __name__ == "__main__":
    main()