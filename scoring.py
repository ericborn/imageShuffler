import os
import re
import pandas as pd
from sd_parsers import ParserManager
from PIL import Image
from imscore.aesthetic.model import LAIONAestheticScorer
import torch
from torchvision import transforms

# Initialize the parser manager
parser_manager = ParserManager()
root_dir = "E:\\Images\\txt2img-images\\prompt test"

# Load the aesthetic model once
print("Loading aesthetic model...")
model = LAIONAestheticScorer.from_pretrained("RE-N-Y/laion-aesthetic")
model.eval()  # Set to evaluation mode
print("Model loaded successfully!")

model_normalize = transforms.Normalize(
    mean=[0.48145466, 0.4578275, 0.40821073],
    std=[0.26862954, 0.26130258, 0.27577711]
)
# Define image preprocessing
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    model_normalize
])

# Initialize empty list to store parsed data
parsed_data = []

# Walk through all subdirectories
for subdir, dirs, files in os.walk(root_dir):
    if subdir == root_dir:
        continue
    
    image_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff')
    image_files = [f for f in files if f.lower().endswith(image_extensions)]
    
    if not image_files:
        continue
    
    # Process EVERY image in the folder
    for image_file in image_files:
        photo_path = os.path.join(subdir, image_file)
        
        try:
            # Extract prompt from the first image (or you can extract from each)
            # If you want to extract prompt from each image individually, move this inside the loop
            if image_file == image_files[0]:  # Only parse prompt once per folder
                prompt_info = parser_manager.parse(photo_path)
                prompt_string = prompt_info.full_prompt if hasattr(prompt_info, 'full_prompt') else ''
                
                # Clean prompt
                prompt_string = prompt_string + ',, ,'
                prompt_string = prompt_string.strip()
                while True:
                    collapsed = re.sub(r',\s*,', ',', prompt_string)
                    if collapsed == prompt_string:
                        break
                    prompt_string = collapsed
                prompt_string = re.sub(r',+$', '', prompt_string)
                prompt_string = re.sub(r',\s*(?!$)', ', ', prompt_string)
            
            # Calculate aesthetic score
            image = Image.open(photo_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Preprocess image and add batch dimension
            image_tensor = transform(image).unsqueeze(0)
            
            # Calculate score
            with torch.no_grad():
                aesthetic_score = model(image_tensor).item()
            
            # Optionally write prompt to each image's folder (only once)
            if image_file == image_files[0]:
                output_path = os.path.join(subdir, 'prompt.txt')
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(f"Prompt: {prompt_string}\n")
                    f.write(f"Aesthetic Score: {aesthetic_score:.4f}")
            
            # Store data for CSV (each image gets its own row)
            parsed_data.append({
                'folder': subdir,
                'image': photo_path,
                'filename': image_file,
                'prompt': prompt_string,
                'aesthetic_score': aesthetic_score,
                'category': 'positive' if 'positive' in subdir.lower() else 'negative'
            })
            
            print(f"✅ Processed {image_file} - Score: {aesthetic_score:.4f}")
            
        except Exception as e:
            print(f"❌ Error processing {photo_path}: {str(e)}")

# Save results
if parsed_data:
    df = pd.DataFrame(parsed_data)
    df.to_csv('aesthetic_analysis.csv', index=False)
    print("\n📊 Analysis Summary:")
    print(f"   Total images processed: {len(df)}")
    print(f"   Average aesthetic score: {df['aesthetic_score'].mean():.4f}")
    print(f"   Max score: {df['aesthetic_score'].max():.4f}")
    print(f"   Min score: {df['aesthetic_score'].min():.4f}")
    
    # Optional: Group by folder to see per-folder statistics
    print("\n📁 Per-folder summary:")
    folder_stats = df.groupby('folder').agg({
        'aesthetic_score': ['count', 'mean', 'std']
    }).round(4)
    print(folder_stats)