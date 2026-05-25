"""MCP (Model Context Protocol) Server for Nexus System.

This implements an MCP server that exposes the system's tools following the 
Model Context Protocol specification. This allows external AI agents (Claude Code,
Cursor, etc.) to discover and call Nexus system tools.

The MCP server can run standalone or be embedded in the AI Service.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from app.tools import TOOL_DEFINITIONS, SYSTEM_TOOLS, _get_json, _post_json

logger = logging.getLogger("ai-service.mcp")


# ─────────────────────────────────────────────────────────
# MCP Protocol Messages
# ─────────────────────────────────────────────────────────

# MCP Request Types
MCP_REQUEST_LIST_TOOLS = "list_tools"
MCP_REQUEST_CALL_TOOL = "call_tool"
MCP_REQUEST_GET_RESOURCES = "list_resources"
MCP_REQUEST_READ_RESOURCE = "read_resource"

# MCP Response Types
MCP_RESPONSE_SUCCESS = "success"
MCP_RESPONSE_ERROR = "error"


# ─────────────────────────────────────────────────────────
# MCP Tool Handlers
# ─────────────────────────────────────────────────────────

async def _handle_list_tools(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP list_tools request.
    
    Returns all available tools with their schemas for external AI agents.
    """
    tools = []
    for name, definition in TOOL_DEFINITIONS.items():
        tools.append({
            "name": definition["name"],
            "description": definition["description"],
            "input_schema": definition["input_schema"],
        })
    
    return {
        "type": MCP_RESPONSE_SUCCESS,
        "tools": tools,
    }


async def _handle_call_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP call_tool request.
    
    Executes a specific tool with given arguments and returns the result.
    """
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})
    
    if not tool_name:
        return {
            "type": MCP_RESPONSE_ERROR,
            "error": "Tool name is required",
        }
    
    # Find and execute the tool
    for tool in SYSTEM_TOOLS:
        if tool.name == tool_name:
            try:
                result = await tool.ainvoke(arguments)
                return {
                    "type": MCP_RESPONSE_SUCCESS,
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, default=str, indent=2),
                        }
                    ],
                }
            except Exception as e:
                logger.error(f"MCP tool call failed: {tool_name} - {e}")
                return {
                    "type": MCP_RESPONSE_ERROR,
                    "error": str(e),
                }
    
    return {
        "type": MCP_RESPONSE_ERROR,
        "error": f"Tool '{tool_name}' not found. Available: {', '.join(t.name for t in SYSTEM_TOOLS)}",
    }


async def _handle_list_resources(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP list_resources request.
    
    Exposes system resources that can be read.
    """
    return {
        "type": MCP_RESPONSE_SUCCESS,
        "resources": [
            {
                "uri": "nexus://system/status",
                "name": "System Status",
                "description": "Current status of all Nexus microservices",
                "mime_type": "application/json",
            },
            {
                "uri": "nexus://system/tools",
                "name": "Available Tools",
                "description": "Complete list of tools available in the Nexus system",
                "mime_type": "application/json",
            },
            {
                "uri": "nexus://audit/stats",
                "name": "Audit Statistics",
                "description": "Aggregated audit event statistics",
                "mime_type": "application/json",
            },
        ],
    }


async def _handle_read_resource(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP read_resource request."""
    uri = params.get("uri", "")
    
    if uri == "nexus://system/status":
        try:
            health_results = {}
            services = {
                "auth": "http://localhost:8001/api/v1/auth/health",
                "user": "http://localhost:8002/api/v1/users/health",
                "role": "http://localhost:8003/api/v1/roles/health",
                "audit": "http://localhost:8004/api/v1/audit/health",
                "ai": "http://localhost:8005/api/v1/ai/health",
            }
            for name, url in services.items():
                try:
                    data = await _get_json(url)
                    health_results[name] = {"status": "healthy", "data": data}
                except Exception as e:
                    health_results[name] = {"status": "unhealthy", "error": str(e)}
            
            return {
                "type": MCP_RESPONSE_SUCCESS,
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(health_results, indent=2),
                    }
                ],
            }
        except Exception as e:
            return {
                "type": MCP_RESPONSE_ERROR,
                "error": str(e),
            }
    
    elif uri == "nexus://system/tools":
        tools_list = []
        for name, definition in TOOL_DEFINITIONS.items():
            tools_list.append({
                "name": definition["name"],
                "description": definition["description"],
            })
        
        return {
            "type": MCP_RESPONSE_SUCCESS,
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(tools_list, indent=2),
                }
            ],
        }
    
    elif uri == "nexus://audit/stats":
        try:
            data = await _get_json("http://localhost:8004/api/v1/audit/stats")
            return {
                "type": MCP_RESPONSE_SUCCESS,
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(data, indent=2),
                    }
                ],
            }
        except Exception as e:
            return {
                "type": MCP_RESPONSE_ERROR,
                "error": str(e),
            }
    
    return {
        "type": MCP_RESPONSE_ERROR,
        "error": f"Resource '{uri}' not found",
    }


# ─────────────────────────────────────────────────────────
# MCP Request Router
# ─────────────────────────────────────────────────────────

MCP_HANDLERS = {
    MCP_REQUEST_LIST_TOOLS: _handle_list_tools,
    MCP_REQUEST_CALL_TOOL: _handle_call_tool,
    MCP_REQUEST_GET_RESOURCES: _handle_list_resources,
    MCP_REQUEST_READ_RESOURCE: _handle_read_resource,
}


async def handle_mcp_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Route an MCP request to the appropriate handler.
    
    Args:
        request: MCP protocol request with "type" and "params" fields.
            Example: {"type": "call_tool", "params": {"name": "list_users", "arguments": {}}}
    
    Returns:
        MCP protocol response.
    """
    request_type = request.get("type", "")
    params = request.get("params", {})
    
    logger.info(f"MCP request: {request_type}", extra={"params": json.dumps(params, default=str)[:200]})
    
    handler = MCP_HANDLERS.get(request_type)
    if not handler:
        return {
            "type": MCP_RESPONSE_ERROR,
            "error": f"Unknown request type: '{request_type}'. Supported: {', '.join(MCP_HANDLERS.keys())}",
        }
    
    try:
        result = await handler(params)
        return result
    except Exception as e:
        logger.error(f"MCP handler error: {e}")
        return {
            "type": MCP_RESPONSE_ERROR,
            "error": f"Internal error: {str(e)}",
        }