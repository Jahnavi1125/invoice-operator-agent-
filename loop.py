import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

import tools

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
MAX_STEPS = 25
LOG = BASE / "logs" / "run_log.jsonl"
APP_URL = "http://127.0.0.1:5000"
REPEAT_LIMIT = 2
READ_ONLY_TOOLS = {"list_files", "read_pdf", "read_text_file"}

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

company_rules = (BASE / "data" / "company_context.md").read_text(encoding="utf-8")

SYSTEM = f"""You are an autonomous AI operator that completes company tasks using tools.
Work step by step: understand the goal, decide the next action, use a tool, observe the result, then adapt.
Never guess values: read them from files or pages. If a step fails, read the error and try a different approach.
Follow these company rules strictly:
{company_rules}
Tools: invoice files are in data/invoices. The company finance system is at {APP_URL} (pages: / and /add).
Use read_page to discover field names and button selectors before filling forms.
Ask the human (ask_human) before any action that the rules say needs approval.
If the task needs something that does not exist (for example there is no invoice from the requested vendor), do not enter anything. Say clearly in your final answer what you searched and what you could not find.
Do not repeat the same read-only tool call with the same arguments, because the result will not change. If you have gathered everything you can, finish with a final answer.
When finished, verify the result by reading the invoice list page, then reply with a short summary and evidence.
"""


def log(entry):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def call_model(contents, config):
    for attempt in range(4):
        try:
            return client.models.generate_content(model=MODEL, contents=contents, config=config)
        except Exception as e:
            msg = str(e)
            if "PerDay" in msg:
                raise RuntimeError(
                    f"Daily quota used up for model {MODEL}. "
                    "Change GEMINI_MODEL or GEMINI_API_KEY in .env."
                )
            if "NOT_FOUND" in msg or "404" in msg:
                raise RuntimeError(
                    f"Model {MODEL} is not available. Run list_models.py and set GEMINI_MODEL in .env."
                )
            wait = 15 * (attempt + 1)
            print(f"Model error: {msg[:120]}... retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError("Model failed after retries")


def run(goal):
    print(f"Starting task with model {MODEL}: {goal}")
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        tools=[types.Tool(function_declarations=tools.TOOL_DECLARATIONS)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    contents = [types.Content(role="user", parts=[types.Part(text=goal)])]
    log({"event": "goal", "goal": goal})
    seen = {}

    for step in range(1, MAX_STEPS + 1):
        resp = call_model(contents, config)
        content = resp.candidates[0].content
        contents.append(content)
        parts = content.parts or []
        calls = [p.function_call for p in parts if p.function_call]

        if not calls:
            final = "".join(p.text or "" for p in parts)
            print("\n=== FINAL ANSWER ===\n" + final)
            log({"event": "final", "text": final})
            return

        response_parts = []
        for call in calls:
            args = dict(call.args) if call.args else {}
            print(f"[step {step}] {call.name} {args}")
            key = (call.name, json.dumps(args, sort_keys=True))
            seen[key] = seen.get(key, 0) + 1
            if call.name in READ_ONLY_TOOLS and seen[key] > REPEAT_LIMIT:
                result = (
                    "NOTE: You already made this exact call and the result will not change. "
                    "Do not repeat it. Use what you already have to finish, or say in your "
                    "final answer what is missing."
                )
                log({"event": "repeat_blocked", "step": step, "tool": call.name, "args": args})
            else:
                try:
                    result = tools.TOOL_FUNCTIONS[call.name](**args)
                except Exception as e:
                    result = f"ERROR: {e}"
            short = str(result)[:300]
            print(f"   -> {short}")
            log({"event": "tool", "step": step, "tool": call.name, "args": args, "result": str(result)[:1500]})
            response_parts.append(types.Part.from_function_response(name=call.name, response={"result": str(result)}))
        contents.append(types.Content(role="user", parts=response_parts))

    print("Stopped: reached the maximum number of steps.")
    log({"event": "stopped", "reason": "max_steps"})


if __name__ == "__main__":
    goal = " ".join(sys.argv[1:]) or "Find the latest invoice from Globex Traders and enter it into the company finance system."
    try:
        run(goal)
    finally:
        tools.close_browser()