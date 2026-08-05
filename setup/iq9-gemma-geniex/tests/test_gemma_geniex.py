#!/usr/bin/env python3
"""Smoke tests for Gemma (E2B) served by GenieX on the IQ-9075.

Run ON the device (the endpoint is localhost-only by design — DESIGN.md §10):

    python3 test_gemma_geniex.py

Needs the `openai` package (same client the agent will use):

    python3 -m venv ~/qnet-venv && ~/qnet-venv/bin/pip install openai
    ~/qnet-venv/bin/python test_gemma_geniex.py

Exit code 0 = tests 1-3 passed. Test 4 (tool calling) reports but never fails
the run: if it doesn't work, that selects the grammar-constrained fallback
(DESIGN.md §17 O1) rather than blocking setup.
"""

import sys
import time

from openai import OpenAI

BASE_URL = "http://127.0.0.1:18181/v1"
MODEL = "google/gemma-4-E2B-it-qat-q4_0-gguf"

# GenieX field names differ from OpenAI's (schema: GET /docs/swagger.yaml):
# enable_think controls Gemma 4's thinking channel, max_completion_tokens is
# the real token cap (OpenAI's max_tokens is silently ignored). With thinking
# on, replies embed "<|channel>thought ... <channel|>ANSWER" —
# strip_thinking() keeps the tests robust either way.
NO_THINK = {"enable_think": False, "max_completion_tokens": 256}


def strip_thinking(text):
    """Return only the part after the last thinking-channel close marker."""
    marker = "<channel|>"
    return text.rsplit(marker, 1)[-1].strip() if marker in text else text.strip()

client = OpenAI(base_url=BASE_URL, api_key="geniex")  # key unchecked by server


def test_1_list_models():
    models = [m.id for m in client.models.list()]
    print(f"  models: {models}")
    assert any(MODEL in m for m in models), f"{MODEL} not in {models}"


def test_2_chat_completion():
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Reply with exactly: HELLO QNET"}],
        max_tokens=20,
        temperature=0.0,
        extra_body=NO_THINK,
    )
    text = strip_thinking(r.choices[0].message.content)
    print(f"  reply: {text!r}")
    assert len(text) > 0, "empty completion"


def test_3_qnet_shaped_prompt():
    """The fall skill's core judgment (DESIGN.md §7): classify a reply as ok/escalate."""
    cases = [
        ("i'm fine, just dropped a cup", "ok"),
        ("my hip hurts and i can't get up", "escalate"),
        ("", "escalate"),  # silence
    ]
    prompt = (
        "You monitor an elderly person who just fell. Their reply is between "
        "quotes. An empty quote means silence. Answer with one word only: "
        '"ok" if they are clearly fine, "escalate" if they need help or did '
        'not respond.\nReply: "{}"'
    )
    wrong = 0
    for reply, expected in cases:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt.format(reply)}],
            max_tokens=10,
            temperature=0.0,
            extra_body=NO_THINK,
        )
        got = strip_thinking(r.choices[0].message.content).lower()
        ok = expected in got
        wrong += 0 if ok else 1
        print(f"  {reply!r:40} -> {got!r} (want {expected}) {'PASS' if ok else 'FAIL'}")
    assert wrong == 0, f"{wrong}/{len(cases)} classifications wrong"


def test_4_tool_calling():
    """§10: v1 relies on native tool-calling. Reported, not required."""
    tools = [{
        "type": "function",
        "function": {
            "name": "say",
            "description": "Speak a short sentence out loud to the person in the room.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    }]
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": "Use the say tool to greet the person in the room.",
        }],
        tools=tools,
        temperature=0.0,
        # thinking deliberately left ON (that's the realistic agent condition),
        # but capped — uncapped thought chains run for minutes at ~16 tok/s
        extra_body={"max_completion_tokens": 300},
    )
    msg = r.choices[0].message
    if msg.tool_calls:
        tc = msg.tool_calls[0]
        print(f"  tool call: {tc.function.name}({tc.function.arguments})")
        return True
    print(f"  NO tool call; content was: {msg.content!r}")
    return False


def measure_latency(runs=3, gen_tokens=200):
    """TTFT + tok/s — converts DESIGN.md's [?] for QCS9075 into [M]."""
    print(f"\n== latency ({runs} runs, ~{gen_tokens} tokens each) ==")
    for i in range(runs):
        t0 = time.perf_counter()
        ttft = None
        n = 0
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content":
                       "Describe a quiet morning in a kitchen, in detail."}],
            max_tokens=gen_tokens,
            temperature=0.7,
            stream=True,
            extra_body=NO_THINK,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                if ttft is None:
                    ttft = time.perf_counter() - t0
                n += 1
        total = time.perf_counter() - t0
        decode = total - (ttft or 0)
        print(f"  run {i+1}: TTFT {ttft:.2f}s | {n} chunks in {total:.2f}s "
              f"| ~{n/decode:.1f} tok/s decode")


def main():
    failures = 0
    for name, fn in [("1: list models", test_1_list_models),
                     ("2: chat completion", test_2_chat_completion),
                     ("3: QNet-shaped classification", test_3_qnet_shaped_prompt)]:
        print(f"== test {name} ==")
        try:
            fn()
            print("  PASS")
        except Exception as e:
            failures += 1
            print(f"  FAIL: {e}")

    print("== test 4: native tool calling (informational) ==")
    try:
        supported = test_4_tool_calling()
        print(f"  tool calling {'WORKS' if supported else 'NOT WORKING — plan for grammar-constrained fallback (O1)'}")
    except Exception as e:
        print(f"  tool calling errored: {e}")

    if failures == 0:
        measure_latency()
    print(f"\n{'ALL REQUIRED TESTS PASSED' if failures == 0 else f'{failures} REQUIRED TEST(S) FAILED'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
