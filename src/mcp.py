# src/mcp.py
from typing import Dict, Any
from src.tools import (
    gmail_oauth,
    messaging,
    payments,
    email_tool,
    calendar_tool,
    email_summary,
    orders
)

# ✅ MCP Tool Map
TOOL_MAP = {
    "messaging.send_message": messaging.send_message,
    "email.summarize": email_tool.summarize_unread,
    "calendar.create_event": calendar_tool.create_event,
    "email.summary": email_summary.send_daily_email_summary,
    "orders.place_order": orders.place_order,
}

def run_call(call: Dict[str, Any]):
    """
    Run a single MCP call. Each call dict must have:
      { "tool": "<tool_name>", "args": {...} }
    """
    tool = call.get("tool")
    args = call.get("args", {})
    fn = TOOL_MAP.get(tool)

    if not fn:
        raise Exception(f"❌ Tool '{tool}' not found in TOOL_MAP.")

    print(f"⚙️ MCP executing tool: {tool} with args: {args}")
    return fn(**args)
