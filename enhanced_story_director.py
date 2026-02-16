"""
Enhanced Story Director with World Template Integration

This service integrates the world template engine with story generation
to provide rich, contextual story experiences that maintain world continuity.

SECURITY NOTE: Never pass internal IDs, timestamps, or system identifiers to LLM prompts.
All prompts should be sanitized to remove database IDs, session tokens, and metadata.
"""

from typing import AsyncIterator, Dict, Any, List, Optional
import json
from datetime import datetime
from .llm_factory import get_provider
from .world_template_engine import WorldTemplateEngine
from .prompt_loader import prompt_loader
from .json_utils import extract_json_from_markdown
from .entity_classifier_service import entity_classifier
# Legacy world_monitor removed - using conversation-specific monitors now
from ..models_legacy import World, LoadState, StorySlide
from ..core.config import settings

def get_system_primer() -> str:
    """Load the system primer from the .txt file"""
    return prompt_loader.load_story_generation_prompt()

# SVG hints for when image generation is enabled
SVG_TOP_HINTS = [
    "<svg viewBox='0 0 320 60'><circle cx='50' cy='20' r='3' fill='white'/><circle cx='100' cy='15' r='2' fill='white'/><circle cx='150' cy='25' r='3' fill='white'/><circle cx='200' cy='18' r='2' fill='white'/><circle cx='250' cy='22' r='3' fill='white'/><path d='M0,40 Q80,35 160,40 T320,40' stroke='white' stroke-width='1' fill='none'/></svg>",
    "<svg viewBox='0 0 320 60'><path d='M20,30 L40,20 L60,30 L80,25 L100,30 L120,28 L140,30 L160,26 L180,30 L200,24 L220,30 L240,27 L260,30 L280,25 L300,30' stroke='white' stroke-width='2' fill='none'/><circle cx='50' cy='15' r='2' fill='white'/><circle cx='150' cy='12' r='2' fill='white'/><circle cx='250' cy='18' r='2' fill='white'/></svg>",
    "<svg viewBox='0 0 320 60'><circle cx='30' cy='20' r='4' fill='white'/><circle cx='80' cy='15' r='3' fill='white'/><circle cx='130' cy='25' r='4' fill='white'/><circle cx='180' cy='18' r='3' fill='white'/><circle cx='230' cy='22' r='4' fill='white'/><circle cx='280' cy='16' r='3' fill='white'/><path d='M0,45 Q160,40 320,45' stroke='white' stroke-width='1' fill='none'/></svg>",
]

SVG_BOTTOM_HINTS = [
    "<svg viewBox='0 0 320 60'><rect x='20' y='30' width='40' height='30' fill='white'/><rect x='80' y='25' width='40' height='35' fill='white'/><rect x='140' y='28' width='40' height='32' fill='white'/><rect x='200' y='26' width='40' height='34' fill='white'/><rect x='260' y='29' width='40' height='31' fill='white'/></svg>",
    "<svg viewBox='0 0 320 60'><rect x='15' y='35' width='30' height='25' fill='white'/><rect x='60' y='30' width='30' height='30' fill='white'/><rect x='105' y='33' width='30' height='27' fill='white'/><rect x='150' y='31' width='30' height='29' fill='white'/><rect x='195' y='34' width='30' height='26' fill='white'/><rect x='240' y='32' width='30' height='28' fill='white'/><rect x='285' y='35' width='30' height='25' fill='white'/></svg>",
    "<svg viewBox='0 0 320 60'><rect x='25' y='28' width='35' height='32' fill='white'/><rect x='75' y='25' width='35' height='35' fill='white'/><rect x='125' y='30' width='35' height='30' fill='white'/><rect x='175' y='27' width='35' height='33' fill='white'/><rect x='225' y='29' width='35' height='31' fill='white'/><rect x='275' y='26' width='35' height='34' fill='white'/></svg>",
]

