"""The agent skill: a valid Agent Skill, in step with the MCP's tools (spec: agent-skill)."""

import asyncio
import re
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2] / "skills" / "wanpire" / "SKILL.md"
LEASE_LIFE = {"wanpire_lease", "wanpire_poll", "wanpire_describe", "wanpire_apply",
              "wanpire_counters", "wanpire_clear", "wanpire_release"}


def front_matter_and_body():
    text = SKILL.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert m, "SKILL.md starts with YAML front matter between --- lines"
    fields = {}
    for line in m.group(1).splitlines():
        if line and not line.startswith((" ", "\t", "#")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"')
    return fields, m.group(2)


def test_front_matter():
    fields, body = front_matter_and_body()
    assert fields["name"] == SKILL.parent.name == "wanpire"
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"]) and len(fields["name"]) <= 64
    d = fields["description"]
    assert 0 < len(d) <= 1024
    assert "link" in d and ("latency" in d or "network" in d)
    assert len(body.splitlines()) < 500


def test_tools_named_exist_and_cover_a_lease():
    pytest.importorskip("mcp")
    import httpx

    from wanpire.mcp_server import make_mcp
    tools = {t.name for t in asyncio.run(make_mcp(httpx.AsyncClient()).list_tools())}
    _, body = front_matter_and_body()
    named = set(re.findall(r"wanpire_[a-z_]+", body))
    assert named <= tools, f"not tools of the MCP: {named - tools}"
    assert LEASE_LIFE <= named, f"not taught: {LEASE_LIFE - named}"


@pytest.mark.parametrize("rule", [
    r"say once",
    r"poll_every_s",
    r"before you (end your turn|stop) to wait for (a person|your user)",
    r"[Nn]ever end another",
    r"/mcp",
    r"wanpire mcp --url",
])
def test_the_rules_are_taught(rule):
    _, body = front_matter_and_body()
    assert re.search(rule, body, re.I), rule
