"""Image generation agent using Mistral AI."""

import logging
import uuid
from pathlib import Path

from mistralai import Mistral
from mistralai.models import ToolFileChunk

from dndyo.app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_mistral_client() -> Mistral:
    """Get Mistral client with API key from settings."""
    settings = get_settings()
    return Mistral(
        api_key=settings.mistral_api_key,
        server_url=settings.mistral_server_url,
    )


def _save_image_file(image_bytes: bytes, filename_prefix: str) -> str | None:
    """Save image bytes to disk and return the relative file path.

    Args:
        image_bytes: Raw image data.
        filename_prefix: Prefix for the filename (e.g., 'game-cover', 'map-1').

    Returns:
        Relative file path (e.g., 'images/game-cover-uuid.png'), or None on failure.
    """
    try:
        settings = get_settings()
        # Generate unique filename
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{filename_prefix}-{unique_id}.png"
        filepath = settings.images_path / filename

        # Write file
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        logger.info(f"Saved image to {filepath}")
        # Return relative path for storage in DB
        return str(Path(settings.images_dir) / filename)

    except Exception as e:
        logger.error(f"Failed to save image file: {e}")
        return None


def generate_game_cover_image(game_name: str, game_description: str) -> str | None:
    """Generate a single cover image for a game using Mistral image generation agent.

    Args:
        game_name: Name of the game.
        game_description: Description or theme of the game.

    Returns:
        Relative file path to saved image, or None if generation fails.
    """
    try:
        client = _get_mistral_client()

        # Create image generation agent
        agent = client.beta.agents.create(
            model="mistral-medium-2505",
            name="Game Cover Image Generator",
            description="Agent used to generate game cover images.",
            instructions="Use the image generation tool to create a professional game cover image based on the description provided.",
            tools=[{"type": "image_generation"}],
            completion_args={
                "temperature": 0.3,
                "top_p": 0.95,
            },
        )

        # Start conversation and generate image
        prompt = f"Create a professional game cover image for '{game_name}': {game_description}"
        response = client.beta.conversations.start(
            agent_id=agent.id,
            inputs=prompt,
        )

        # Extract and download the generated image
        if response.outputs and len(response.outputs) > 0:
            for chunk in response.outputs[-1].content:
                if isinstance(chunk, ToolFileChunk):
                    file_bytes = client.files.download(file_id=chunk.file_id).read()
                    return _save_image_file(file_bytes, f"game-cover-{game_name[:20]}")

        logger.warning(f"No image generated for game cover: {game_name}")
        return None

    except Exception as e:
        logger.error(f"Failed to generate game cover image: {e}")
        return None


def generate_map_images(map_names: list[str]) -> dict[str, str | None]:
    """Generate images for multiple maps using Mistral image generation agent.

    Args:
        map_names: List of map names to generate images for.

    Returns:
        Dictionary mapping map names to file paths of saved images.
        Maps with failed generation will have None as value.
    """
    images = {name: None for name in map_names}

    if not map_names:
        return images

    try:
        client = _get_mistral_client()

        # Create image generation agent
        agent = client.beta.agents.create(
            model="mistral-medium-2505",
            name="Map Image Generator",
            description="Agent used to generate map images for D&D games.",
            instructions="Use the image generation tool to create detailed D&D map images based on the descriptions provided.",
            tools=[{"type": "image_generation"}],
            completion_args={
                "temperature": 0.3,
                "top_p": 0.95,
            },
        )

        # Generate image for each map in a single conversation
        map_descriptions = ", ".join(
            [f"a map called '{name}'" for name in map_names]
        )
        prompt = f"Generate {len(map_names)} separate D&D map images for: {map_descriptions}. Each image should be distinct and visually different."

        response = client.beta.conversations.start(
            agent_id=agent.id,
            inputs=prompt,
        )

        # Extract generated images
        image_list = []
        if response.outputs and len(response.outputs) > 0:
            for chunk in response.outputs[-1].content:
                if isinstance(chunk, ToolFileChunk):
                    file_bytes = client.files.download(file_id=chunk.file_id).read()
                    image_list.append(file_bytes)

        # Save images and assign to maps (in order)
        for i, map_name in enumerate(map_names):
            if i < len(image_list):
                file_path = _save_image_file(image_list[i], f"map-{map_name[:20]}")
                images[map_name] = file_path
            else:
                logger.warning(f"No image generated for map: {map_name}")

        return images

    except Exception as e:
        logger.error(f"Failed to generate map images: {e}")
        return images