# Simple text placeholders for when image generation is disabled
TEXT_TOP_HINTS = [
    "🌲 Forest Canopy",
    "🏔️ Mountain Peaks", 
    "⭐ Starry Sky",
    "🌅 Sunrise Horizon",
    "🌊 Ocean Waves",
    "🌙 Moonlit Night"
]

TEXT_BOTTOM_HINTS = [
    "🪨 Rocky Ground",
    "🌿 Forest Floor",
    "🏰 Castle Walls",
    "🛤️ Ancient Path",
    "💎 Crystal Caves",
    "🔥 Campfire"
]

# Configuration flags
ENABLE_ASCII_ART = False  # Set to False to disable ASCII art generation
ENABLE_REAL_TIME_SYNC = True  # Set to False to disable real-world time synchronization

def get_panel_hints(index: int) -> tuple[str, str]:
    """Get appropriate panel hints based on image generation and ASCII art settings."""
    if not settings.ENABLE_ASCII_ART:
        return ("", "")  # No ASCII art when disabled
    
    if settings.ENABLE_IMAGE_GENERATION:
        return (
            SVG_TOP_HINTS[index % len(SVG_TOP_HINTS)],
            SVG_BOTTOM_HINTS[index % len(SVG_BOTTOM_HINTS)]
        )
    else:
        return (
            TEXT_TOP_HINTS[index % len(TEXT_TOP_HINTS)],
            TEXT_BOTTOM_HINTS[index % len(TEXT_BOTTOM_HINTS)]
        )

