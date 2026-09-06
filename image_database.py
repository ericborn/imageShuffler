import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import json

# Import your existing ParserManager
from sd_parsers import ParserManager


class ImageDatabase:
    def __init__(self, db_path: str = "image_evaluations.db"):
        """Initialize the database connection and create tables if they don't exist."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self.create_tables()
    
    def create_tables(self):
        """Create the database schema."""
        cursor = self.conn.cursor()
        
        # Table 1: image_details
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS image_details (
                image_id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                positive_prompt TEXT,
                negative_prompt TEXT,
                loras TEXT,  -- comma-separated string
                seed INTEGER,
                model TEXT,  -- Checkpoint/model name
                steps INTEGER,
                scheduler TEXT,  -- Sampler name
                cfg REAL,  -- CFG scale
                generation_strategy TEXT,  -- 'Assembled' or 'Freeform'
                
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
                
        self.conn.commit()
        print("✓ Database tables created successfully")
    
    def insert_image(self, image_data: Dict) -> int:
        """
        Insert a new image record.
        
        Args:
            image_data: Dictionary containing image metadata and review fields
        
        Returns:
            image_id: The auto-incremented ID of the new record
        """
        cursor = self.conn.cursor()
        
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
        
        self.conn.commit()
        return cursor.lastrowid
    
    def insert_layer_evaluation(self, layer_data: Dict):
        """
        Insert or update a layer evaluation for an image.
        
        Args:
            layer_data: Dictionary containing layer evaluation data
        """
        cursor = self.conn.cursor()
        
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
        
        self.conn.commit()
    
    def parse_prompt_layers(self, prompt_text: str) -> List[Dict]:
        """
        Parse a colon-delimited prompt into layer components.
        
        Expected format: "CATEGORY: text description. CATEGORY2: another description."
        
        Args:
            prompt_text: The full prompt string
        
        Returns:
            List of dictionaries with 'category' and 'text' keys
        """
        layers = []
        
        if not prompt_text:
            return layers
        
        # Split by patterns like "CATEGORY: " (case insensitive, with colon)
        # Using regex to find all occurrences of word+colon at start of segments
        import re
        
        # Find all category: text pairs
        # Pattern: captures CATEGORY (uppercase word) and the following text until next category or end
        pattern = r'([A-Z_]+):\s*([^A-Z_]+?(?=\s*[A-Z_]+:\s*|$))'
        
        matches = re.findall(pattern, prompt_text, re.IGNORECASE | re.DOTALL)
        
        for idx, (category, text) in enumerate(matches, 1):
            layers.append({
                'layer_number': idx,
                'layer_category': category.upper(),
                'layer_text': text.strip()
            })
        
        return layers

    def extract_loras(json_data):
        """Extract lora_name: strength_model pairs from a ComfyUI workflow JSON.
           Accepts a JSON string, dict, or file path.
        """
        # Handle string, dict, or file path input
        if isinstance(json_data, dict):
            data = json_data
        elif isinstance(json_data, str) and json_data.strip().startswith("{"):
            data = json.loads(json_data)
        else:
            with open(json_data, "r") as f:
                data = json.load(f)

        lora_entries = []

        for node in data.get("nodes", []):
            named_values = node.get("widgets_values_named", {})
            lora_name = named_values.get("lora_name")
            strength = named_values.get("strength_model")

            if lora_name is not None and strength is not None:
                lora_entries.append(f"{lora_name}: {strength}")

        return ", ".join(lora_entries)
    
    def extract_metadata_from_image(self, image_path: str, parser_manager: ParserManager) -> Dict:
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
                    'seed': None,
                    'model': 'NO_METADATA',
                    'steps': None,
                    'scheduler': 'NO_METADATA',
                    'cfg': None,
                    'loras': None
                }
            
            # Extract checkpoint/model names
            checkpoint_names = []
            if hasattr(prompt_info, 'models') and prompt_info.models:
                for model in prompt_info.models:
                    checkpoint_names.append(model.name)
                model_name = ', '.join(checkpoint_names)
            else:
                model_name = ''
            
            # Extract sampler information
            sampler_name = ''
            cfg_scale = None
            steps = None
            seed = None
            
            if hasattr(prompt_info, 'samplers') and prompt_info.samplers:
                sampler = prompt_info.samplers[0]
                sampler_name = sampler.name if hasattr(sampler, 'name') else ''
                
                if hasattr(sampler, 'parameters') and sampler.parameters:
                    params = sampler.parameters
                    cfg_scale = params.get('cfg_scale') or params.get('cfg')
                    steps = params.get('steps') or params.get('step')
                    seed = params.get('seed')
            
            # Extract LoRAs if available
            if hasattr(prompt_info, 'raw_parameters') and prompt_info.raw_parameters:
                raw_parameters = prompt_info.raw_parameters['workflow']
                loras = self.extract_loras(raw_parameters)
            
            return {
                'file_name': Path(image_path).name,
                'file_path': image_path,
                'positive_prompt': prompt_info.full_prompt if hasattr(prompt_info, 'full_prompt') else '',
                'negative_prompt': prompt_info.full_negative_prompt if hasattr(prompt_info, 'full_negative_prompt') else '',
                'seed': seed,
                'model': model_name,
                'steps': int(steps) if steps else None,
                'scheduler': sampler_name,
                'cfg': float(cfg_scale) if cfg_scale else None,
                'loras': loras if loras else None
            }
            
        except Exception as e:
            print(f"Error extracting metadata from {image_path}: {e}")
            return {
                'file_name': Path(image_path).name,
                'file_path': image_path,
                'positive_prompt': f'ERROR: {str(e)}',
                'negative_prompt': f'ERROR: {str(e)}',
                'seed': None,
                'model': 'ERROR',
                'steps': None,
                'scheduler': 'ERROR',
                'cfg': None,
                'loras': None
            }
    
    def get_unreviewed_images(self, limit: int = 50) -> List[Dict]:
        """Get images that haven't been reviewed yet."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM image_details 
            WHERE verdict IS NULL 
            ORDER BY created_at ASC 
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def update_image_review(self, image_id: int, review_data: Dict):
        """Update review fields for an image."""
        cursor = self.conn.cursor()
        
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
        
        self.conn.commit()
    
    def get_image_with_layers(self, image_id: int) -> Dict:
        """Get an image with all its layer evaluations."""
        cursor = self.conn.cursor()
        
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
    
    def close(self):
        """Close the database connection."""
        self.conn.close()


