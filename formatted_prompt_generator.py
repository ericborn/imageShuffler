# -*- coding: utf-8 -*-
"""
Created on Tue Aug 25 09:45:22 2026

@author: eric
"""

#import json
#import os
import re
import random
import requests
import lmstudio as lms
from dynamicprompts.generators.randomprompt import RandomPromptGenerator
from dynamicprompts.wildcards import WildcardManager
from pathlib import Path
import time

# LM Studio default endpoint (OpenAI-compatible API)
url = "http://localhost:1234/v1/chat/completions"

# paths
# used to expand/refine both keyword and sentence based prompts
path_sys_prompt_refiner = Path("E:/Images/txt2img-images/data/sys_prompt_prompt_refiner.txt")

# used to generate a sentence from a single keyword
path_sys_sentence_builder = Path("E:/Images/txt2img-images/data/sys_prompt_sentence_builder.txt")

path_wildcards_sentence_dir = Path("C:/stable-diffusion-webui-forge/extensions/sd-dynamic-prompts/wildcards/advPrompt")
path_wildcards_keyword_dir = Path("C:/stable-diffusion-webui-forge/extensions/sd-dynamic-prompts/wildcards/keyword")

path_sentence_file_raw = Path("E:/Images/txt2img-images/data/sentence_prompts_raw.txt")
path_sentence_file_revised = Path("E:/Images/txt2img-images/data/sentence_prompts_revised.txt")

path_keyword_file_raw = Path("E:/Images/txt2img-images/data/keyword_prompts_raw.txt")
path_keyword_file_revised = Path("E:/Images/txt2img-images/data/keywordprompts_revised.txt")

# System prompts
with open(path_sys_prompt_refiner, 'r') as f:
    system_prompt_prompt_refiner = f.read()
    
with open(path_sys_sentence_builder, 'r') as f:
    system_prompt_sentence_builder = f.read()

#########
# only run to load prompts from file
#########
# load prompts from file if already generated
with open(path_sentence_file_raw, 'r') as f:
    sentence_prompts_string = f.read()
    
with open(path_keyword_file_raw, 'r') as f:
    keyword_prompts_string = f.read()

# sentence prompts cleanup
# split single string on starting category for Medium:
sentence_prompts_parts = re.split("(Medium: )", sentence_prompts_string)

sentence_prompts_raw = []
start_idx = 1 if sentence_prompts_parts[0].strip() == "" else 0

for i in range(start_idx, len(sentence_prompts_parts), 2):
    # Check if there is a matching text block after the delimiter
    if i + 1 < len(sentence_prompts_parts):
        sentence_prompts_raw.append(sentence_prompts_parts[i] + sentence_prompts_parts[i + 1])
    else:
        sentence_prompts_raw.append(sentence_prompts_parts[i])

# remove leading spaces before each category
sentence_prompts_raw = [re.sub(r"\n +", "\n", block) for block in sentence_prompts_raw]

####
# keyword prompts cleanup
# split single string on starting category for Medium:
keyword_prompts_parts = re.split("(Medium: )", keyword_prompts_string)

keyword_prompts_raw = []
start_idx = 1 if keyword_prompts_parts[0].strip() == "" else 0

for i in range(start_idx, len(keyword_prompts_parts), 2):
    # Check if there is a matching text block after the delimiter
    if i + 1 < len(keyword_prompts_parts):
        keyword_prompts_raw.append(keyword_prompts_parts[i] + keyword_prompts_parts[i + 1])
    else:
        keyword_prompts_raw.append(keyword_prompts_parts[i])

# remove leading spaces before each category
keyword_prompts_raw = [re.sub(r"\n +", "\n", block) for block in keyword_prompts_raw]

#########
# only run to generate new prompts
#########
# 1. Set up and build raw sentence wildcards
wm_sentence = WildcardManager(path_wildcards_sentence_dir)
generator_s = RandomPromptGenerator(wm_sentence)
sentence_prompts_raw = []
sentence_prompts_revised = []

