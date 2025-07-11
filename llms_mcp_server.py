#!/usr/bin/env python3
"""
LLMS MCP Server - Documentation Subtopic Access

A production-ready Model Context Protocol server that provides tools for
accessing documentation subtopics from llms-full.txt format.

Environment Variables:
    DOCS_BASE_URL: Base URL of the documentation site (required)
    SERVER_NAME: Name of the server instance (default: "llms-docs")
    CACHE_TTL: Cache TTL in seconds (default: 3600)
    REQUEST_TIMEOUT: HTTP request timeout in seconds (default: 30.0)
"""

import os
import re
import time
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

# Configuration from environment variables
BASE_URL = os.getenv("DOCS_BASE_URL", "")
SERVER_NAME = os.getenv("SERVER_NAME", "llms-docs")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30.0"))

if not BASE_URL:
    raise ValueError(
        "DOCS_BASE_URL environment variable is required. "
        "Set it to the base URL of your documentation site."
    )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    name=SERVER_NAME,
    instructions=f"""
This server provides access to documentation subtopics from {BASE_URL}.
Use list_llms_full_sections() to discover available sections,
then get_llms_full_section(title) to retrieve specific content.
""".strip(),
)

# Constants
USER_AGENT = f"{SERVER_NAME}/1.0"

# In-memory cache with TTL
cache: Dict[str, Tuple[str, float]] = {}


class LLMSFullSection(BaseModel):
    """Represents a section available in llms-full.txt format."""

    title: str = Field(description="The title of the documentation section")
    source_url: str = Field(description="The complete URL of the source document")
    index: int = Field(description="The order index of this section")


def get_cached_content(url: str) -> Optional[str]:
    """Retrieve cached content if available and not expired."""
    if url in cache:
        content, timestamp = cache[url]
        if time.time() - timestamp < CACHE_TTL:
            return content
        else:
            del cache[url]
    return None


def set_cached_content(url: str, content: str) -> None:
    """Cache content with current timestamp."""
    cache[url] = (content, time.time())


