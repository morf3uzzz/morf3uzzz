#!/usr/bin/env python3
"""Собирает control-panel SVG профиля из живых данных GitHub GraphQL API.

Запускается из GitHub Actions раз в сутки. Токен берётся из GITHUB_TOKEN,
который Actions выдаёт сам — никаких внешних ключей и платных сервисов.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape

USER = os.environ.get("USERNAME", "morf3uzzz")
TOKEN = os.environ["GITHUB_TOKEN"]
API = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes { stargazerCount forkCount primaryLanguage { name } }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount } }
      }
    }
  }
}
"""


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "rixai-control-panel",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]


def collect(user):
    repos = user["repositories"]["nodes"]
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]]

    created = datetime.strptime(user["createdAt"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    uptime = (datetime.now(timezone.utc) - created).days

    langs = {}
    for repo in repos:
        lang = repo["primaryLanguage"]
        if lang:
            langs[lang["name"]] = langs.get(lang["name"], 0) + 1

    return {
        "repos": user["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "forks": sum(r["forkCount"] for r in repos),
        "followers": user["followers"]["totalCount"],
        "commits": user["contributionsCollection"]["totalCommitContributions"],
        "contrib_year": cal["totalContributions"],
        "uptime": uptime,
        "langs": sorted(langs.items(), key=lambda kv: -kv[1]),
        "spark": days[-49:],
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ── палитры ────────────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg": "#0d1117", "panel": "#11161d", "stroke": "#232b36",
        "text": "#e6edf3", "dim": "#7d8590", "accent": "#d97757",
        "ok": "#3fb950", "grid": "#1b222c",
    },
    "light": {
        "bg": "#ffffff", "panel": "#f6f8fa", "stroke": "#d0d7de",
        "text": "#1f2328", "dim": "#59636e", "accent": "#bc4c00",
        "ok": "#1a7f37", "grid": "#eaeef2",
    },
}

W, H = 860, 420


def sparkline(days, x, y, w, h, c):
    """Столбиковый график активности за последние 7 недель."""
    if not days:
        return ""
    peak = max(days) or 1
    step = w / len(days)
    bw = max(step - 1.6, 1.2)
    out = []
    for i, v in enumerate(days):
        bh = max(v / peak * h, 1.0)
        bx = x + i * step
        by = y + h - bh
        op = 0.30 + 0.70 * (v / peak)
        out.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
            f'rx="0.8" fill="{c["accent"]}" opacity="{op:.2f}"/>'
        )
    return "".join(out)


def module(x, y, w, title, value, sub, c, delay):
    """Карточка модуля системы с индикатором и пульсацией."""
    return f"""
  <g transform="translate({x},{y})">
    <rect width="{w}" height="86" rx="8" fill="{c['panel']}" stroke="{c['stroke']}"/>
    <circle cx="18" cy="20" r="3.5" fill="{c['ok']}">
      <animate attributeName="opacity" values="1;0.25;1" dur="2.4s"
               begin="{delay}s" repeatCount="indefinite"/>
    </circle>
    <text x="30" y="24" font-size="10.5" fill="{c['dim']}"
          font-family="ui-monospace,SFMono-Regular,Menlo,monospace"
          letter-spacing="1.4">{escape(title)}</text>
    <text x="18" y="56" font-size="25" font-weight="600" fill="{c['text']}"
          font-family="ui-monospace,SFMono-Regular,Menlo,monospace">{escape(value)}</text>
    <text x="18" y="74" font-size="10.5" fill="{c['dim']}"
          font-family="ui-monospace,SFMono-Regular,Menlo,monospace">{escape(sub)}</text>
  </g>"""


def render(d, theme):
    c = THEMES[theme]
    mono = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

    stack = " · ".join(n for n, _ in d["langs"][:4]) or "Python · JavaScript"

    mods = (
        module(28, 132, 258, "SKILLS", f"{d['repos']}", "репозиториев в системе", c, 0)
        + module(301, 132, 258, "AGENTS", f"{d['commits']}", "коммитов за год", c, 0.8)
        + module(574, 132, 258, "REACH", f"⭐ {d['stars']}", f"{d['forks']} форков · {d['followers']} подписчиков", c, 1.6)
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"
     viewBox="0 0 {W} {H}" font-family="{mono}" role="img"
     aria-label="RixAI control panel — {d['repos']} репозиториев, {d['stars']} звёзд, uptime {d['uptime']} дней">
  <rect width="{W}" height="{H}" rx="12" fill="{c['bg']}"/>
  <rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="11.5" fill="none" stroke="{c['stroke']}"/>

  <!-- заголовок окна -->
  <g transform="translate(28,34)">
    <circle cx="0"  cy="0" r="5" fill="#ff5f57"/>
    <circle cx="18" cy="0" r="5" fill="#febc2e"/>
    <circle cx="36" cy="0" r="5" fill="#28c840"/>
    <text x="60" y="4" font-size="12.5" fill="{c['dim']}">rixai@github ~ control panel</text>
  </g>

  <!-- шапка -->
  <text x="28" y="82" font-size="30" font-weight="700" fill="{c['text']}"
        letter-spacing="-0.4">RixAI</text>
  <g transform="translate(120,72)">
    <rect width="74" height="19" rx="9.5" fill="none" stroke="{c['ok']}" opacity="0.55"/>
    <circle cx="13" cy="9.5" r="3.5" fill="{c['ok']}">
      <animate attributeName="opacity" values="1;0.3;1" dur="1.8s" repeatCount="indefinite"/>
    </circle>
    <text x="24" y="13.5" font-size="10.5" fill="{c['ok']}" letter-spacing="0.9">RUNNING</text>
  </g>
  <text x="28" y="106" font-size="13" fill="{c['dim']}">
    skills для Claude · агентные системы · сложные автоматизации
  </text>

  <!-- модули -->
  {mods}

  <!-- график активности -->
  <g transform="translate(28,248)">
    <text x="0" y="0" font-size="10.5" fill="{c['dim']}" letter-spacing="1.4">ACTIVITY / 7 недель</text>
    <text x="804" y="0" font-size="10.5" fill="{c['dim']}" text-anchor="end">{d['contrib_year']} за год</text>
    <rect x="0" y="10" width="804" height="54" rx="6" fill="{c['panel']}" stroke="{c['stroke']}"/>
    {sparkline(d['spark'], 12, 20, 780, 36, c)}
  </g>

  <!-- нижняя строка -->
  <g transform="translate(28,344)">
    <rect width="804" height="1" fill="{c['grid']}"/>
    <text x="0" y="24" font-size="11.5" fill="{c['dim']}">
      <tspan fill="{c['accent']}">uptime</tspan> {d['uptime']} дней
      <tspan fill="{c['dim']}">   ·   </tspan>
      <tspan fill="{c['accent']}">stack</tspan> {escape(stack)}
    </text>
    <text x="804" y="24" font-size="11.5" fill="{c['dim']}" text-anchor="end">
      обновлено {d['updated']}
    </text>
    <text x="0" y="48" font-size="11.5" fill="{c['dim']}">
      <tspan fill="{c['ok']}">›</tspan> система собрала эту панель сама, без единой правки руками
    </text>
  </g>
</svg>
"""


def main():
    data = collect(fetch())
    for theme in THEMES:
        path = f"panel-{theme}.svg"
        with open(path, "w", encoding="utf-8") as f:
            f.write(render(data, theme))
        print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