for i in range(100):
    frame_roll = random.randint(1,100)
    if (frame_roll > 90):
        full_sentence_template = """Medium: __01-medium__
        Subject: One woman is the primary subject. 
        Pose/Action: __04d-interaction__
        Appearance/Clothing: __03a-base__ woman She has __03g-hair__. __03m-makeup__. 
        Wearing __03o-clothing_category__ {0-3$$and __03t-accessories__}.
        Camera/Composition: __07a-camera_shot_size__, __07b-camera_height__, 
        {0-1$$__07c-camera_frame_placement__} {0-1$$__07d-camera_focus__}
        Environment/Lighting: __05d-environment_light_combo__"""
    elif (frame_roll >= 50 and frame_roll <= 90):
        full_sentence_template = """Medium: __01-medium__
        Subject: One woman is the primary subject. 
        Pose/Action: __04d-interaction__
        Appearance/Clothing: __03a-base__ woman She has __03g-hair__. __03m-makeup__. 
        Wearing __03o-clothing_category__ {0-3$$and __03t-accessories__}.
        Camera/Composition: __07a-camera_shot_size__, __07b-camera_height__, {0-1$$__07d-camera_focus__}
        Environment/Lighting: __05d-environment_light_combo__"""
    else:
        full_sentence_template = """Medium: __01-medium__
        Subject: One woman is the primary subject. 
        Pose/Action: __04d-interaction__
        Appearance/Clothing: __03a-base__ woman She has __03g-hair__. __03m-makeup__. 
        Wearing __03o-clothing_category__ {0-3$$and __03t-accessories__}.
        Camera/Composition: __07a-camera_shot_size__, __07b-camera_height__
        Environment/Lighting: __05d-environment_light_combo__"""
    # 3. Generate base prompts
    sentence_prompts_raw.append((generator_s.generate(full_sentence_template, num_images=1))[0])    

# test specific wildcard list    
#print(generator_s.generate("""{0-1$$__07c-camera_frame_placement__} {0-1$$__07d-camera_focus__}""", num_images=1))

# 2.B Save a backup with all results in one go
full_sentence_file = path_sentence_file_raw
with open(full_sentence_file, 'w', encoding='utf-8') as f:
    for i, prompt in enumerate(sentence_prompts_raw, 1):
        f.write(prompt)
        f.write("\n")
print(f"Backup saved to: {full_sentence_file.absolute()}")

##############
# 2. Set up and build raw keyword wildcards
wm_keyword = WildcardManager(path_wildcards_keyword_dir)
generator_k = RandomPromptGenerator(wm_keyword)
keyword_prompts_raw = []
keyword_prompts_revised = []

for i in range(100):
    frame_roll = random.randint(1,100)
    #print(frame_roll)
    if (frame_roll > 90):
        # style of photo
        full_keyword_template = """Medium: __01-medium__ 
        Subject: One __descriptors__ woman is the primary subject.
        Pose/Action: __04d-interaction__
        Appearance/Clothing: __base__, {__ethnicity__|__skin_tone__}, {0-1$$__tats__}.
        She has {0-1$$__makeup__} __hair_texture__ __hair_style__ __hair_color_saturation__ 
        __hair_color__ hair, __eye_color__.
        wearing {__clothing_category__} {0-3$$ and $$__accessories__}.
        Camera/Composition: __07-camera_shot_size__, __07-camera_height__, {0-1$$__07-camera_frame_placement__} {0-1$$__07-camera_focus__}
        Environment: __05a-environment__ 
        Lighting: __lighting__"""
    elif (frame_roll >= 50 and frame_roll <= 90):
        full_keyword_template = """Medium: __01-medium__ 
        Subject: __descriptors__ woman is the primary subject.
        Pose/Action: __04d-interaction__
        Appearance/Clothing: __base__, {__ethnicity__|__skin_tone__}, {0-1$$__tats__}.
        She has {0-1$$__makeup__} __hair_texture__ __hair_style__ __hair_color_saturation__ 
        __hair_color__ hair, __eye_color__.
        wearing {__clothing_category__} {0-3$$ and $$__accessories__}.
        Camera/Composition: __07-camera_shot_size__, __07-camera_height__, __07-camera_focus__ 
        Environment: __05a-environment__ 
        Lighting: __lighting__"""
    else:
        full_keyword_template = """Medium: __01-medium__ 
        Subject: __descriptors__ woman is the primary subject.
        Pose/Action: __04d-interaction__
        Appearance/Clothing: __base__, {__ethnicity__|__skin_tone__}, {0-1$$__tats__}.
        She has {0-1$$__makeup__} __hair_texture__ __hair_style__ __hair_color_saturation__ 
        __hair_color__ hair, __eye_color__.
        wearing {__clothing_category__} {0-3$$ and $$__accessories__}.
        Camera/Composition: __07-camera_shot_size__, __07-camera_height__,
        Environment: __05a-environment__ 
        Lighting: __lighting__"""
        
    # 3. Generate base prompts
    keyword_prompts_raw.append((generator_k.generate(full_keyword_template, num_images=1))[0])

# test specific wildcard list
#print(generator_k.generate("__hair_texture__", num_images=1))

# Save a backup with all results in one go
full_keyword_file = path_keyword_file_raw
with open(full_keyword_file, 'w', encoding='utf-8') as f:
    for i, prompt in enumerate(keyword_prompts_raw, 1):
        f.write(prompt)
        f.write("\n")
print(f"Backup saved to: {full_keyword_file.absolute()}")

