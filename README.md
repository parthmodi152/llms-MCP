# LLMS MCP Server

A production-ready Model Context Protocol server for accessing documentation subtopics from llms-full.txt format.

## Features

**Simple & Focused**: Exactly 2 tools for documentation subtopic access:

- `list_llms_full_sections()` - Discover available subtopics
- `get_llms_full_section(title)` - Get complete subtopic content

**Production Ready**:
- ✅ Proper error handling with FastMCP ToolError
- ✅ Comprehensive logging 
- ✅ Structured output with Pydantic models
- ✅ Type-annotated parameters (work correctly in Cursor)
- ✅ HTTP caching with configurable TTL
- ✅ Environment-based configuration
- ✅ Comprehensive test suite
- ✅ Multiple transport support (STDIO, HTTP)

## Quick Start

### 1. Installation

```bash
pip install -r requirements.txt
```

### 2. Run Server

```bash
# Set required environment variable
export DOCS_BASE_URL="https://docs.pydantic.dev/latest/"

# Run with default settings
python llms_mcp_server.py

# Or with custom configuration
export SERVER_NAME="pydantic-docs"
export CACHE_TTL="7200"
export REQUEST_TIMEOUT="45.0"
python llms_mcp_server.py
```

### 3. Use Tools

```python
# 1. Discover available subtopics
sections = await list_llms_full_sections()
# Returns: [{"title": "Getting Started", "source_url": "...", "index": 0}, ...]

# 2. Get specific subtopic
content = await get_llms_full_section("Getting Started")  
# Returns: "# Getting Started\nSource: ...\n\n[full content]"
```

## Configuration

Configure via environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DOCS_BASE_URL` | ✅ | - | Base URL of documentation site |
| `SERVER_NAME` | ❌ | `llms-docs` | Server instance name |
| `CACHE_TTL` | ❌ | `3600` | Cache TTL in seconds |
| `REQUEST_TIMEOUT` | ❌ | `30.0` | HTTP timeout in seconds |

## Cursor Integration

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "pydantic-docs": {
      "command": "python",
      "args": ["/path/to/llms_mcp_server.py"],
      "env": {
        "DOCS_BASE_URL": "https://docs.pydantic.dev/latest/",
        "SERVER_NAME": "pydantic-docs"
      }
    }
  }
}
```

## Multiple Libraries

Create separate server instances for different documentation:

```json
{
  "mcpServers": {
    "fastapi": {
      "command": "python", 
      "args": ["/path/to/llms_mcp_server.py"],
      "env": {
        "DOCS_BASE_URL": "https://fastapi.tiangolo.com/",
        "SERVER_NAME": "fastapi-docs"
      }
    },
    "django": {
      "command": "python",
      "args": ["/path/to/llms_mcp_server.py"], 
      "env": {
        "DOCS_BASE_URL": "https://docs.djangoproject.com/en/stable/",
        "SERVER_NAME": "django-docs"
      }
    }
  }
}
```

## Testing

Run the comprehensive test suite:

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
python -m pytest test_llms_mcp_server.py -v

# Or directly
python test_llms_mcp_server.py
```

## Transport Options

**STDIO (Default)**: Best for local tools and Cursor integration
```bash
python llms_mcp_server.py
```

**HTTP**: Best for web deployments and remote access
```bash
# Using run method arguments
python -c "
import llms_mcp_server
llms_mcp_server.mcp.run(transport='http', host='0.0.0.0', port=8000)
"

# Or using FastMCP CLI
fastmcp run llms_mcp_server.py --transport http --port 8000
```

## Architecture

- **llms_mcp_server.py**: Main production server with 2 tools
- **test_llms_mcp_server.py**: Comprehensive test suite
- **requirements.txt**: Dependencies

**Design Principles**:
- Minimal complexity (only 2 tools)
- Production-ready error handling
- FastMCP best practices
- Comprehensive testing
- Clear documentation

## Workflow

1. **Discovery**: `list_llms_full_sections()` returns structured list
2. **Access**: `get_llms_full_section(title)` returns formatted content  
3. **Caching**: Automatic 1-hour HTTP caching for performance
4. **Error Handling**: Clear error messages for troubleshooting

Perfect for AI agents that need reliable, simple access to documentation subtopics.

