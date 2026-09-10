# -*- coding: utf-8 -*-
"""
Created on Thu Sep 10 13:24:05 2026

@author: eric
"""
import re
import lmstudio as lms
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class PathConfig:
    """Configuration for file paths."""
    sys_sentence_refiner: Path
    sys_sentence_builder: Path
    wildcards_sentence_dir: Path
    wildcards_keyword_dir: Path
    sentence_file_raw: Path
    sentence_file_revised: Path
    keyword_file_raw: Path
    keyword_file_revised: Path

@dataclass
class ProcessingConfig:
    """Configuration for processing parameters."""
    split_pattern: str = r"__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_[a-fA-F0-9]+__"
    delimiter: str = "Medium: "
    verbose: bool = True

# ============================================================================
# TOKEN UTILITIES (kept for reference / optional use)
# ============================================================================

def estimate_tokens(model: lms.LLM, text: str) -> int:
    """Estimate token count for a given text using the model's tokenizer."""
    return len(model.tokenize(text))

def get_context_window(model: Optional[lms.LLM] = None, default: int = 8000) -> int:
    """Get the actual context window size from LM Studio."""
    try:
        lm_model = model if model else lms.llm()
        if lm_model:
            return lm_model.get_context_length()
    except Exception:
        pass
    return default

# ============================================================================
# PROMPT PARSING AND CLEANUP
# ============================================================================

def parse_prompts_from_string(prompt_string: str, delimiter: str = "Medium: ") -> List[str]:
    """
    Parse prompts from a single string, splitting on a delimiter.

    Args:
        prompt_string: The raw string containing all prompts
        delimiter: The delimiter that marks the start of each prompt

    Returns:
        List of individual prompt strings
    """
    parts = re.split(f"({delimiter})", prompt_string)
    prompts = []
    start_idx = 1 if parts[0].strip() == "" else 0

    for i in range(start_idx, len(parts), 2):
        if i + 1 < len(parts):
            prompts.append(parts[i] + parts[i + 1])
        else:
            prompts.append(parts[i])

    # Remove leading spaces before each category
    prompts = [re.sub(r"\n +", "\n", block) for block in prompts]
    return prompts


def load_prompts_from_file(file_path: Path, delimiter: str = "Medium: ") -> List[str]:
    """Load and parse prompts from a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return parse_prompts_from_string(content, delimiter)


def load_system_prompt(file_path: Path) -> str:
    """Load a system prompt from a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def clean_response(response: str, split_pattern: str) -> str:
    """Extract the final response by removing chain-of-thought reasoning."""
    return re.split(split_pattern, response)[-1].strip()

# ============================================================================
# FILE I/O
# ============================================================================

def save_prompts_to_file(prompts: List[str], file_path: Path) -> None:
    """Save a list of prompts to a text file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        for prompt in prompts:
            f.write(prompt)
            f.write("\n")
    print(f"Saved to: {file_path.absolute()}")

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

    Args:
        model: The LLM model (reused across all calls)
        system_prompt: System prompt applied to every fresh context
        prompts: List of user prompts to process
        split_pattern: Regex pattern to strip reasoning from responses
        verbose: Whether to print progress
        progress_label: Optional label shown in progress output

    Returns:
        List of revised responses, one per input prompt, in order
    """
    revised_prompts: List[str] = []
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
            revised_prompts.append(cleaned)
            if verbose:
                preview = cleaned[:60].replace("\n", " ")
                print(f"  [{i}/{total}] {preview}...")
        except Exception as e:
            # Preserve list alignment — store an error marker so downstream
            # indices still map to the original prompt list.
            revised_prompts.append(f"[ERROR processing prompt {i}: {e}]")
            if verbose:
                print(f"  [{i}/{total}] ERROR: {e}")

    if verbose:
        print(f"Done. Processed {total} prompts.")

    return revised_prompts

# ============================================================================
# HIGH-LEVEL PIPELINE
# ============================================================================

def run_processing_pipeline(
    raw_file_path: Path,
    output_file_path: Path,
    system_prompt_path: Path,
    split_pattern: str,
    delimiter: str = "Medium: ",
    verbose: bool = True,
    progress_label: str = "",
) -> List[str]:
    """
    Complete pipeline: load prompts, process each in its own context, save results.

    Returns:
        List of revised prompts
    """
    if verbose:
        print(f"\nLoading prompts from: {raw_file_path}")

    prompts = load_prompts_from_file(raw_file_path, delimiter)
    system_prompt = load_system_prompt(system_prompt_path)

    model = lms.llm()

    revised = process_prompts_isolated(
        model=model,
        system_prompt=system_prompt,
        prompts=prompts,
        split_pattern=split_pattern,
        verbose=verbose,
        progress_label=progress_label,
    )

    save_prompts_to_file(revised, output_file_path)
    return revised

# ============================================================================
# MAIN
# ============================================================================

paths = PathConfig(
    sys_sentence_refiner=Path("E:/Images/txt2img-images/data/sys_prompt_sentence_refiner.txt"),
    sys_sentence_builder=Path("E:/Images/txt2img-images/data/sys_prompt_sentence_builder.txt"),
    wildcards_sentence_dir=Path("C:/stable-diffusion-webui-forge/extensions/sd-dynamic-prompts/wildcards/advPrompt"),
    wildcards_keyword_dir=Path("C:/stable-diffusion-webui-forge/extensions/sd-dynamic-prompts/wildcards/keyword"),
    sentence_file_raw=Path("E:/Images/txt2img-images/data/sentence_prompts_raw.txt"),
    sentence_file_revised=Path("E:/Images/txt2img-images/data/sentence_prompts_revised.txt"),
    keyword_file_raw=Path("E:/Images/txt2img-images/data/keyword_prompts_raw.txt"),
    keyword_file_revised=Path("E:/Images/txt2img-images/data/keywordprompts_revised.txt"),
)

config = ProcessingConfig(
    split_pattern=r"__LM_STUDIO_INTERNAL_LSEP_SYNTHETIC_REASONING_END_[a-fA-F0-9]+__",
    delimiter="Medium: ",
    verbose=True,
)

# --- Process keyword prompts ---
print("\n" + "=" * 60)
print("PROCESSING KEYWORD PROMPTS")
print("=" * 60)
keyword_revised = run_processing_pipeline(
    raw_file_path=paths.keyword_file_raw,
    output_file_path=paths.keyword_file_revised,
    system_prompt_path=paths.sys_sentence_refiner,
    split_pattern=config.split_pattern,
    delimiter=config.delimiter,
    verbose=config.verbose,
    progress_label="keyword",
)

# --- Process sentence prompts ---
print("\n" + "=" * 60)
print("PROCESSING SENTENCE PROMPTS")
print("=" * 60)
sentence_revised = run_processing_pipeline(
    raw_file_path=paths.sentence_file_raw,
    output_file_path=paths.sentence_file_revised,
    system_prompt_path=paths.sys_sentence_refiner,
    split_pattern=config.split_pattern,
    delimiter=config.delimiter,
    verbose=config.verbose,
    progress_label="sentence",
)

print(f"\nAll done. Keyword prompts: {len(keyword_revised)}, "
      f"Sentence prompts: {len(sentence_revised)}")
