"""A stand-in for the Claude Code CLI used by ``test_claude_code_llm.py``.

Behavior comes from ``FAKE_CLAUDE_MODE``; every call records its argv, stdin and
whether API credentials leaked into its environment to ``FAKE_CLAUDE_RECORD``.
"""

import json
import os
import sys

args = sys.argv[1:]
mode = os.environ.get("FAKE_CLAUDE_MODE", "text")


def out(event: dict) -> None:
    print(json.dumps(event), flush=True)


if args[:1] == ["--version"]:
    print("2.1.300 (Claude Code)")
    sys.exit(0)
if args[:2] == ["auth", "status"]:
    out({"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "pro", "email": "writer@example.com"})
    sys.exit(0)

stdin = sys.stdin.read()
record = os.environ.get("FAKE_CLAUDE_RECORD")
if record:
    with open(record, "w", encoding="utf-8") as f:
        system = ""
        if "--system-prompt-file" in args:
            with open(args[args.index("--system-prompt-file") + 1], encoding="utf-8") as sf:
                system = sf.read()
        json.dump({"args": args, "stdin": stdin, "system": system, "api_key_seen": "ANTHROPIC_API_KEY" in os.environ}, f)

usage = {"input_tokens": 11, "output_tokens": 7, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 0}
out({"type": "system", "subtype": "init", "model": "fake"})

if mode == "text":
    for chunk in ["Hello ", "from ", "your plan."]:
        out(
            {
                "type": "stream_event",
                "parent_tool_use_id": None,
                "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": chunk}},
            }
        )
    out({"type": "result", "subtype": "success", "is_error": False, "result": "Hello from your plan.", "num_turns": 1, "usage": usage})
elif mode == "structured":
    payload = json.loads(os.environ["FAKE_CLAUDE_PAYLOAD"])
    out(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "",
            "num_turns": 2,
            "usage": usage,
            "structured_output": payload,
        }
    )
elif mode == "limit":
    out({"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "resetsAt": 1793159400, "rateLimitType": "five_hour"}})
    out(
        {
            "type": "result",
            "subtype": "success",
            "is_error": True,
            "api_error_status": 429,
            "result": "Claude usage limit reached.",
            "usage": {},
        }
    )
elif mode == "auth":
    out(
        {
            "type": "result",
            "subtype": "success",
            "is_error": True,
            "api_error_status": None,
            "result": "Not logged in · Please run /login",
            "usage": {},
        }
    )
elif mode == "crash":
    print("boom", file=sys.stderr)
    sys.exit(3)
