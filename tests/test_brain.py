import asyncio
from types import SimpleNamespace as NS

from jarvis import brain, db


class FakeStream:
    def __init__(self, msg):
        self.msg = msg

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    @property
    def text_stream(self):
        async def gen():
            for b in self.msg.content:
                if b.type == "text":
                    yield b.text
        return gen()

    async def get_final_message(self):
        return self.msg


def fake_client(*replies):
    calls = []

    def stream(**kw):
        calls.append(kw)
        return FakeStream(replies[len(calls) - 1])
    return NS(messages=NS(stream=stream)), calls


def test_tool_loop_runs_tool_then_replies(monkeypatch):
    brain.history.clear()
    client, calls = fake_client(
        NS(stop_reason="tool_use", content=[NS(type="tool_use", id="t1", name="add_task", input={"title": "Ring the bank"})]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="Done, sir.")]),
    )
    monkeypatch.setattr(brain, "client", lambda: client)
    tools_seen, deltas = [], []

    async def on_tool(n): tools_seen.append(n)
    async def on_text(t): deltas.append(t)

    assert asyncio.run(brain.reply("remind me to ring the bank", on_text, on_tool)) == "Done, sir."
    assert tools_seen == ["add_task"] and deltas == ["Done, sir."]
    assert db.list_tasks()[0]["title"] == "Ring the bank"
    tool_result = calls[1]["messages"][-1]["content"][0]
    assert tool_result["tool_use_id"] == "t1" and "Added" in tool_result["content"]
    assert [m["role"] for m in brain.history] == ["user", "assistant"]


def test_tool_loop_is_capped(monkeypatch):
    loop_msg = NS(stop_reason="tool_use", content=[NS(type="tool_use", id="t", name="list_tasks", input={})])
    client, calls = fake_client(*[loop_msg] * 20)
    monkeypatch.setattr(brain, "client", lambda: client)
    out = asyncio.run(brain.reply("loop forever"))
    assert len(calls) == brain.MAX_ITERATIONS and "round in circles" in out
