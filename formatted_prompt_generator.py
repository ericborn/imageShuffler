# -*- coding: utf-8 -*-
"""
Created on Tue Aug 25 09:45:22 2026

@author: eric
"""

#import json
import os
import random
import requests
from dynamicprompts.generators.randomprompt import RandomPromptGenerator
from dynamicprompts.wildcards import WildcardManager
from pathlib import Path
import time

# LM Studio default endpoint (OpenAI-compatible API)
url = "http://localhost:1234/v1/chat/completions"

# Your prompts
system_prompt = """You are an expert prompt engineer for text-to-image models. Your task is to expand the user's prompt into a highly effective image-generation prompt.

Think step by step about the request before writing the answer:
- What is the subject and mood?
- What visual styles, mediums, and lighting options would fit? Consider two or three alternatives and pick the one that best serves the caption.
- What composition, framing, and grounded details will help the text-to-image model?

Then output a single expanded prompt paragraph.

Follow these rules strictly:
1. **Faithfulness First:** Preserve all original subjects, actions, colors, and spatial relationships. Do not add new objects, props, characters, or animals unless the user clearly implies them.
2. **Practical T2I Structure:** Write a prompt that a text-to-image model can parse cleanly. Group subjects with their own attributes and actions. Use grounded phrasing for poses, interactions, and spatial layout.
3. **Style Planning Stays Internal:** Use your internal reasoning to choose style, medium, framing, and lighting. Do not emit planning tags or wrappers in the visible answer body.
4. **Text Rendering:** If the user requests visible text, quotes, labels, or typography, specify the exact text clearly and wrap requested words in quotes.
5. **Avoid Over-Specification:** Do not invent highly specific clothing, colors, materials, or scene details unless the input supports them.
6. **Structure:** Write one cohesive paragraph after the thinking block. No bullets, JSON, or markdown.
7. **Respect Existing Detail:** If the user's prompt is already detailed, lightly polish and finalize rather than heavily expanding — preserve their phrasing and direction.
8. **Respect the Human Form:** Treat depictions of people with dignity. Assume clothing covers genitals and intimate anatomy.
9. **Preserve User Medium:** When the user explicitly requests a medium (e.g. "photo of", "photograph of", "illustration of", "painting of", "sketch of", "3D render of"), honor it. Do not pivot to a different medium to avoid difficulty — match the user's stated intent.
"""

# 1. Set up dynamicprompts
wildcards_dir = Path("C:/stable-diffusion-webui-forge/extensions/sd-dynamic-prompts/wildcards/advPrompt")
raw_file = Path("E:/Images/txt2img-images/data/unformatted_prompts.txt")
formatted_file = Path("E:/Images/txt2img-images/data/formatted_prompts.txt")

wm = WildcardManager(wildcards_dir)
generator = RandomPromptGenerator(wm)
base_prompts = []
formatted_prompt = []

for i in range(100):
    ass_selection = ""
    breast_selection = ""
    breast_roll = random.randint(0, 2)
    if (breast_roll == 0):
        ass_prompt = wm.get_all_values("__03c-ass__")
        ass_selection = random.sample(ass_prompt, min(1, len(ass_prompt)))[0]
    if (breast_roll == 1):
        breast_prompt = wm.get_all_values("__03b-breast__")
        breast_selection = random.sample(breast_prompt, min(1, len(breast_prompt)))[0]
    else:
        ass_prompt = wm.get_all_values("__03c-ass__")
        ass_selection = random.sample(ass_prompt, min(1, len(ass_prompt)))[0]
        breast_prompt = wm.get_all_values("__03b-breast__")
        breast_selection = random.sample(breast_prompt, min(1, len(breast_prompt)))[0]

    pre_text = "Now expand the following prompt: "
    base_template = '__03a-base__'
    bna_template = f' {breast_selection}, {ass_selection}'
    full_template = pre_text + base_template + bna_template + """. The woman is the primary subject. She has __03g-hair__.
    wearing __03m-makeup__. Wearing __03o-clothing_category__ {0-3$$and __03t-accessories__}. 
    {__04a-pose__|__04b-action__} 
    {__05a-environment__ choose a style of lighting to fit the 
    environment and describe how its brightness and color affects the 
    environments materials with reflections or shadows|__05d-environment_light_combo__}. 
    Select an shot size, camera height and viewing angle that fits with the subject and environment. 
    Use an appropriate focus and depth of field."""

    # 3. Generate base prompts (e.g., 20 for batch)
    base_prompts.append((generator.generate(full_template, num_images=1))[0])

# Function to estimate token count (rough approximation)
def estimate_tokens(text):
    """Rough estimate: ~4 characters per token for English text"""
    return len(text) // 4

# Function to get the actual context window size from LM Studio
def get_context_window():
    try:
        # Try to get model info
        models_url = "http://localhost:1234/api/v0/models"
        response = requests.get(models_url)
        if response.status_code == 200:
            models = response.json()
            if models and len(models) > 0:
                # Get the first loaded model's context length
                model_info = models[0]
                return model_info.get("context_length", 12000)  # Default fallback
    except:
        pass
    return 12000  # Default fallback if can't retrieve

# Get context window size
CONTEXT_WINDOW = get_context_window()
print(f"Context window size: {CONTEXT_WINDOW} tokens")

