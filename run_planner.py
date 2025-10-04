from src.planner import parse_command

if __name__ == "__main__":
    print("💬 Enter a natural language task (type 'exit' to quit):")
    while True:
        cmd = input(">>> ")
        if cmd.lower() == "exit":
            break
        parse_command(cmd)
