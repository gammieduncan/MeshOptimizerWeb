#!/usr/bin/env python
from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path

def create_watermark(text="PREVIEW", size=(512, 128), filename="watermark.png"):
    """
    Create a repeating watermark image with the specified text.
    """
    # Create a transparent image
    watermark = Image.new('RGBA', size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(watermark)
    
    try:
        # Try to use a font file if available
        font = ImageFont.truetype("arial.ttf", 24)
    except IOError:
        # Fall back to default font
        font = ImageFont.load_default()
    
    # Calculate text size (using newer API)
    if hasattr(font, "getbbox"):
        # For Pillow >= 9.2.0
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    else:
        # For older Pillow versions
        text_width, text_height = font.getsize(text)
    
    # Calculate spacing to create a pattern
    x_spacing = text_width + 20
    y_spacing = text_height + 10
    
    # Draw text in a pattern
    for y in range(0, size[1] + y_spacing, y_spacing):
        for x in range(0, size[0] + x_spacing, x_spacing):
            # Alternate the position slightly for a more natural look
            offset_x = (y // y_spacing) % 2 * (x_spacing // 2)
            draw.text((x + offset_x, y), text, font=font, fill=(255, 255, 255, 128))
    
    # Save the watermark
    watermark_path = Path(__file__).parent.parent / "app" / "static" / "images" / filename
    watermark.save(watermark_path)
    print(f"Watermark created at {watermark_path}")
    
if __name__ == "__main__":
    create_watermark() 