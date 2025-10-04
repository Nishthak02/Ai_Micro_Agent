from typing import Dict, Any
from .tools import messaging, payments, email_tool, calendar_tool


TOOL_MAP = {
'messaging.send_message': messaging.send_message,
'payments.generate_upi': payments.generate_upi_link,
'email.summarize': email_tool.summarize_unread,
'calendar.create_event': calendar_tool.create_event,
}




def run_call(call: Dict[str, Any]):
    tool = call.get('tool')
    args = call.get('args', {})
    fn = TOOL_MAP.get(tool)
    if not fn:
        raise Exception(f'Tool {tool} not found')
    return fn(**args)