# ============ EXAMPLE USAGE ============

def batch_import_images(image_paths: List[str], db: ImageDatabase, parser_manager: ParserManager):
    """Batch import multiple images with their metadata."""
    
    for image_path in image_paths:
        print(f"Processing: {image_path}")
        
        # Extract metadata
        metadata = db.extract_metadata_from_image(image_path, parser_manager)
        
        # Insert into database
        image_id = db.insert_image(metadata)
        
        # Parse the prompt into layers and insert them
        if metadata['positive_prompt'] and metadata['positive_prompt'] not in ['NO_METADATA', 'ERROR']:
            layers = db.parse_prompt_layers(metadata['positive_prompt'])
            
            for layer in layers:
                layer['image_id'] = image_id
                db.insert_layer_evaluation(layer)
        
        print(f"  ✓ Imported with ID: {image_id}")


# ============ QUERY EXAMPLES ============

def get_top_combinations(db: ImageDatabase):
    """Example query: Find top-performing layer combinations."""
    cursor = db.conn.cursor()
    
    # Find which layer categories are most often 'Visible' in 'Keeper' images
    cursor.execute("""
        SELECT 
            le.layer_category,
            le.execution_status,
            COUNT(*) as count
        FROM layer_evaluations le
        JOIN image_details id ON le.image_id = id.image_id
        WHERE id.verdict = 'Keeper'
        GROUP BY le.layer_category, le.execution_status
        ORDER BY le.layer_category, count DESC
    """)
    
    results = cursor.fetchall()
    for row in results:
        print(f"{row['layer_category']}: {row['execution_status']} = {row['count']}")


def find_failure_patterns(db: ImageDatabase):
    """Example query: Find common failure modes."""
    cursor = db.conn.cursor()
    
    # Find which layers are most often 'Omitted' in 'Dud' images
    cursor.execute("""
        SELECT 
            le.layer_category,
            COUNT(*) as omission_count,
            GROUP_CONCAT(DISTINCT id.fix_category) as fix_categories
        FROM layer_evaluations le
        JOIN image_details id ON le.image_id = id.image_id
        WHERE id.verdict = 'Dud' 
            AND le.execution_status = 'Omitted'
        GROUP BY le.layer_category
        ORDER BY omission_count DESC
    """)
    
    results = cursor.fetchall()
    for row in results:
        print(f"{row['layer_category']}: Omitted in {row['omission_count']} images (Fix categories: {row['fix_categories']})")