# old version with creative control given to llm
# for i in range(100):
#     ass_selection = ""
#     breast_selection = ""
#     breast_roll = random.randint(0, 2)
#     if (breast_roll == 0):
#         ass_prompt = wm.get_all_values("__03c-ass__")
#         ass_selection = random.sample(ass_prompt, min(1, len(ass_prompt)))[0]
#     if (breast_roll == 1):
#         breast_prompt = wm.get_all_values("__03b-breast__")
#         breast_selection = random.sample(breast_prompt, min(1, len(breast_prompt)))[0]
#     else:
#         ass_prompt = wm.get_all_values("__03c-ass__")
#         ass_selection = random.sample(ass_prompt, min(1, len(ass_prompt)))[0]
#         breast_prompt = wm.get_all_values("__03b-breast__")
#         breast_selection = random.sample(breast_prompt, min(1, len(breast_prompt)))[0]

#     #TODO
#     # text needs to be expanded to additional detail by leading the model
#     # lifting a barbell loaded with heavy weight
#     # lifting a barbell loaded with heavy weight, the bar sags from the load.
#     # she possesses huge breasts and a large ass
#     # Her breasts possess immense physical mass, but are firm, perky and exposed. She possesses an exaggerated large ass which is disproportionatly large for her slim physique
#     # create facial expressions dynamic prompt list
#     # maybe try having the llm create expanded prompt strings for each dynamic
#     # file itself instead of doing the whole prompt one shot
    
#     # style of photo
#     pre_text = "Now expand the following prompt: "
#     base_template = '__03a-base__'
#     bna_template = f' {breast_selection}, {ass_selection}'
#     full_template = pre_text + base_template + bna_template + """. The woman is the primary subject. She has __03g-hair__.
#     wearing __03m-makeup__. Wearing __03o-clothing_category__ {0-3$$and __03t-accessories__}. 
#     {__04a-pose__|__04b-action__} 
#     {__05a-environment__ choose a style of lighting to fit the 
#     environment and describe how its brightness and color affects the 
#     environments materials with reflections or shadows|__05d-environment_light_combo__}. 
#     Select an shot size, camera height and viewing angle that fits with the subject and environment. 
#     Use an appropriate focus and depth of field."""

#     # 3. Generate base prompts (e.g., 20 for batch)
#     base_prompts.append((generator.generate(full_template, num_images=1))[0])

# Function to estimate token count (rough approximation)
def estimate_tokens(text):
    """Rough estimate: ~4 characters per token for English text"""
    return len(text) // 4

# Function to get the actual context window size from LM Studio
def get_context_window():
    try:
        # Try to get model info
        lm_model = lms.llm()
        if lm_model:
            return lm_model.get_context_length()
    except:
        pass
    return 8000  # Default fallback if can't retrieve

def does_chat_fit_in_context(model: lms.LLM, chat: lms.Chat) -> bool:
    # Convert the conversation to a string using the prompt template.
    formatted = model.apply_prompt_template(chat)
    # Count the number of tokens in the string.
    token_count = len(model.tokenize(formatted))
    # Get the current loaded context length of the model
    context_length = model.get_context_length()
    return token_count < context_length

model = lms.llm()
chat = lms.Chat.from_history({
    "messages": [
        { "role": "user", "content": "What is the meaning of life." },
        { "role": "assistant", "content": "The meaning of life is..." },
        # ... More messages
    ]
})
print("Fits in context:", does_chat_fit_in_context(model, chat))

# Get context window size
CONTEXT_WINDOW = get_context_window()
print(f"Context window size: {CONTEXT_WINDOW} tokens")

# Buffer for system prompt and overhead
SYSTEM_PROMPT_TOKENS = estimate_tokens(path_sys_prompt_refiner)
OVERHEAD_BUFFER = 250  # Buffer for message formatting overhead
MAX_RESPONSE_TOKENS = 8000
SAFETY_MARGIN = 100  # Safety margin to prevent hitting the limit

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
output_file = sentence_file_revised
with open(output_file, 'w', encoding='utf-8') as f:
    for idx, prompt in enumerate(sentence_prompts_raw):
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
        
        print(f"\n[Prompt {idx + 1}/{len(sentence_prompts_revised)}]")
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
            sentence_file_revised.append(response)
            
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
print(f"  Total revised prompts generated: {len(sentence_prompts_revised)}")
print(f"  Total conversation resets/trims: {current_conversation}")
print(f"  Total formatted prompts received: {len(sentence_file_revised)}")
print(f"  Results saved to: {output_file.absolute()}")
print(f"{'='*50}")

# Save a backup with all results in one go
full_formatted_file = sentence_file_revised
with open(full_formatted_file, 'w', encoding='utf-8') as f:
    for i, prompt in enumerate(sentence_prompts_revised, 1):
        f.write(prompt)
        f.write("\n")
print(f"Backup saved to: {full_formatted_file.absolute()}")

# Save a backup with all results in one go
full_keyword_file = raw_file
with open(full_keyword_file, 'w', encoding='utf-8') as f:
    for i, prompt in enumerate(keyword_prompts_revised, 1):
        f.write(prompt)
        f.write("\n")
print(f"Backup saved to: {full_keyword_file.absolute()}")