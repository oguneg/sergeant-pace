"""A weaker model sometimes answers in character and CLAIMS it logged the run or stepped the plan back without calling anything.
Seen live: a visitor was told 'I've stepped you back' while the stored history stayed empty. The code must never show that reply."""
import pytest

import agent
import tools
from conftest import onboard
from test_agent_rollback import FakeChat, make_coach


class RecordingChat(FakeChat):
    def __init__(self, script):
        super().__init__(script)
        self.sent = []

    def send_message(self, text):
        self.sent.append(text)
        return super().send_message(text)


def logs_the_run():
    s = tools.load_state()["upcoming"][0]
    agent.traced(tools.log_run)(s["id"], s.get("reps") or s.get("run_min") or 1, 5)


def talks_only():
    pass                                   # an answer with no tool call at all


@pytest.fixture(autouse=True)
def recruit():
    onboard()


def test_a_reply_without_the_required_call_is_not_returned_the_model_is_reminded_once():
    chat = RecordingChat([talks_only, logs_the_run])
    coach = make_coach(chat)
    reply, trace = coach.send("[Run report] ...", require="log_run")
    assert [t["tool"] for t in trace] == ["log_run"] and len(tools.load_state()["history"]) == 1
    assert chat.calls == 2 and "did not call log_run" in chat.sent[1] and chat.sent[0] == "[Run report] ..."


def test_a_second_miss_raises_instead_of_showing_a_false_claim():
    chat = RecordingChat([talks_only, talks_only])
    with pytest.raises(agent.MissingToolCall):
        make_coach(chat).send("[Run report] ...", require="log_run")
    assert chat.calls == 2 and tools.load_state()["history"] == []


def test_calling_some_other_tool_does_not_count():
    chat = RecordingChat([lambda: agent.traced(tools.get_status)(), logs_the_run])
    reply, trace = make_coach(chat).send("[Run report] ...", require="log_run")
    assert chat.calls == 2 and "log_run" in [t["tool"] for t in trace]


def test_half_done_work_from_the_missed_attempt_is_undone():
    """The model called adjust_plan but never logged the run: that plan change must not survive."""
    before = tools.load_state()["upcoming"][0]["level"]
    chat = RecordingChat([lambda: agent.traced(tools.adjust_plan)("step_back", "x"), talks_only])
    with pytest.raises(agent.MissingToolCall):
        make_coach(chat).send("[Run report] ...", require="log_run")
    after = tools.load_state()
    assert after["upcoming"][0]["level"] == before and after["history"] == []


def test_without_a_requirement_there_is_no_reminder():
    chat = RecordingChat([talks_only])
    reply, trace = make_coach(chat).send("how do I tie my shoes?")
    assert chat.calls == 1 and trace == []


def test_a_missing_tool_is_not_mistaken_for_google_being_down():
    assert agent.kind_of(agent.MissingToolCall("log_run")) == "other"
