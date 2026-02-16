"""
JSON Utility Functions for handling markdown-wrapped JSON responses
"""

import json
import re
from typing import Dict, Any, Optional, Tuple

def extract_json_from_markdown(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from markdown code blocks or raw text.
    Handles various formats:
    - ```json\n{...}\n```
    - ```\n{...}\n```
    - Raw JSON text
    """
    if not text or not text.strip():
        return None
    
    # Clean the text
    text = text.strip()
    
    # Try to extract JSON from markdown code blocks
    json_patterns = [
        r'```json\s*\n(.*?)\n```',  # ```json\n{...}\n```
        r'```\s*\n(.*?)\n```',      # ```\n{...}\n```
        r'```json\s*(.*?)```',       # ```json{...}```
        r'```\s*(.*?)```',           # ```{...}```
    ]
    
    for pattern in json_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            json_text = match.group(1).strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                continue
    
    # If no markdown blocks found, try parsing the entire text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON-like content in the text
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    return None

def is_valid_json(text: str) -> bool:
    """Check if text contains valid JSON"""
    return extract_json_from_markdown(text) is not None

def clean_json_text(text: str) -> str:
    """Clean text to prepare for JSON parsing"""
    if not text:
        return ""
    
    # Remove markdown code block markers
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    
    return text

def ensure_valid_story_json(text: str) -> Tuple[Dict[str, Any], bool]:
    """
    Ensure the provider output can be parsed as a valid story JSON.
    Returns (json_dict, was_repaired).

    Repair steps:
    - Try extract_json_from_markdown
    - Try clean markdown fences and parse
    - Try to locate the first {...} block
    - If all fail, return a safe fallback JSON wrapping the text as center_text
    """
    if not text or not text.strip():
        return ({
            "center_text": "",
            "top_panel_text": "",
            "bottom_panel_text": "",
            "awaits_user_input": True,
            "input_hint": "What do you do?"
        }, True)

    # 1) Try normal extraction
    data = extract_json_from_markdown(text)
    if isinstance(data, dict):
        return (data, False)

    # 2) Clean and parse
    cleaned = clean_json_text(text)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return (parsed, True)
    except Exception:
        pass

    # 3) Try to find first JSON-like block
    block = re.search(r"\{[\s\S]*\}", cleaned)
    if block:
        try:
            parsed = json.loads(block.group(0))
            if isinstance(parsed, dict):
                return (parsed, True)
        except Exception:
            pass

    # 4) Fallback: wrap as valid story JSON
    safe = cleaned if cleaned else text
    return ({
        "center_text": safe.strip(),
        "top_panel_text": "",
        "bottom_panel_text": "",
        "awaits_user_input": True,
        "input_hint": "What do you do?"
    }, True)
