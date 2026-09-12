import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from image_utils import normalize_path, extract_prompt_info, get_images_path

# Import your existing ParserManager
from sd_parsers import ParserManager

DB_NAME = 'image_evaluations.db'
DB_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), DB_NAME)

def init_db():
    """Initialize the database connection and create tables if they don't exist."""
    """Create the database schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table 1: image_details
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS image_details (
            image_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            positive_prompt TEXT,
            negative_prompt TEXT,
            loras TEXT,  -- comma-separated string
            seed TEXT,
            model TEXT,  -- Checkpoint/model name
            steps TEXT,
            scheduler TEXT,  -- Sampler name
            cfg TEXT,  -- CFG scale
            generation_strategy TEXT,  -- 'Keyword' or 'Sentence'
            
            -- Review fields (filled during evaluation)
            verdict TEXT,  -- 'Keeper', 'Fixer', or 'Dud'
            reviewed_at TIMESTAMP,
            times_displayed INTEGER DEFAULT 0,
            fix_category TEXT,  -- 'Anatomy', 'Background', 'Clothing', 'Lighting', 'Composition', 'Other'
            fix_reason TEXT,  -- Free text description of what needs fixing
            
            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table 2: layer_evaluations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS layer_evaluations (
            evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            layer_number INTEGER NOT NULL,  -- 1-8 matching your hierarchy
            layer_category TEXT NOT NULL,  -- 'MEDIUM', 'SUBJECT', 'POSE', 'APPEARANCE', 
                                            -- 'CAMERA', 'ENVIRONMENT', 'LIGHTING', 'COLOR', 
                                            -- 'MATERIALS', 'STYLE' (you can have 8-10 layers)
            layer_text TEXT,  -- The actual text snippet after the colon
            
            -- Review fields (filled during evaluation)
            execution_status TEXT,  -- 'Visible', 'Bleed', or 'Omitted'
            conflict_type TEXT,  -- 'Subject_vs_Env', 'Action_vs_Clothing', 'Lighting_vs_Color', 'Style_vs_Medium', or NULL
            is_dominant BOOLEAN DEFAULT 0,  -- Whether this was the longest clause
            
            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (image_id) REFERENCES image_details(image_id) ON DELETE CASCADE,
            UNIQUE(image_id, layer_number)  -- One evaluation per layer per image
        )
    """)
            
    conn.commit()
    conn.close()
    print("✓ Database tables created successfully")

