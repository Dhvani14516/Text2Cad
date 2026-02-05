"""
UMACAD - Vision Language Model Interface
Handles communication with VLM/LLM providers via OpenAI-compatible APIs.
Supports dynamic base_url for OpenRouter, DeepSeek, Ollama, etc.
"""

from typing import Dict, Any, Optional, Union, List, cast
from PIL import Image
import base64
import io
import os
from loguru import logger
from openai import OpenAI


class VLMInterface:
    """
    Universal Interface for OpenAI-compatible APIs.
    Configurable via dictionary to support multiple providers.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the interface with a specific provider config.
        """
        self.config = config
        self.max_tokens = config.get('max_tokens', 4096)
        self.temperature = config.get('temperature', 0.7)
        
        # 1. Get API Key Name from Config
        api_key_env_var = config.get('api_key_env')
        self.api_key = "dummy-key"  # Default for local models (e.g. Ollama)
        
        if api_key_env_var:
            # 2. Get Actual Key from Environment
            key_val = os.getenv(api_key_env_var)
            if key_val:
                self.api_key = key_val
            else:
                logger.warning(f"API key environment variable '{api_key_env_var}' not found. Using dummy key (may fail for remote APIs).")
            
        # 3. Get Base URL
        self.base_url = config.get('base_url', "https://openrouter.ai/api/v1")

        self.usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
        self._initialize_client()

    def _track_usage(self, response):
        try:
            # Check if usage exists
            if hasattr(response, 'usage') and response.usage:
                u = response.usage
                self.usage["prompt_tokens"] += u.prompt_tokens
                self.usage["completion_tokens"] += u.completion_tokens
                self.usage["total_tokens"] += u.total_tokens
                logger.debug(f"Tokens used: {u.total_tokens} (Total: {self.usage['total_tokens']})")
            else:
                logger.debug(f"API response had no usage data. Provider: {self.base_url}")
        except Exception as e:
            logger.warning(f"Failed to track usage: {e}")
    
    def _initialize_client(self):
        """Initialize the OpenAI client with the config-defined URL"""
        try:
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key
            )
            logger.info(f"VLMInterface connected to: {self.base_url}")
        except Exception as e:
            logger.error(f"Failed to initialize client for {self.base_url}: {e}")
            raise
    
    def analyze_text(self, prompt: str, model_name: str) -> str:
        """Analyze text using LLM"""
        logger.info(f"Analyzing text with model: {model_name}")
        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are an expert CAD design assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            self._track_usage(response)
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"API error (Text) on {self.base_url}: {e}")
            raise
    
    def analyze_with_image(self, 
                           prompt: str,
                           image: Union[str, Image.Image],
                           model_name: str) -> str:
        """Analyze text with image using VLM"""
        logger.info(f"Analyzing text+image with model: {model_name}")
        try:
            # Convert image to base64
            image_data = ""
            image_type = "jpeg"

            if isinstance(image, str):
                with open(image, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                ext = image.split('.')[-1].lower()
                image_type = "png" if ext == "png" else "jpeg"
            elif isinstance(image, Image.Image):
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")
                image_data = base64.b64encode(buffered.getvalue()).decode('utf-8')
                image_type = "png"
            else:
                raise ValueError("Image must be file path or PIL Image")
            
            # Construct message
            user_message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{image_type};base64,{image_data}"
                        }
                    }
                ]
            }

            response = self.client.chat.completions.create(
                model=model_name,
                # FIX: Explicitly cast to Any to silence strict Pylance checks
                messages=cast(Any, [user_message]),
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            self._track_usage(response)
            return response.choices[0].message.content or ""
        
        except Exception as e:
            logger.error(f"API error (Image) on {self.base_url}: {e}")
            raise
            
    def analyze_with_multiple_images(self,
                                     prompt: str,
                                     images: List[Union[str, Image.Image]],
                                     model_name: str) -> str:
        """Analyze text with multiple images simultaneously"""
        logger.info(f"Analyzing text + {len(images)} images with model: {model_name}")
        
        try:
            content_payload: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]

            for img in images:
                pil_img = None
                # Load Image
                try:
                    if isinstance(img, str):
                        pil_img = Image.open(img)
                    elif isinstance(img, Image.Image):
                        pil_img = img
                except Exception as e:
                    logger.warning(f"Skipping invalid image: {e}")
                    continue
                
                if pil_img:
                    # Resize logic
                    if pil_img.width > 512 or pil_img.height > 512:
                        pil_img.thumbnail((512, 512))
                    
                    if pil_img.mode in ('RGBA', 'P'):
                        pil_img = pil_img.convert('RGB')

                    buffered = io.BytesIO()
                    
                    # High quality for CAD lines
                    pil_img.save(buffered, format="JPEG", quality=85)
                    img_data = base64.b64encode(buffered.getvalue()).decode('utf-8')
                    img_type = "jpeg"

                    # Add to payload
                    content_payload.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{img_type};base64,{img_data}",
                            "detail": "auto" 
                        }
                    })

            # Construct the final message dict
            user_message = {
                "role": "user",
                "content": content_payload
            }

            response = self.client.chat.completions.create(
                model=model_name,
                # FIX: Explicitly cast to Any
                messages=cast(Any, [user_message]),
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            self._track_usage(response)
            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"API error (Multi-Image) on {self.base_url}: {e}")
            raise

    def get_usage_stats(self):
        """Return accumulated token usage"""
        return self.usage.copy()