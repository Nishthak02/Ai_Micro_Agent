import argparse
import json
from src.db import init_db, create_user, create_task, list_tasks

def main():
    parser = argparse.ArgumentParser(description="Admin CLI for AI Micro Agent")
    subparsers = parser.add_subparsers(dest="command")

    # --- create-user command ---
    p_user = subparsers.add_parser("create-user")
    p_user.add_argument("--name", required=True)
    p_user.add_argument("--chat_id", required=True)

    # --- create-task command ---
    p_task = subparsers.add_parser("create-task")
    p_task.add_argument("--user_id", required=True, type=int)
    p_task.add_argument("--type", required=True, choices=["reminder", "bill_link", "email_summary"])
    p_task.add_argument("--text", required=True)

    # --- list-tasks command ---
    subparsers.add_parser("list-tasks")

    args = parser.parse_args()
    init_db()

    if args.command == "create-user":
        uid = create_user(args.name, args.chat_id)
        print(f"✅ Created user {args.name} with id={uid}")

    elif args.command == "create-task":
        plan = {
            "plan": args.type,
            "calls": [
                {"tool": "messaging.send_message", "args": {"chat_id": args.user_id, "text": args.text}}
            ]
        }
        tid = create_task(args.user_id, args.type, plan, "*", 1)
        print(f"✅ Created task id={tid}")

    elif args.command == "list-tasks":
        rows = list_tasks()
        print("📋 Tasks:")
        for r in rows:
            print(r)

if __name__ == "__main__":
    main()