async def fetch_content(url: str) -> str:
    """
    Fetch content from URL with caching and comprehensive error handling.

    Args:
        url: The URL to fetch content from

    Returns:
        The content as a string

    Raises:
        ToolError: If the content cannot be fetched
    """
    cached_content = get_cached_content(url)
    if cached_content is not None:
        logger.debug(f"Cache hit for {url}")
        return cached_content

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/plain, text/markdown, text/html, */*",
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            logger.debug(f"Fetching {url}")
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            content = response.text
            set_cached_content(url, content)
            logger.debug(f"Successfully fetched {len(content)} characters from {url}")
            return content

    except httpx.TimeoutException:
        raise ToolError(f"Request timed out when fetching {url}")
    except httpx.HTTPStatusError as e:
        raise ToolError(f"HTTP {e.response.status_code} error when fetching {url}")
    except httpx.RequestError as e:
        raise ToolError(f"Network error when fetching {url}: {e}")
    except Exception as e:
        raise ToolError(f"Unexpected error when fetching {url}: {e}")


def parse_llms_txt(content: str) -> List[Tuple[str, str]]:
    """
    Parse llms.txt content and extract title-URL pairs.

    Args:
        content: Raw content of the llms.txt file

    Returns:
        List of (title, url) tuples found in the content
    """
    links = []
    lines = content.split("\n")
    link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"

    for line in lines:
        matches = re.findall(link_pattern, line)
        for title, url in matches:
            title = title.strip()
            url = url.strip()
            # Only include URLs that look valid
            if "." in url and url:
                links.append((title, url))

    logger.debug(f"Parsed {len(links)} links from llms.txt")
    return links


def normalize_url(base_url: str, relative_url: str) -> str:
    """Convert relative URL to absolute URL based on base URL."""
    if relative_url.startswith(("http://", "https://")):
        return relative_url

    if not base_url.endswith("/"):
        base_url += "/"

    return urljoin(base_url, relative_url)


async def get_llms_txt() -> str:
    """Fetch the llms.txt file from the configured documentation site."""
    base_url = BASE_URL
    if not base_url.endswith("/"):
        base_url += "/"

    llms_url = urljoin(base_url, "llms.txt")
    return await fetch_content(llms_url)


@mcp.tool()
async def list_llms_full_sections() -> List[LLMSFullSection]:
    """
    List all sections available in llms-full.txt format.

    Discovers all documentation sections by parsing the llms.txt file
    and returns structured information about each available section.
    This is the recommended starting point for exploring documentation.

    Returns:
        List of available sections with titles, URLs, and index order

    Raises:
        ToolError: If llms.txt cannot be fetched or parsed
    """
    try:
        logger.info("Fetching available documentation sections")

        # Get the llms.txt content
        llms_content = await get_llms_txt()

        # Parse the links from llms.txt
        links = parse_llms_txt(llms_content)

        if not links:
            logger.warning("No documentation links found in llms.txt")
            return []

        # Convert to structured section format
        sections = []
        for index, (title, url) in enumerate(links):
            absolute_url = normalize_url(BASE_URL, url)
            sections.append(
                LLMSFullSection(title=title, source_url=absolute_url, index=index)
            )

        logger.info(f"Found {len(sections)} documentation sections")
        return sections

    except ToolError:
        # Re-raise ToolErrors as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing sections: {e}")
        raise ToolError(f"Failed to list documentation sections: {e}")


@mcp.tool()
async def get_llms_full_section(title: str) -> str:
    """
    Get the complete content of a specific documentation section.

    Retrieves a specific section in standardized llms-full.txt format,
    including section headers and source attribution. Use
    list_llms_full_sections() first to find available section titles.

    Args:
        title: Exact title of the section to retrieve (case-sensitive)

    Returns:
        The complete section content with headers in llms-full.txt format

    Raises:
        ToolError: If the section cannot be found or retrieved
    """
    try:
        logger.info(f"Fetching section: {title}")

        # Get the llms.txt content first to find the section
        llms_content = await get_llms_txt()
        links = parse_llms_txt(llms_content)

        if not links:
            raise ToolError("No documentation sections are available")

        # Find the document with matching title
        target_doc = None
        for doc_title, url in links:
            if doc_title == title:
                target_doc = (doc_title, url)
                break

        if not target_doc:
            available_titles = [doc_title for doc_title, _ in links]
            titles_list = "\n".join(f"- {t}" for t in available_titles)
            raise ToolError(
                f"Section '{title}' not found. " f"Available sections:\n{titles_list}"
            )

        # Fetch the document content
        absolute_url = normalize_url(BASE_URL, target_doc[1])
        doc_content = await fetch_content(absolute_url)

        # Format as standardized llms-full.txt section
        section = f"# {target_doc[0]}\n" f"Source: {absolute_url}\n\n" f"{doc_content}"

        logger.info(
            f"Successfully retrieved section '{title}' " f"({len(section)} characters)"
        )
        return section

    except ToolError:
        # Re-raise ToolErrors as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting section '{title}': {e}")
        raise ToolError(f"Failed to retrieve section '{title}': {e}")


def clear_cache() -> None:
    """Clear the internal cache. Useful for testing or forcing fresh data."""
    global cache
    cache.clear()
    logger.info("Cache cleared")


def get_cache_stats() -> Dict[str, int]:
    """Get cache statistics for monitoring."""
    current_time = time.time()
    active_entries = 0
    expired_entries = 0

    for url, (content, timestamp) in cache.items():
        if current_time - timestamp < CACHE_TTL:
            active_entries += 1
        else:
            expired_entries += 1

    return {
        "active_entries": active_entries,
        "expired_entries": expired_entries,
        "total_entries": len(cache),
        "cache_ttl_seconds": CACHE_TTL,
    }


if __name__ == "__main__":
    logger.info(f"Starting {SERVER_NAME} for {BASE_URL}")
    logger.info(f"Cache TTL: {CACHE_TTL}s, Request timeout: {REQUEST_TIMEOUT}s")
    mcp.run()
