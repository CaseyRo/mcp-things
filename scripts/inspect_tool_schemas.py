#!/usr/bin/env python3
"""
Diagnostic script to inspect FastMCP tool schema format.
This helps identify schema compatibility issues with n8n.
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from things_mcp.fast_server import mcp
import mcp.types as types


def inspect_tool_schema(tool):
    """Extract schema information from a tool definition."""
    schema_info = {
        "name": tool.name,
        "description": tool.description,
        "has_inputSchema": hasattr(tool, "inputSchema") and tool.inputSchema is not None,
        "tool_type": type(tool).__name__,
        "tool_attributes": [attr for attr in dir(tool) if not attr.startswith("__")],
    }

    # Check all possible schema-related attributes
    for attr in ["inputSchema", "input_schema", "schema", "parameters", "params"]:
        if hasattr(tool, attr):
            value = getattr(tool, attr)
            if value is not None:
                schema_info[f"has_{attr}"] = True
                schema_info[attr] = value

    if hasattr(tool, "inputSchema") and tool.inputSchema:
        schema = tool.inputSchema
        schema_info["inputSchema"] = {
            "type": getattr(schema, "type", None),
            "properties": getattr(schema, "properties", None),
            "required": getattr(schema, "required", None),
        }

        # Check for inputType property (what n8n might be looking for)
        if isinstance(schema, dict):
            schema_info["inputSchema"]["inputType"] = schema.get("inputType")
            schema_info["inputSchema"]["raw_schema"] = schema
        else:
            # If it's an object, try to get its dict representation
            try:
                schema_dict = schema.model_dump() if hasattr(schema, "model_dump") else dict(schema)
                schema_info["inputSchema"]["inputType"] = schema_dict.get("inputType")
                schema_info["inputSchema"]["raw_schema"] = schema_dict
            except:
                schema_info["inputSchema"]["raw_schema"] = str(schema)

    # Check annotations
    if hasattr(tool, "annotations") and tool.annotations:
        schema_info["annotations"] = {
            "readOnlyHint": getattr(tool.annotations, "readOnlyHint", None),
            "idempotentHint": getattr(tool.annotations, "idempotentHint", None),
            "destructiveHint": getattr(tool.annotations, "destructiveHint", None),
        }

    # Try to get the raw tool dict representation
    try:
        if hasattr(tool, "model_dump"):
            schema_info["raw_tool_dict"] = tool.model_dump()
        elif hasattr(tool, "dict"):
            schema_info["raw_tool_dict"] = tool.dict()
        elif hasattr(tool, "__dict__"):
            schema_info["raw_tool_dict"] = tool.__dict__
    except:
        pass

    return schema_info


def main():
    """Inspect all tools and output their schema structure."""
    print("Inspecting FastMCP tool schemas...")
    print("=" * 80)

    # Get tools from FastMCP server
    # FastMCP stores tools internally, we need to access them
    tools = []
    try:
        # Try different ways to access tools
        if hasattr(mcp, "_tools"):
            tools = list(mcp._tools.values()) if isinstance(mcp._tools, dict) else list(mcp._tools)
        elif hasattr(mcp, "tools"):
            tools = list(mcp.tools.values()) if isinstance(mcp.tools, dict) else list(mcp.tools)
        elif hasattr(mcp, "_server"):
            # FastMCP might store tools in the underlying server
            server = mcp._server
            if hasattr(server, "_tools"):
                tools = list(server._tools.values()) if isinstance(server._tools, dict) else list(server._tools)
            elif hasattr(server, "tools"):
                tools = list(server.tools.values()) if isinstance(server.tools, dict) else list(server.tools)

        # If still no tools, try _tool_manager
        if not tools and hasattr(mcp, "_tool_manager"):
            tool_manager = mcp._tool_manager
            if hasattr(tool_manager, "_tools"):
                tools_dict = tool_manager._tools
                tools = list(tools_dict.values()) if isinstance(tools_dict, dict) else list(tools_dict)
            elif hasattr(tool_manager, "tools"):
                tools_dict = tool_manager.tools
                tools = list(tools_dict.values()) if isinstance(tools_dict, dict) else list(tools_dict)

        # If still no tools, try to inspect the mcp object structure
        if not tools:
            print("DEBUG: Inspecting FastMCP object structure...")
            attrs = [attr for attr in dir(mcp) if not attr.startswith("__")]
            print(f"Available attributes: {attrs[:20]}...")

            # Try _tool_manager
            if hasattr(mcp, "_tool_manager"):
                tm = mcp._tool_manager
                print(f"Tool manager type: {type(tm)}")
                tm_attrs = [attr for attr in dir(tm) if not attr.startswith("__")]
                print(f"Tool manager attributes: {tm_attrs[:20]}")

                # Try to get tools from tool manager
                for attr in ["_tools", "tools", "_registry", "registry"]:
                    if hasattr(tm, attr):
                        value = getattr(tm, attr)
                        if isinstance(value, dict) and len(value) > 0:
                            first_item = list(value.values())[0]
                            if hasattr(first_item, "name"):
                                print(f"Found tools in tool_manager.{attr}")
                                tools = list(value.values())
                                break

        if not tools:
            print("ERROR: Cannot access tools from FastMCP instance")
            print("Trying to access via _server attribute...")
            if hasattr(mcp, "_server"):
                server = mcp._server
                print(f"Server type: {type(server)}")
                print(f"Server attributes: {[attr for attr in dir(server) if not attr.startswith('__')][:20]}")
            return
    except Exception as e:
        print(f"ERROR: Failed to access tools: {e}")
        import traceback
        traceback.print_exc()
        return

    if not tools:
        print("WARNING: No tools found")
        return

    print(f"Found {len(tools)} tools\n")

    # Inspect each tool
    all_schemas = []
    for tool in tools:
        schema_info = inspect_tool_schema(tool)
        all_schemas.append(schema_info)

    # Print summary
    print("TOOL SCHEMA SUMMARY")
    print("=" * 80)
    for schema_info in all_schemas:
        print(f"\nTool: {schema_info['name']}")
        print(f"  Description: {schema_info['description'][:60]}...")
        print(f"  Has inputSchema: {schema_info['has_inputSchema']}")

        if schema_info.get("inputSchema"):
            input_schema = schema_info["inputSchema"]
            print(f"  Schema type: {input_schema.get('type')}")
            print(f"  Has inputType: {'inputType' in str(input_schema.get('raw_schema', {}))}")

            if input_schema.get("properties"):
                print(f"  Properties: {list(input_schema['properties'].keys()) if isinstance(input_schema['properties'], dict) else 'N/A'}")
            if input_schema.get("required"):
                print(f"  Required: {input_schema['required']}")

    # Check for missing inputType
    print("\n" + "=" * 80)
    print("COMPATIBILITY ANALYSIS")
    print("=" * 80)

    tools_without_inputType = []
    for schema_info in all_schemas:
        if schema_info.get("inputSchema"):
            raw_schema = schema_info["inputSchema"].get("raw_schema", {})
            if isinstance(raw_schema, dict) and "inputType" not in raw_schema:
                tools_without_inputType.append(schema_info["name"])

    if tools_without_inputType:
        print(f"\n⚠️  {len(tools_without_inputType)} tools missing 'inputType' property:")
        for name in tools_without_inputType:
            print(f"   - {name}")
    else:
        print("\n✓ All tools have 'inputType' property")

    # Save detailed JSON output
    output_file = Path(__file__).parent / "tool_schemas.json"
    with open(output_file, "w") as f:
        json.dump(all_schemas, f, indent=2, default=str)
    print(f"\n✓ Detailed schema info saved to: {output_file}")

    # Print a sample tool's full schema
    if all_schemas:
        print("\n" + "=" * 80)
        print("SAMPLE TOOL SCHEMA (first tool with parameters)")
        print("=" * 80)
        sample = None
        for schema_info in all_schemas:
            if schema_info.get("inputSchema") and schema_info["inputSchema"].get("properties"):
                sample = schema_info
                break

        if sample:
            print(json.dumps(sample, indent=2, default=str))
        else:
            print("No tools with parameters found for sample")


if __name__ == "__main__":
    main()

