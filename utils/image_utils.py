"""
UMACAD - Image Processing Utilities
Helper functions for image manipulation and processing
"""

from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Tuple, List, Optional, Any
import io


def create_multiview_grid(renders: Dict[str, Image.Image],
                          grid_size: Tuple[int, int] = (2, 2),
                          spacing: int = 10,
                          background_color: Tuple[int, int, int] = (255, 255, 255)) -> Optional[Image.Image]:
    """
    Create a grid layout of multiple view renders
    
    Args:
        renders: Dictionary of view_name -> PIL Image
        grid_size: (rows, cols) for grid layout
        spacing: Pixels between images
        background_color: RGB background color
        
    Returns:
        Combined PIL Image or None if input is empty
    """
    if not renders:
        return None
    
    # Get image sizes (assume all same size)
    # We cast to list to safely access values
    first_img = list(renders.values())[0]
    img_width, img_height = first_img.size
    
    rows, cols = grid_size
    
    # Calculate grid dimensions
    grid_width = cols * img_width + (cols + 1) * spacing
    grid_height = rows * img_height + (rows + 1) * spacing
    
    # Create blank canvas
    grid = Image.new('RGB', (grid_width, grid_height), background_color)
    draw = ImageDraw.Draw(grid)
    
    # Place images
    view_list = list(renders.items())
    for idx, (view_name, img) in enumerate(view_list[:rows * cols]):
        row = idx // cols
        col = idx % cols
        
        x = spacing + col * (img_width + spacing)
        y = spacing + row * (img_height + spacing)
        
        grid.paste(img, (x, y))
        
        # Add label
        try:
            # Try loading a readable font
            font = ImageFont.truetype("arial.ttf", 16)
        except OSError:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", 16)
            except OSError:
                font = ImageFont.load_default()
        
        # Draw text with a small outline for visibility
        draw.text((x + 5, y + 5), view_name, fill=(0, 0, 0), font=font)
    
    return grid


def add_dimension_annotations(image: Image.Image,
                              dimensions: List[Dict[str, Any]]) -> Image.Image:
    """
    Add dimension annotations to an image
    
    Args:
        image: PIL Image
        dimensions: List of dimension dictionaries with 'position', 'name', 'value'
        
    Returns:
        Annotated PIL Image
    """
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    
    for dim in dimensions:
        # Default position to top-left if missing
        x, y = dim.get('position', (10, 10))
        
        name = dim.get('name', 'dim')
        value = dim.get('value', 0)
        unit = dim.get('unit', 'mm')
        
        text = f"{name}: {value}{unit}"
        
        draw.text((x, y), text, fill=(255, 0, 0), font=font)
    
    return annotated


def resize_maintaining_aspect(image: Image.Image,
                              max_size: Tuple[int, int]) -> Image.Image:
    """
    Resize image maintaining aspect ratio
    
    Args:
        image: PIL Image
        max_size: (max_width, max_height)
        
    Returns:
        Resized PIL Image
    """
    # Thumbnail modifies the image in-place, so we copy first
    img_copy = image.copy()
    img_copy.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img_copy


def image_to_bytes(image: Image.Image, format: str = 'PNG') -> bytes:
    """Convert PIL Image to bytes"""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


def bytes_to_image(data: bytes) -> Image.Image:
    """Convert bytes to PIL Image"""
    return Image.open(io.BytesIO(data))