# Buffer for system prompt and overhead
SYSTEM_PROMPT_TOKENS = estimate_tokens(system_prompt)
OVERHEAD_BUFFER = 500  # Buffer for message formatting overhead
MAX_RESPONSE_TOKENS = 11000
SAFETY_MARGIN = 1000  # Safety margin to prevent hitting the limit

# Function to send a single prompt to the LLM
def send_prompt(messages, prompt_index, conversation_index):
    """Send messages and return the response"""
    payload = {
        "model": "local-model",
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": MAX_RESPONSE_TOKENS,
        "stream": False
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        if response.status_code == 200:
            result = response.json()
            assistant_message = result["choices"][0]["message"]["content"]
            
            # Print token usage if available
            if "usage" in result:
                print(f"  Prompt tokens: {result['usage'].get('prompt_tokens', 0)}")
                print(f"  Completion tokens: {result['usage'].get('completion_tokens', 0)}")
                print(f"  Total tokens: {result['usage'].get('total_tokens', 0)}")
            
            return assistant_message
        else:
            print(f"Error (prompt {prompt_index}): {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"Exception (prompt {prompt_index}): {e}")
        return None

# Function to estimate tokens in a conversation
def estimate_conversation_tokens(messages):
    """Estimate total tokens in a message list"""
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        total += 50  # Overhead for role and formatting
    return total

# Main processing loop
print("\nProcessing prompts in a single continuous conversation...")
conversation_messages = [{"role": "system", "content": system_prompt}]
current_tokens = SYSTEM_PROMPT_TOKENS
current_conversation = 0

# Open file for writing results incrementally
output_file = formatted_file
with open(output_file, 'w', encoding='utf-8') as f:
    for idx, prompt in enumerate(base_prompts):
        prompt_tokens = estimate_tokens(prompt)
        new_message = {"role": "user", "content": prompt}
        
        # Calculate estimated total if we add this prompt
        estimated_total = current_tokens + prompt_tokens + MAX_RESPONSE_TOKENS + OVERHEAD_BUFFER
        
        # Check if we need to trim or reset the conversation
        if estimated_total > (CONTEXT_WINDOW - SAFETY_MARGIN):
            # We're approaching the limit - trim the conversation by keeping only recent messages
            print(f"\n⚠️ Approaching token limit ({current_tokens}/{CONTEXT_WINDOW})")
            print(f"Trimming conversation history to keep most recent exchanges...")
            
            # Keep system prompt + last 5 messages (2-3 exchanges) + overhead
            # This maintains conversation context while staying under the limit
            KEEP_RECENT = 6  # Keep system + last 5 messages
            
            if len(conversation_messages) > KEEP_RECENT:
                # Preserve system message and last N messages
                conversation_messages = [conversation_messages[0]] + conversation_messages[-KEEP_RECENT+1:]
                current_tokens = SYSTEM_PROMPT_TOKENS + sum([estimate_tokens(msg.get("content", "")) + 50 
                                                             for msg in conversation_messages[1:]])
                print(f"Trimmed to {len(conversation_messages)} messages, {current_tokens} tokens")
                current_conversation += 1
            else:
                # If we can't trim enough, reset completely
                conversation_messages = [{"role": "system", "content": system_prompt}]
                current_tokens = SYSTEM_PROMPT_TOKENS
                current_conversation += 1
                print(f"Reset conversation completely due to token limit")
                time.sleep(0.5)  # Small delay
        
        # Add the prompt to conversation
        conversation_messages.append(new_message)
        current_tokens += prompt_tokens + 50  # Add overhead
        
        print(f"\n[Prompt {idx + 1}/{len(base_prompts)}]")
        print(f"Current tokens: {current_tokens}/{CONTEXT_WINDOW} (will add ~{MAX_RESPONSE_TOKENS} for response)")
        
        # Send the request with current conversation history
        response = send_prompt(conversation_messages, idx + 1, current_conversation + 1)
        
        if response:
            # Add the assistant's response to conversation history
            assistant_message = {"role": "assistant", "content": response}
            conversation_messages.append(assistant_message)
            response_tokens = estimate_tokens(response) + 50
            current_tokens += response_tokens
            
            # Save to formatted_prompt list
            formatted_prompt.append(response)
            
            # Write directly to file
            f.write(response)
            f.write("\n")
            f.flush()  # Force write to disk
            
            print(f"✓ Response saved (conversation now has {len(conversation_messages)} messages)")
        else:
            print(f"✗ Failed to get response for prompt {idx + 1}")
        
        time.sleep(0.3)  # Small delay between requests

# Final summary
print(f"\n{'='*50}")
print(f"Processing complete!")
print(f"  Total base prompts generated: {len(base_prompts)}")
print(f"  Total conversation resets/trims: {current_conversation}")
print(f"  Total formatted prompts received: {len(formatted_prompt)}")
print(f"  Results saved to: {output_file.absolute()}")
print(f"{'='*50}")

# Save a backup with all results in one go
full_formatted_file = formatted_file
with open(full_formatted_file, 'w', encoding='utf-8') as f:
    for i, prompt in enumerate(formatted_prompt, 1):
        f.write(prompt)
        f.write("\n")
print(f"Backup saved to: {full_formatted_file.absolute()}")

# Save a backup with all results in one go
full_raw_file = raw_file
with open(full_raw_file, 'w', encoding='utf-8') as f:
    for i, prompt in enumerate(base_prompts, 1):
        f.write(prompt)
        f.write("\n")
print(f"Backup saved to: {full_raw_file.absolute()}")