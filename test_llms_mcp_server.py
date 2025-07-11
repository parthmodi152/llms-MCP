#!/usr/bin/env python3
"""
Test suite for LLMS MCP Server

Tests the documentation subtopic access tools using FastMCP's in-memory
testing patterns and mocking capabilities.
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from fastmcp import Client
from fastmcp.exceptions import ToolError

# Import our server
from llms_mcp_server import mcp, clear_cache, get_cache_stats


@pytest.fixture
def mock_llms_txt():
    """Sample llms.txt content for testing."""
    return """
# Documentation

[Getting Started](getting-started.md)
[API Reference](api/reference.html)
[Advanced Topics](docs/advanced.md)
"""


@pytest.fixture
def mock_doc_content():
    """Sample documentation content."""
    return "# Getting Started\n\nThis is the getting started guide..."


@pytest.fixture(autouse=True)
def clear_server_cache():
    """Clear cache before each test."""
    clear_cache()
    yield
    clear_cache()


class TestListLLMSFullSections:
    """Test the list_llms_full_sections tool."""

    async def test_successful_listing(self, mock_llms_txt):
        """Test successful section listing."""
        with patch("llms_mcp_server.fetch_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_llms_txt

            async with Client(mcp) as client:
                result = await client.call_tool("list_llms_full_sections", {})

                assert result.data is not None
                sections = result.data
                assert len(sections) == 3

                # Check first section
                assert sections[0]["title"] == "Getting Started"
                assert sections[0]["index"] == 0
                assert "getting-started.md" in sections[0]["source_url"]

    async def test_empty_llms_txt(self):
        """Test handling of empty llms.txt."""
        with patch("llms_mcp_server.fetch_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "# No links here"

            async with Client(mcp) as client:
                result = await client.call_tool("list_llms_full_sections", {})

                assert result.data == []

    async def test_network_error(self):
        """Test handling of network errors."""
        with patch("llms_mcp_server.fetch_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = ToolError("Network error")

            async with Client(mcp) as client:
                with pytest.raises(Exception) as exc_info:
                    await client.call_tool("list_llms_full_sections", {})

                # Should propagate the ToolError
                assert "Network error" in str(exc_info.value)


class TestGetLLMSFullSection:
    """Test the get_llms_full_section tool."""

    async def test_successful_retrieval(self, mock_llms_txt, mock_doc_content):
        """Test successful section retrieval."""
        with patch("llms_mcp_server.fetch_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = [mock_llms_txt, mock_doc_content]

            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_llms_full_section", {"title": "Getting Started"}
                )

                content = result.data
                assert "# Getting Started" in content
                assert "Source:" in content
                assert mock_doc_content in content

    async def test_section_not_found(self, mock_llms_txt):
        """Test handling of non-existent section."""
        with patch("llms_mcp_server.fetch_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_llms_txt

            async with Client(mcp) as client:
                with pytest.raises(Exception) as exc_info:
                    await client.call_tool(
                        "get_llms_full_section", {"title": "Non-existent Section"}
                    )

                error_msg = str(exc_info.value)
                assert "not found" in error_msg
                assert "Available sections:" in error_msg

    async def test_empty_sections_list(self):
        """Test handling when no sections are available."""
        with patch("llms_mcp_server.fetch_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "# No links"

            async with Client(mcp) as client:
                with pytest.raises(Exception) as exc_info:
                    await client.call_tool(
                        "get_llms_full_section", {"title": "Any Title"}
                    )

                assert "No documentation sections are available" in str(exc_info.value)

    async def test_document_fetch_error(self, mock_llms_txt):
        """Test handling of document fetch errors."""
        with patch("llms_mcp_server.fetch_content", new_callable=AsyncMock) as mock_fetch:
            # First call (llms.txt) succeeds, second call (document) fails
            mock_fetch.side_effect = [mock_llms_txt, ToolError("Document not found")]

            async with Client(mcp) as client:
                with pytest.raises(Exception) as exc_info:
                    await client.call_tool(
                        "get_llms_full_section", {"title": "Getting Started"}
                    )

                assert "Document not found" in str(exc_info.value)


class TestCaching:
    """Test caching functionality."""

    async def test_cache_functionality(self, mock_llms_txt):
        """Test that caching works correctly."""
        with patch("llms_mcp_server.fetch_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_llms_txt

            async with Client(mcp) as client:
                # First call should fetch from network
                await client.call_tool("list_llms_full_sections", {})

                # Second call should use cache
                await client.call_tool("list_llms_full_sections", {})

                # Should only have been called once due to caching
                assert mock_fetch.call_count == 1

    def test_cache_stats(self):
        """Test cache statistics."""
        # Initially empty
        stats = get_cache_stats()
        assert stats["active_entries"] == 0
        assert stats["total_entries"] == 0

        # After clearing, should still be empty
        clear_cache()
        stats = get_cache_stats()
        assert stats["active_entries"] == 0


class TestValidation:
    """Test parameter validation."""

    async def test_missing_title_parameter(self):
        """Test that missing title parameter is handled."""
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("get_llms_full_section", {})

    async def test_wrong_parameter_type(self):
        """Test that wrong parameter types are handled."""
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("get_llms_full_section", {"title": 123})


class TestIntegration:
    """Integration tests for complete workflows."""

    async def test_complete_workflow(self, mock_llms_txt, mock_doc_content):
        """Test complete discover-then-fetch workflow."""
        with patch("llms_mcp_server.fetch_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = [
                mock_llms_txt,  # For list_sections
                mock_llms_txt,  # For get_section (to find the title)
                mock_doc_content,  # For get_section (actual content)
            ]

            async with Client(mcp) as client:
                # Step 1: Discover available sections
                sections_result = await client.call_tool("list_llms_full_sections", {})
                sections = sections_result.data

                assert len(sections) > 0
                first_section_title = sections[0]["title"]

                # Step 2: Fetch specific section
                content_result = await client.call_tool(
                    "get_llms_full_section", {"title": first_section_title}
                )

                content = content_result.data
                assert first_section_title in content
                assert "Source:" in content


# Test configuration and fixtures for async testing
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
