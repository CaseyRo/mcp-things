#!/usr/bin/env python3
"""
MCP tools configuration for Things integration with Windsurf.
This ensures proper tool registration and naming for seamless integration.
"""
import mcp.types as types
from typing import List, Dict


READ_ONLY_ANNOTATIONS = types.ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    openWorldHint=False,
)

ADD_ANNOTATIONS = types.ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)

UPDATE_ANNOTATIONS = types.ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


ANNOTATIONS_MAP: Dict[str, types.ToolAnnotations] = {
    "get-todos": READ_ONLY_ANNOTATIONS,
    "get-projects": READ_ONLY_ANNOTATIONS,
    "get-areas": READ_ONLY_ANNOTATIONS,
    "get-inbox": READ_ONLY_ANNOTATIONS,
    "get-today": READ_ONLY_ANNOTATIONS,
    "get-upcoming": READ_ONLY_ANNOTATIONS,
    "get-anytime": READ_ONLY_ANNOTATIONS,
    "get-someday": READ_ONLY_ANNOTATIONS,
    "get-logbook": READ_ONLY_ANNOTATIONS,
    "get-trash": READ_ONLY_ANNOTATIONS,
    "get-tags": READ_ONLY_ANNOTATIONS,
    "get-tagged-items": READ_ONLY_ANNOTATIONS,
    "search-todos": READ_ONLY_ANNOTATIONS,
    "search-advanced": READ_ONLY_ANNOTATIONS,
    "search-items": READ_ONLY_ANNOTATIONS,
    "show-item": READ_ONLY_ANNOTATIONS,
    "get-recent": READ_ONLY_ANNOTATIONS,
    "add-todo": ADD_ANNOTATIONS,
    "add-project": ADD_ANNOTATIONS,
    "update-todo": UPDATE_ANNOTATIONS,
    "update-project": UPDATE_ANNOTATIONS,
}