def insert_image(image_data: Dict) -> int:
    """
    Insert a new image record.
    
    Args:
        image_data: Dictionary containing image metadata and review fields
    
    Returns:
        image_id: The auto-incremented ID of the new record
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Handle timestamps
    reviewed_at = image_data.get('reviewed_at')
    if reviewed_at is None and image_data.get('verdict'):
        reviewed_at = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT INTO image_details (
            file_name, file_path, positive_prompt, negative_prompt, loras,
            seed, model, steps, scheduler, cfg, generation_strategy,
            verdict, reviewed_at, times_displayed, fix_category, fix_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        image_data.get('file_name'),
        image_data.get('file_path'),
        image_data.get('positive_prompt'),
        image_data.get('negative_prompt'),
        image_data.get('loras'),
        image_data.get('seed'),
        image_data.get('model'),
        image_data.get('steps'),
        image_data.get('scheduler'),
        image_data.get('cfg'),
        image_data.get('generation_strategy'),
        image_data.get('verdict'),
        reviewed_at,
        image_data.get('times_displayed', 0),
        image_data.get('fix_category'),
        image_data.get('fix_reason')
    ))
    
    conn.commit()
    conn.close()
    return cursor.lastrowid

def insert_layer_evaluation(layer_data: Dict):
    """
    Insert or update a layer evaluation for an image.
    
    Args:
        layer_data: Dictionary containing layer evaluation data
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO layer_evaluations (
            image_id, layer_number, layer_category, layer_text,
            execution_status, conflict_type, is_dominant
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(image_id, layer_number) DO UPDATE SET
            layer_text = excluded.layer_text,
            execution_status = excluded.execution_status,
            conflict_type = excluded.conflict_type,
            is_dominant = excluded.is_dominant,
            updated_at = CURRENT_TIMESTAMP
    """, (
        layer_data.get('image_id'),
        layer_data.get('layer_number'),
        layer_data.get('layer_category'),
        layer_data.get('layer_text'),
        layer_data.get('execution_status'),
        layer_data.get('conflict_type'),
        layer_data.get('is_dominant', 0)
    ))
    
    conn.commit()
    conn.close()

def parse_prompt_layers(prompt_text: str) -> List[Dict]:
    """
    Parse a colon-delimited prompt into layer components.
    
    Expected format: "CATEGORY: text description. CATEGORY2: another description."
    
    Args:
        prompt_text: The full prompt string
    
    Returns:
        List of dictionaries with 'category' and 'text' keys
    """
    layers = []
    
    if not prompt_text or prompt_text in ['NO_METADATA', 'ERROR']:
        return [{
            'layer_number': 1,
            'layer_category': 'PARSE_ERROR',
            'layer_text': 'Unable to parse prompt layers'
        }]
    
    import re
    
    # Known category labels
    CATEGORIES = [
        'Medium', 'Subject', 'Pose/Action', 'Pose', 'Action', 'Appearance',
        'Clothing', 'Appearance/Clothing', 'Camera/Composition', 'Composition',
        'Camera', 'Environment', 'Spatial layers', 'Environment/Spatial layers',
        'Lighting', 'Color', 'Materials'
    ]
    
    # Build a pattern that matches only these labels followed by a colon.
    # Sort by length (desc) so "POSE/ACTION" is tried before "POSE".
    # \b word boundary on each side prevents matching inside other words.
    label_alternation = '|'.join(
        re.escape(c) for c in sorted(CATEGORIES, key=len, reverse=True)
    )
    pattern = re.compile(
        rf'(?P<category>\b(?:{label_alternation})\b)\s*:\s*',
        re.IGNORECASE
    )
    
    matches = list(pattern.finditer(prompt_text))
    
    if matches:
        for idx, match in enumerate(matches, 1):
            start = match.end()
            end = matches[idx].start() if idx < len(matches) else len(prompt_text)
            text = prompt_text[start:end].strip()
            # Collapse internal newlines/multiple spaces into single spaces
            text = re.sub(r'\s+', ' ', text).strip()
            
            if text:
                layers.append({
                    'layer_number': len(layers) + 1,
                    'layer_category': match.group('category').upper(),
                    'layer_text': text
                })
    
    if not layers:
        # No categories found - return fallback
        layers.append({
            'layer_number': 1,
            'layer_category': 'UNPARSED',
            'layer_text': prompt_text
        })
    
    return layers

def extract_data_from_workflow(json_data, data_type):
    """Extract lora_name: strength_model pairs from a ComfyUI workflow JSON.
    
    Accepts a JSON string, dict, or file path.
    """
    import json

    # Handle string, dict, or file path input
    if isinstance(json_data, dict):
        data = json_data
    elif isinstance(json_data, str) and json_data.strip().startswith("{"):
        data = json.loads(json_data)
    else:
        with open(json_data, "r") as f:
            data = json.load(f)
    if data_type == "model":
        for node in data.get("nodes", []):
            named_values = node.get("widgets_values_named", {})
            model_name = named_values.get("unet_name")

            if model_name is not None:
                return model_name.removesuffix(".safetensors")

    elif data_type == "prompt":
        for node in data.get("nodes", []):
            if node['type'] == 'ShowText|pysssss':
                prompt = (node["widgets_values"][0][0])

                if prompt is not None:
                    return prompt

    elif data_type == "generation_strategy":
        for node in data.get("nodes", []):
            if node['type'] == 'LoadTextFile':
                text_file_values = node.get("widgets_values", {}) 
                if text_file_values is not None:
                    import re
                    refined_strat = re.search(r'(keyword|sentence)', text_file_values[1])
                    if refined_strat is not None: 
                        return refined_strat.group(1) 
                    else:
                        return 'Unknown'

    elif data_type == "lora":
        lora_entries = []
        for node in data.get("nodes", []):
            named_values = node.get("widgets_values_named", {})
            lora_name = named_values.get("lora_name")
            strength = named_values.get("strength_model")

            if lora_name is not None and strength is not None:
                lora_entries.append(f"{lora_name}: {strength}")

        return ", ".join(lora_entries)

    return model_name

def extract_loras_from_prompt(prompt_text: str) -> Optional[str]:
    """
    Extract LoRA information from the prompt text.
    Looks for patterns like <lora:name:weight> or <lora:name>
    
    Args:
        prompt_text: The full prompt string
    
    Returns:
        Comma-separated string of LoRA names and weights, or None if none found
    """
    import re
    
    if not prompt_text:
        return None
    
    lora_pattern = r'<lora:([^:>]+)(?::([^>]+))?>'
    matches = re.findall(lora_pattern, prompt_text)
    
    if not matches:
        return None
    
    lora_entries = []
    for name, weight in matches:
        if weight:
            lora_entries.append(f"{name}: {weight}")
        else:
            lora_entries.append(name)
    
    return ", ".join(lora_entries) if lora_entries else None

def extract_metadata_from_image(image_path: str, parser_manager: ParserManager) -> Dict:
    """
    Extract metadata from an image using ParserManager.
    
    Returns:
        Dictionary with extracted metadata ready for insertion
    """
    try:
        prompt_info = parser_manager.parse(image_path)
        
        if not prompt_info:
            return {
                'file_name': Path(image_path).name,
                'file_path': image_path,
                'positive_prompt': 'NO_METADATA',
                'negative_prompt': 'NO_METADATA',
                'seed': 'NO_METADATA',
                'model': 'NO_METADATA',
                'steps': 'NO_METADATA',
                'scheduler': 'NO_METADATA',
                'cfg': 'NO_METADATA',
                'loras': 'NO_METADATA'
            }
        
        # Extract checkpoint/model names
        checkpoint_names = []
        if hasattr(prompt_info, 'models') and prompt_info.models:
            for model in prompt_info.models:
                checkpoint_names.append(model.name)
            model_name = ', '.join(checkpoint_names)
        else:
            model_name = ''

        if not model_name and hasattr(prompt_info, 'raw_parameters') and prompt_info.raw_parameters:
            raw_parameters = prompt_info.raw_parameters.get('workflow', {})
            if raw_parameters:
                model_name = extract_data_from_workflow(raw_parameters, "model")
                full_prompt = extract_data_from_workflow(raw_parameters, "prompt")
                generation_strategy = extract_data_from_workflow(raw_parameters, "generation_strategy")
        
        # Extract sampler information
        sampler_name = ''
        cfg_scale = ''
        steps = ''
        seed = ''

        if hasattr(prompt_info, 'samplers') and prompt_info.samplers:
            # Initialize lists to collect values from all samplers
            names_list = []
            cfg_list = []
            steps_list = []
            seed_list = []

            for sampler in prompt_info.samplers:
                if hasattr(sampler, 'name'):
                    names_list.append(str(sampler.name))
                    
                if hasattr(sampler, 'parameters') and sampler.parameters:
                    params = sampler.parameters
                    
                    # Extract values (default to empty string if not found)
                    cfg = params.get('cfg_scale') or params.get('cfg') or ''
                    step = params.get('steps') or params.get('step') or ''
                    sd = params.get('seed') or ''
                    
                    cfg_list.append(str(cfg))
                    steps_list.append(str(step))
                    seed_list.append(str(sd))
            
            # Convert all collected lists to comma-separated strings
            sampler_name = ', '.join(names_list)
            cfg_scale = ', '.join(cfg_list)
            steps = ', '.join(steps_list)
            seed = ', '.join(seed_list)

        # positive prompt
        if not full_prompt:
            full_prompt = prompt_info.full_prompt if hasattr(prompt_info, 'full_prompt') else ''
            if not full_prompt and hasattr(prompt_info, 'metadata') and prompt_info.metadata:
                show_text_nodes = prompt_info.metadata.get("ShowText|pysssss", [])
                if show_text_nodes:
                    text_parts = []
                    for node in show_text_nodes:
                        text = node.get("text_0")
                        if text:
                            text_parts.append(text)
                    full_prompt = "\n".join(text_parts) if text_parts else ''
        
        # Negative prompt
        negative_prompt = ''
        if hasattr(prompt_info, 'full_negative_prompt') and prompt_info.full_negative_prompt:
            negative_prompt = prompt_info.full_negative_prompt
        elif hasattr(prompt_info, 'metadata') and prompt_info.metadata:
            show_text_nodes = prompt_info.metadata.get("ShowText|pysssss", [])
            if show_text_nodes:
                neg_parts = []
                for node in show_text_nodes:
                    text = node.get("text_1")
                    if text:
                        neg_parts.append(text)
                negative_prompt = "\n".join(neg_parts) if neg_parts else ''

        # Extract LoRAs from prompt
        loras = extract_loras_from_prompt(full_prompt)
        if not loras and hasattr(prompt_info, 'raw_parameters') and prompt_info.raw_parameters:
            raw_parameters = prompt_info.raw_parameters.get('workflow', {})
            if raw_parameters:
                loras = extract_data_from_workflow(raw_parameters, "lora")
        
        return {
            'file_name': Path(image_path).name,
            'file_path': image_path,
            'positive_prompt': full_prompt,
            'negative_prompt': negative_prompt,
            'seed': seed,
            'model': model_name,
            'steps': int(steps) if steps else None,
            'scheduler': sampler_name,
            'cfg': float(cfg_scale) if cfg_scale else None,
            'loras': loras if loras else None,
            'generation_strategy': generation_strategy if generation_strategy else 'Unknown'
        }
        
    except Exception as e:
        print(f"Error extracting metadata from {image_path}: {e}")
        return {
            'file_name': Path(image_path).name,
            'file_path': image_path,
            'positive_prompt': f'ERROR: {str(e)}',
            'negative_prompt': f'ERROR: {str(e)}',
            'seed': 'ERROR',
            'model': 'ERROR',
            'steps': 'ERROR',
            'scheduler': 'ERROR',
            'cfg': 'ERROR',
            'loras': 'ERROR',
            'generation_strategy': 'ERROR',
        }

def get_unreviewed_images(limit: int = 50) -> List[Dict]:
    """Get images that haven't been reviewed yet."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM image_details 
        WHERE verdict IS NULL 
        ORDER BY created_at ASC 
        LIMIT ?
    """, (limit,))
    
    return [dict(row) for row in cursor.fetchall()]

def get_image_with_layers(image_id: int) -> Dict:
    """Get an image with all its layer evaluations."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get image details
    cursor.execute("SELECT * FROM image_details WHERE image_id = ?", (image_id,))
    image = cursor.fetchone()
    
    if not image:
        return None
    
    # Get layer evaluations
    cursor.execute("""
        SELECT * FROM layer_evaluations 
        WHERE image_id = ? 
        ORDER BY layer_number ASC
    """, (image_id,))
    
    layers = [dict(row) for row in cursor.fetchall()]
    
    result = dict(image)
    result['layers'] = layers
    
    return result

def mark_as_seen(image_path):
    """Mark an image as seen in the database by incrementing times_displayed"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    image_name = os.path.basename(image_path)
    abs_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static', image_path)
    
    cursor.execute('SELECT times_displayed FROM image_details WHERE image_id = ?', (image_name,))
    result = cursor.fetchone()
    
    if result:
        new_count = result[0] + 1
        cursor.execute(
            'UPDATE image_details SET times_displayed = ? WHERE image_id = ?',
            (new_count, image_name)
        )
    else:
        cursor.execute(
            'INSERT INTO image_details (file_path, file_name, times_displayed) VALUES (?, ?, 1)',
            (normalize_path(abs_path), image_name)
        )
    
    conn.commit()
    conn.close()

def get_image_stats(image_path):
    """Get image statistics from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    image_id = os.path.basename(image_path)
    
    cursor.execute('SELECT times_displayed FROM image_details WHERE image_id = ?', (image_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {'times_displayed': result[0]}
    return {'times_displayed': 0}

def mark_deleted(image_path):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    image_id = os.path.basename(image_path)

    # Check if a fix_reason already exists for this image
    cursor.execute(
        "SELECT fix_reason FROM image_details WHERE image_id = ?",
        (image_id,)
    )
    row = cursor.fetchone()

    # Only set the default reason if none exists (or it's empty/null)
    if row is None or not row[0]:
        cursor.execute("""
            UPDATE image_details 
            SET verdict = 'Dud', 
                fix_category = 'Deleted', 
                fix_reason = 'Image deleted by user' 
            WHERE image_id = ?""", (image_id,))
    else:
        # Preserve existing fix_reason, only update verdict and fix_category
        cursor.execute("""
            UPDATE image_details 
            SET verdict = 'Dud', 
                fix_category = 'Deleted' 
            WHERE image_id = ?""", (image_id,))

    conn.commit()
    conn.close()

def find_image(image_path):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT image_id FROM image_details WHERE file_path = ?", (image_path,))
    result = cursor.fetchone()

    return result

def update_image_review(image_id: int, review_data: Dict):
    """Update review fields for an image."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE image_details 
        SET verdict = ?,
            reviewed_at = ?,
            fix_category = ?,
            fix_reason = ?,
            times_displayed = times_displayed + 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE image_id = ?
    """, (
        review_data.get('verdict'),
        datetime.now().isoformat(),
        review_data.get('fix_category'),
        review_data.get('fix_reason'),
        image_id
    ))
    
    conn.commit()
    conn.close()