async def stream_next_slide_with_world_context(
    world: World, 
    load_state: LoadState, 
    payload: Dict[str, Any],
    story_history: List[Dict] = None,
    conversation_id: str = None
) -> AsyncIterator[str]:
    """
    Stream next slide with full world context integration.
    This is the main function that creates the GTA-like character switching experience.
    """
    
    # Create world template engine instance
    template_engine = WorldTemplateEngine()
    
    # Update world activity
    template_engine.update_world_activity(world, load_state)
    
    # Generate comprehensive world template (or use override from caller)
    override = payload.get("world_context_override")
    if override:
        world_template = override
    else:
        world_template = template_engine.generate_world_template(
            world, load_state, story_history
        )
    
    # Get provider
    provider = get_provider()
    
    # Extract payload data
    world_id = payload["world_id"]
    chapter_id = payload["chapter_id"]
    last_index = payload.get("last_slide_index", 0)
    player_input = payload.get("player_input")
    
    # Generate story context based on world template and player input
    story_context = world_template

    # Incorporate recent conversation history (compact) if provided
    if story_history:
        # Build a compact transcript of the last N exchanges within a token-ish cap
        def approx_tokens(text: str) -> int:
            # Rough token estimate: 1 token ~ 4 chars English
            return max(1, len(text) // 4)

        max_tokens = 1200  # reserve most of context for system/world; adjust as needed
        used_tokens = 0
        transcript_lines: List[str] = []
        # story_history is a list of dicts from DB; map to role/content
        for msg in story_history[-50:]:  # hard cap to 50 recent messages
            role = msg.get("message_type", "user").upper()
            content = msg.get("content", "")
            # Skip very long blobs like full JSON responses; prefer center_text if present
            try:
                from .json_utils import extract_json_from_markdown
                parsed = extract_json_from_markdown(content)
                if isinstance(parsed, dict) and parsed.get("center_text"):
                    content = parsed["center_text"]
            except Exception:
                pass

            line = f"{('Player' if role == 'USER' else 'Narrator')}: {content.strip()}"
            cost = approx_tokens(line)
            if used_tokens + cost > max_tokens:
                break
            transcript_lines.append(line)
            used_tokens += cost

        if transcript_lines:
            story_context += "\n\nPREVIOUS CONVERSATION (compact):\n" + "\n".join(transcript_lines)
    
    if player_input:
        # Classify entities in player input
        entities = entity_classifier.classify_entities(player_input, {
            "world_id": world_id,
            "world_type": world.world_type,
            "current_location": load_state.current_location,
            "time_of_day": load_state.time_of_day,
            "weather": load_state.weather
        })
        
        # Add entity context to story context
        if entities:
            entity_context = "\n\nDETECTED ENTITIES IN PLAYER INPUT:\n"
            for entity in entities:
                entity_context += f"- {entity.text} ({entity.entity_type.value}, confidence: {entity.confidence:.2f})\n"
            story_context += entity_context
        
        story_context += f"\n\nPLAYER'S RESPONSE: {player_input}\n\nContinue the story based on the player's choice. Maintain the established tone and setting."
    
    # Apply intensity moderation
    from ..services.intensity_moderation_service import IntensityModerationService
    intensity_service = IntensityModerationService()
    intensity_instructions = intensity_service.generate_intensity_prompt("story_generation", world.stats)
    
    # Build messages for the provider
    system_reminder = payload.get("system_reminder")
    system_prefix = f"{system_reminder}\n\n" if system_reminder else ""
    messages: List[Dict[str, str]] = [
        {
            "role": "system", 
            "content": f"{system_prefix}{get_system_primer()}\n\n{intensity_instructions}\n\n{story_context}"
        },
        {
            "role": "user", 
            "content": f"""Player Input: {player_input or "Continue the story"}

Current Situation:
- Location: {load_state.current_location}
- Time: {load_state.time_of_day}
- Weather: {load_state.weather}

Continue the story based on the player's input. Do not repeat technical information like world IDs, chapter IDs, or slide indices unless explicitly requested. Focus on narrative content and story progression."""
        }
    ]

    # Stream the response
    buffer = ""
    print(f"🔍 ENHANCED DIRECTOR: Starting provider.stream() with provider: {type(provider)}")
    print(f"🔍 ENHANCED DIRECTOR: Messages length: {len(messages)}")
    print(f"🔍 ENHANCED DIRECTOR: World type: {world.world_type}")
    
    try:
        chunk_count = 0
        async for chunk in provider.stream(
            messages, 
            temperature=0.7, 
            session_token=payload.get("session_token"),
            world_id=world_id,
            template=world.world_type,
            user_input=player_input,
            sampling_override=payload.get("sampling_override")
        ):
            chunk_count += 1
            buffer += chunk
            print(f"🔍 ENHANCED DIRECTOR: Received chunk {chunk_count}: {chunk[:50]}...")
            # Yield individual chunks for real-time streaming
            yield chunk
        
        print(f"🔍 ENHANCED DIRECTOR: Total chunks received: {chunk_count}")
        print(f"🔍 ENHANCED DIRECTOR: Total buffer length: {len(buffer)}")
        
        # Track token usage for story generation
        if buffer.strip():
            try:
                from .token_counting_middleware import token_counting_middleware
                from .enhanced_token_analytics import PromptType
                
                # Extract prompt text from messages
                prompt_text = "\n\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
                
                # Track story generation
                token_counting_middleware.track_story_generation(
                    world_id=world_id,
                    conversation_id=conversation_id,
                    user_id=payload.get("user_id", "system"),
                    prompt_text=prompt_text,
                    response_text=buffer
                )
                
                print(f"🔍 TOKEN TRACKING: Tracked story generation for world {world_id}")
            except Exception as e:
                print(f"⚠️ TOKEN TRACKING ERROR: {e}")
        
        # Generate image if enabled and we have story content
        # Check both global setting and user preference
        user_image_enabled = payload.get("image_generation_enabled", True)
        if settings.ENABLE_IMAGE_GENERATION and user_image_enabled and buffer.strip():
            try:
                from .freepik_image_generator import freepik_generator
                from .json_utils import extract_json_from_markdown
                
                # Check if we should generate an image (every second message)
                should_generate_image = await _should_generate_image(conversation_id, world_id, user_image_enabled)
                
                if should_generate_image:
                    # Extract story data to get the center text for image generation
                    story_data = extract_json_from_markdown(buffer)
                    if story_data and story_data.get("center_text"):
                        story_text = story_data["center_text"]
                        print(f"🎨 ENHANCED DIRECTOR: Generating image for story context (message #{await _get_message_count(conversation_id)}): {story_text[:100]}...")
                        
                        # Generate image based on story context
                        image_data = await freepik_generator.generate_story_image(
                            story_context=story_text,
                            world_type=world.world_type,
                            style="atmospheric"
                        )
                        
                        if image_data:
                            print(f"✅ ENHANCED DIRECTOR: Image generated successfully: {image_data.get('image_url', 'No URL')}")
                            # Add image data to the story response
                            if story_data:
                                story_data["image_data"] = image_data
                                # Re-serialize the JSON with image data and wrap in markdown
                                updated_buffer = f"```json\n{json.dumps(story_data, indent=2)}\n```"
                                
                                # Send the updated response with image data as a final chunk
                                print(f"🎨 ENHANCED DIRECTOR: Sending updated response with image data")
                                yield updated_buffer
                                
                                # Update buffer for storage
                                buffer = updated_buffer
                        else:
                            print(f"⚠️ ENHANCED DIRECTOR: Image generation failed")
                    else:
                        print(f"⚠️ ENHANCED DIRECTOR: Could not extract story text for image generation")
                else:
                    print(f"🎨 ENHANCED DIRECTOR: Skipping image generation (not every second message)")
            except Exception as e:
                print(f"❌ ENHANCED DIRECTOR IMAGE ERROR: {e}")
                import traceback
                print(f"❌ IMAGE TRACEBACK: {traceback.format_exc()}")
        
        # Audio generation is now handled manually via UI - no automatic generation
        
        # Store the full Gemini conversation
        if conversation_id:
            await _store_gemini_conversation(conversation_id, world_id, messages, buffer, chunk_count)
        
    except Exception as e:
        print(f"❌ ENHANCED DIRECTOR ERROR: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise
    
    # World Monitor Analysis - Automatically triggered after story generation
    if conversation_id and buffer.strip():
        try:
            # Use utility function to extract JSON from markdown-wrapped response
            from ..services.json_utils import extract_json_from_markdown
            story_data = extract_json_from_markdown(buffer)
            
            if story_data:
                from ..services.conversation_world_monitor import ConversationWorldMonitor
                conversation_monitor = ConversationWorldMonitor(conversation_id, world_id)
                world_decision = await conversation_monitor.analyze_game_event(
                    world, load_state, player_input or "Continue story", story_data.get("center_text", "")
                )
                print(f"🔍 WORLD MONITOR: Analysis complete for conversation {conversation_id}")
            else:
                print(f"⚠️ WORLD MONITOR: Could not parse JSON from response for conversation {conversation_id}")
                print(f"⚠️ RAW BUFFER: {buffer[:200]}...")
        except Exception as e:
            print(f"⚠️ WORLD MONITOR ERROR: {e}")
            import traceback
            print(f"⚠️ TRACEBACK: {traceback.format_exc()}")

async def create_initial_story_slide(
    world: World, 
    load_state: LoadState, 
    payload: Dict[str, Any]
) -> AsyncIterator[str]:
    """
    Create the initial story slide for a new world or load state.
    This sets up the world and begins the adventure.
    """
    
    # Create world template engine instance
    template_engine = WorldTemplateEngine()
    
    # Update world activity
    template_engine.update_world_activity(world, load_state)
    
    # Generate initial world template
    world_template = template_engine.create_initial_world_template(world)
    
    # Get provider
    provider = get_provider()
    
    # Extract payload data
    world_id = payload["world_id"]
    chapter_id = payload["chapter_id"]
    
    # Apply intensity moderation
    from ..services.intensity_moderation_service import IntensityModerationService
    intensity_service = IntensityModerationService()
    intensity_instructions = intensity_service.generate_intensity_prompt("story_generation", world.stats)
    
    # Build messages for the provider
    messages: List[Dict[str, str]] = [
        {
            "role": "system", 
            "content": f"{get_system_primer()}\n\n{intensity_instructions}\n\n{world_template}"
        },
        {
            "role": "user", 
            "content": json.dumps({
                "world_id": world_id,
                "chapter_id": chapter_id,
                "last_slide_index": 0,
                "player_input": None,
                "template": world.world_type,
                "world_name": world.name,
                "is_initial": True,
                "style": {
                    "top_panel_hint": get_panel_hints(0)[0],
                    "bottom_panel_hint": get_panel_hints(0)[1]
                }
            })
        }
    ]

    # Stream the response
    buffer = ""
    async for chunk in provider.stream(
        messages, 
        temperature=0.7, 
        session_token=payload.get("session_token"),
        world_id=world_id,
        template=world.world_type,
        user_input=None,
        sampling_override=payload.get("sampling_override")
    ):
        buffer += chunk
        yield chunk
    
    # Try to parse as JSON and yield complete slide
    if buffer.strip():
        try:
            story_data = extract_json_from_markdown(buffer)
            # Just yield the center_text for clean streaming
            if "center_text" in story_data:
                yield story_data["center_text"]
        except json.JSONDecodeError:
            # Fallback if not JSON - just yield the text
            yield buffer.strip()

def update_load_state_from_story_data(
    load_state: LoadState, 
    story_data: Dict[str, Any]
) -> None:
    """
    Update load state based on story data to maintain world continuity.
    This extracts information from the LLM response to update the world state.
    """
    
    # Update basic slide info
    load_state.current_slide_index = story_data.get("slide_index", load_state.current_slide_index)
    load_state.total_slides = max(load_state.total_slides, load_state.current_slide_index)
    
    # Extract location information if mentioned
    center_text = story_data.get("center_text", "")
    if "location" in center_text.lower() or "place" in center_text.lower():
        # Simple location extraction - could be enhanced with NLP
        if "forest" in center_text.lower():
            load_state.current_location = "Forest"
        elif "castle" in center_text.lower():
            load_state.current_location = "Castle"
        elif "village" in center_text.lower():
            load_state.current_location = "Village"
        elif "dungeon" in center_text.lower():
            load_state.current_location = "Dungeon"
    
    # Extract time information
    if "morning" in center_text.lower():
        load_state.time_of_day = "Morning"
    elif "afternoon" in center_text.lower():
        load_state.time_of_day = "Afternoon"
    elif "evening" in center_text.lower():
        load_state.time_of_day = "Evening"
    elif "night" in center_text.lower():
        load_state.time_of_day = "Night"
    
    # Extract weather information
    if "rain" in center_text.lower():
        load_state.weather = "Rainy"
    elif "sunny" in center_text.lower():
        load_state.weather = "Sunny"
    elif "fog" in center_text.lower():
        load_state.weather = "Foggy"
    elif "storm" in center_text.lower():
        load_state.weather = "Stormy"
    
    # Update story context
    if not load_state.story_context:
        load_state.story_context = {}
    
    load_state.story_context["last_slide"] = {
        "slide_index": load_state.current_slide_index,
        "content": center_text,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Add to recent events
    if not load_state.recent_events:
        load_state.recent_events = []
    
    load_state.recent_events.append({
        "description": center_text[:100] + "..." if len(center_text) > 100 else center_text,
        "timestamp": datetime.utcnow().isoformat(),
        "slide_index": load_state.current_slide_index
    })
    
    # Keep only last 10 events
    if len(load_state.recent_events) > 10:
        load_state.recent_events = load_state.recent_events[-10:]
    
    # Update last activity
    load_state.last_activity = datetime.utcnow()

async def _store_gemini_conversation(conversation_id: str, world_id: str, messages: List[Dict[str, str]], response: str, chunk_count: int):
    """Store the full Gemini conversation for debugging and analysis"""
    try:
        from ..models_conversation.conversation import ConversationMessage, MessageType
        from ..db import engine
        from sqlmodel import Session
        import json
        
        # Build the full prompt context
        prompt_context = "=== GEMINI CONVERSATION ===\n"
        for i, msg in enumerate(messages):
            prompt_context += f"Message {i+1} ({msg['role']}):\n{msg['content']}\n\n"
        
        prompt_context += f"=== RESPONSE ===\n{response}\n\n"
        prompt_context += f"=== METADATA ===\nChunks received: {chunk_count}\nResponse length: {len(response)}"
        
        with Session(engine) as session:
            # Create a Gemini conversation message
            gemini_message = ConversationMessage(
                conversation_id=conversation_id,
                world_id=world_id,
                user_id="system",  # Gemini conversation is a system service
                message_type=MessageType.GEMINI_CONVERSATION,
                content=response,
                prompt_context=prompt_context,
                tokens_used=len(prompt_context.split()) + len(response.split()),  # Rough estimate
                response_time_ms=0,  # Will be updated by the calling function
                world_context=f"Gemini conversation for story generation",
                template_variables=json.dumps({
                    "service": "enhanced_story_director",
                    "conversation_type": "story_generation",
                    "chunk_count": chunk_count,
                    "response_length": len(response)
                })
            )
            session.add(gemini_message)
            session.commit()
            
            print(f"🔍 GEMINI CONVERSATION: Stored conversation for {conversation_id}")
    except Exception as e:
        print(f"Error storing Gemini conversation: {e}")

async def _should_generate_image(conversation_id: str, world_id: str, user_image_enabled: bool = True) -> bool:
    """
    Determine if an image should be generated for this message.
    Images are generated every second message to balance visual appeal with performance.
    """
    if not conversation_id or not user_image_enabled:
        return False
    
    try:
        from ..db import engine
        from sqlmodel import Session, select, func
        from ..models_conversation.conversation import ConversationMessage, MessageType
        
        with Session(engine) as session:
            # Count AI messages in this conversation
            ai_message_count = session.exec(
                select(func.count(ConversationMessage.id))
                .where(ConversationMessage.conversation_id == conversation_id)
                .where(ConversationMessage.message_type == MessageType.AI)
            ).first() or 0
            
            # Generate image based on configured frequency
            frequency = settings.IMAGE_GENERATION_FREQUENCY
            should_generate = (ai_message_count + 1) % frequency == 0
            print(f"🎨 IMAGE DECISION: Message #{ai_message_count + 1}, User enabled: {user_image_enabled}, Generate: {should_generate}")
            return should_generate
            
    except Exception as e:
        print(f"❌ IMAGE DECISION ERROR: {e}")
        # Default to generating image if we can't determine message count
        return True

async def _get_message_count(conversation_id: str) -> int:
    """Get the current message count for a conversation"""
    if not conversation_id:
        return 0
    
    try:
        from ..db import engine
        from sqlmodel import Session, select, func
        from ..models_conversation.conversation import ConversationMessage, MessageType
        
        with Session(engine) as session:
            ai_message_count = session.exec(
                select(func.count(ConversationMessage.id))
                .where(ConversationMessage.conversation_id == conversation_id)
                .where(ConversationMessage.message_type == MessageType.AI)
            ).first() or 0
            
            return ai_message_count + 1
            
    except Exception as e:
        print(f"❌ MESSAGE COUNT ERROR: {e}")
        return 1

# Legacy compatibility function - DEPRECATED
async def stream_next_slide(payload: Dict[str, Any]) -> AsyncIterator[str]:
    """
    DEPRECATED: This function is no longer supported.
    Use stream_next_slide_with_world_context instead.
    """
    yield '{"error": "Legacy function deprecated. Use stream_next_slide_with_world_context instead."}'