def get_mcp_tools_list() -> List[types.Tool]:
    """
    Return the list of MCP tools with consistent naming between registration and implementation.
    
    Uses consistent naming without prefixes to ensure proper tool functioning.
    """
    return [
        # Basic operations
        types.Tool(
            name="get-todos",
            description="Get todos from Things, optionally filtered by project",
            annotations=ANNOTATIONS_MAP["get-todos"],
            inputSchema={
                "type": "object",
                "properties": {
                    "project_uuid": {
                        "type": "string",
                        "description": "Optional UUID of a specific project to get todos from",
                    },
                    "include_items": {
                        "type": "boolean",
                        "description": "Include checklist items",
                        "default": True
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get-projects",
            description="Get all projects from Things",
            annotations=ANNOTATIONS_MAP["get-projects"],
            inputSchema={
                "type": "object",
                "properties": {
                    "include_items": {
                        "type": "boolean",
                        "description": "Include tasks within projects",
                        "default": False
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get-areas",
            description="Get all areas from Things",
            annotations=ANNOTATIONS_MAP["get-areas"],
            inputSchema={
                "type": "object",
                "properties": {
                    "include_items": {
                        "type": "boolean",
                        "description": "Include projects and tasks within areas",
                        "default": False
                    }
                },
                "required": [],
            },
        ),

        # List views
        types.Tool(
            name="get-inbox",
            description="Get todos from Inbox",
            annotations=ANNOTATIONS_MAP["get-inbox"],
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="get-today",
            description="Get todos due today",
            annotations=ANNOTATIONS_MAP["get-today"],
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="get-upcoming",
            description="Get upcoming todos",
            annotations=ANNOTATIONS_MAP["get-upcoming"],
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="get-anytime",
            description="Get todos from Anytime list",
            annotations=ANNOTATIONS_MAP["get-anytime"],
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="get-someday",
            description="Get todos from Someday list",
            annotations=ANNOTATIONS_MAP["get-someday"],
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="get-logbook",
            description="Get completed todos from Logbook, defaults to last 7 days",
            annotations=ANNOTATIONS_MAP["get-logbook"],
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period to look back (e.g., '3d', '1w', '2m', '1y'). Defaults to '7d'",
                        "pattern": "^\\d+[dwmy]$"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of entries to return. Defaults to 50",
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get-trash",
            description="Get trashed todos",
            annotations=ANNOTATIONS_MAP["get-trash"],
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),

        # Tag operations
        types.Tool(
            name="get-tags",
            description="Get all tags",
            annotations=ANNOTATIONS_MAP["get-tags"],
            inputSchema={
                "type": "object",
                "properties": {
                    "include_items": {
                        "type": "boolean",
                        "description": "Include items tagged with each tag",
                        "default": False
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get-tagged-items",
            description="Get items with a specific tag",
            annotations=ANNOTATIONS_MAP["get-tagged-items"],
            inputSchema={
                "type": "object",
                "properties": {
                    "tag": {
                        "type": "string",
                        "description": "Tag title to filter by"
                    }
                },
                "required": ["tag"],
            },
        ),

        # Search operations
        types.Tool(
            name="search-todos",
            description="Search todos by title or notes",
            annotations=ANNOTATIONS_MAP["search-todos"],
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term to look for in todo titles and notes",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="search-advanced",
            description="Advanced todo search with multiple filters",
            annotations=ANNOTATIONS_MAP["search-advanced"],
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["incomplete", "completed", "canceled"],
                        "description": "Filter by todo status"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Filter by start date (YYYY-MM-DD)"
                    },
                    "deadline": {
                        "type": "string",
                        "description": "Filter by deadline (YYYY-MM-DD)"
                    },
                    "tag": {
                        "type": "string",
                        "description": "Filter by tag"
                    },
                    "area": {
                        "type": "string",
                        "description": "Filter by area UUID"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["to-do", "project", "heading"],
                        "description": "Filter by item type"
                    }
                },
                "required": [],
            },
        ),

        # Recent items
        types.Tool(
            name="get-recent",
            description="Get recently created items",
            annotations=ANNOTATIONS_MAP["get-recent"],
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period (e.g., '3d', '1w', '2m', '1y')",
                        "pattern": "^\\d+[dwmy]$"
                    }
                },
                "required": ["period"],
            },
        ),

        # Things URL Scheme tools
        types.Tool(
            name="add-todo",
            description="Create a new todo in Things",
            annotations=ANNOTATIONS_MAP["add-todo"],
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the todo"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Notes for the todo"
                    },
                    "when": {
                        "type": "string",
                        "description": "When to schedule the todo (today, tomorrow, evening, anytime, someday, or YYYY-MM-DD)"
                    },
                    "deadline": {
                        "type": "string",
                        "description": "Deadline for the todo (YYYY-MM-DD)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to apply to the todo"
                    },
                    "checklist_items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Checklist items to add"
                    },
                    "list_id": {
                        "type": "string",
                        "description": "ID of project/area to add to"
                    },
                    "list_title": {
                        "type": "string",
                        "description": "Title of project/area to add to"
                    },
                    "heading": {
                        "type": "string",
                        "description": "Heading to add under"
                    }
                },
                "required": ["title"]
            }
        ),

        types.Tool(
            name="add-project",
            description="Create a new project in Things",
            annotations=ANNOTATIONS_MAP["add-project"],
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the project"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Notes for the project"
                    },
                    "when": {
                        "type": "string",
                        "description": "When to schedule the project"
                    },
                    "deadline": {
                        "type": "string",
                        "description": "Deadline for the project"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to apply to the project"
                    },
                    "area_id": {
                        "type": "string",
                        "description": "ID of area to add to"
                    },
                    "area_title": {
                        "type": "string",
                        "description": "Title of area to add to"
                    },
                    "todos": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Initial todos to create in the project"
                    }
                },
                "required": ["title"]
            }
        ),

        types.Tool(
            name="update-todo",
            description="Update an existing todo in Things",
            annotations=ANNOTATIONS_MAP["update-todo"],
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "ID of the todo to update"
                    },
                    "title": {
                        "type": "string",
                        "description": "New title"
                    },
                    "notes": {
                        "type": "string",
                        "description": "New notes"
                    },
                    "when": {
                        "type": "string",
                        "description": "New schedule"
                    },
                    "deadline": {
                        "type": "string",
                        "description": "New deadline"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New tags"
                    },
                    "completed": {
                        "type": "boolean",
                        "description": "Mark as completed"
                    },
                    "canceled": {
                        "type": "boolean",
                        "description": "Mark as canceled"
                    }
                },
                "required": ["id"]
            }
        ),

        types.Tool(
            name="update-project",
            description="Update an existing project in Things",
            annotations=ANNOTATIONS_MAP["update-project"],
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "ID of the project to update"
                    },
                    "title": {
                        "type": "string",
                        "description": "New title"
                    },
                    "notes": {
                        "type": "string",
                        "description": "New notes"
                    },
                    "when": {
                        "type": "string",
                        "description": "New schedule"
                    },
                    "deadline": {
                        "type": "string",
                        "description": "New deadline"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New tags"
                    },
                    "completed": {
                        "type": "boolean",
                        "description": "Mark as completed"
                    },
                    "canceled": {
                        "type": "boolean",
                        "description": "Mark as canceled"
                    }
                },
                "required": ["id"]
            }
        ),

        types.Tool(
            name="search-items",
            description="Search for items in Things",
            annotations=ANNOTATIONS_MAP["search-items"],
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        ),

        types.Tool(
            name="show-item",
            description="Show a specific item or list in Things",
            annotations=ANNOTATIONS_MAP["show-item"],
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "ID of item to show, or one of: inbox, today, upcoming, anytime, someday, logbook"
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional query to filter by"
                    },
                    "filter_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags to filter by"
                    }
                },
                "required": ["id"]
            }
        )
    ]
