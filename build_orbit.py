#!/usr/bin/env python3
"""Собирает «Орбиту» — герой-баннер профиля RixAI.

Ядро — система, вокруг по орбитам вращаются агенты: каждый агент = публичный
репозиторий, радиус орбиты и размер точки зависят от его звёзд.

Все цифры берутся из публичного среза GraphQL (privacy: PUBLIC), то есть
ровно то, что видит анонимный посетитель. Запускается из GitHub Actions,
зависимостей нет — только стандартная библиотека.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape

# Логин зашит намеренно: переменные USER/USERNAME конфликтуют с системными
# (на macOS USER = имя пользователя ОС), из-за чего панель однажды собралась
# по чужому аккаунту и показала завышенные цифры.
LOGIN = "morf3uzzz"
TOKEN = os.environ["GITHUB_TOKEN"]
API = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    repositories(
      first: 100
      ownerAffiliations: OWNER
      privacy: PUBLIC
      isFork: false
      orderBy: {field: STARGAZERS, direction: DESC}
    ) {
      totalCount
      nodes { name stargazerCount forkCount primaryLanguage { name } }
    }
  }
}
"""


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "rixai-orbit",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]


def collect(user):
    repos = user["repositories"]["nodes"]
    created = datetime.strptime(user["createdAt"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )

    langs = {}
    for r in repos:
        lang = r["primaryLanguage"]
        if lang:
            langs[lang["name"]] = langs.get(lang["name"], 0) + 1

    return {
        "repos": user["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "forks": sum(r["forkCount"] for r in repos),
        "followers": user["followers"]["totalCount"],
        "days": (datetime.now(timezone.utc) - created).days,
        "top": [r for r in repos if r["stargazerCount"] > 0][:5],
        "langs": sorted(langs.items(), key=lambda kv: -kv[1])[:4],
        "updated": datetime.now(timezone.utc).strftime("%d.%m.%Y"),
    }


THEMES = {
    "dark": {
        "bg": "#0b0f17", "text": "#f8fafc", "dim": "#94a3b8", "faint": "#f8fafc",
        "core_in": "#fff5ec", "core_mid": "#ff8a4c", "core_out": "#c2410c",
        "accent": "#fb923c", "ink": "#2a1206",
        "dots": ["#fb923c", "#38bdf8", "#a78bfa", "#4ade80", "#f472b6"],
    },
    "light": {
        "bg": "#faf8f5", "text": "#141821", "dim": "#6b7280", "faint": "#141821",
        "core_in": "#fff1e4", "core_mid": "#f97316", "core_out": "#9a3412",
        "accent": "#c2410c", "ink": "#fff5ec",
        "dots": ["#ea580c", "#0284c7", "#7c3aed", "#16a34a", "#db2777"],
    },
}

W, H = 860, 380
CX, CY = 240, 190


def orbits(d, c):
    """Орбиты и агенты. Больше звёзд — ближе к ядру и крупнее точка."""
    top = d["top"]
    if not top:
        return "", ""

    rings, agents = [], []
    peak = max(r["stargazerCount"] for r in top) or 1

    for i, repo in enumerate(top):
        radius = 88 + i * 30
        speed = 13 + i * 6.5
        start = (i * 137) % 360
        size = 3.0 + 2.4 * (repo["stargazerCount"] / peak)
        colour = c["dots"][i % len(c["dots"])]
        direction = -1 if i % 2 else 1

        rings.append(
            f'<circle cx="{CX}" cy="{CY}" r="{radius}" fill="none" '
            f'stroke="{c["faint"]}" stroke-opacity="0.10"/>'
        )
        # дуга-трассировка
        rings.append(
            f'<g><animateTransform attributeName="transform" type="rotate" '
            f'from="{start} {CX} {CY}" to="{start + 360 * direction} {CX} {CY}" '
            f'dur="{speed}s" repeatCount="indefinite"/>'
            f'<path d="M{CX + radius},{CY} A{radius},{radius} 0 0 1 '
            f'{CX + radius * 0.71:.1f},{CY + radius * 0.71:.1f}" fill="none" '
            f'stroke="{colour}" stroke-opacity="0.34" stroke-width="1.4" '
            f'stroke-linecap="round"/></g>'
        )
        agents.append(
            f'<g><animateTransform attributeName="transform" type="rotate" '
            f'from="{start} {CX} {CY}" to="{start + 360 * direction} {CX} {CY}" '
            f'dur="{speed}s" repeatCount="indefinite"/>'
            f'<circle cx="{CX + radius}" cy="{CY}" r="{size:.1f}" fill="{colour}">'
            f'<title>{escape(repo["name"])} — {repo["stargazerCount"]}★</title>'
            f'</circle></g>'
        )

    return "".join(rings), "".join(agents)


def render(d, theme):
    c = THEMES[theme]
    serif = "Georgia,'Times New Roman',serif"
    mono = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

    rings, agents = orbits(d, c)
    stack = " · ".join(n for n, _ in d["langs"]) or "Python · JavaScript"

    facts = [
        (f"{d['repos']}", "открытых проекта"),
        (f"{d['stars']}", "звезды собрано"),
        (f"{d['forks']}", "форка сделано"),
    ]
    fact_svg = "".join(
        f'<g transform="translate({i * 104},0)">'
        f'<text x="0" y="0" font-family="{serif}" font-size="27" font-weight="700" '
        f'fill="{c["text"]}">{v}</text>'
        f'<text x="0" y="17" font-family="{mono}" font-size="9.5" fill="{c["dim"]}">'
        f'{label}</text></g>'
        for i, (v, label) in enumerate(facts)
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"
     viewBox="0 0 {W} {H}" role="img"
     aria-label="RixAI — {d['repos']} открытых проектов, {d['stars']} звёзд, {d['days']} дней работы">
  <defs>
    <radialGradient id="core-{theme}" cx="50%" cy="50%">
      <stop offset="0%"   stop-color="{c['core_in']}"/>
      <stop offset="45%"  stop-color="{c['core_mid']}"/>
      <stop offset="100%" stop-color="{c['core_out']}"/>
    </radialGradient>
    <radialGradient id="glow-{theme}" cx="50%" cy="50%">
      <stop offset="0%"   stop-color="{c['core_mid']}" stop-opacity="0.42"/>
      <stop offset="100%" stop-color="{c['core_mid']}" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="{W}" height="{H}" rx="14" fill="{c['bg']}"/>

  <circle cx="{CX}" cy="{CY}" r="168" fill="url(#glow-{theme})"/>
  {rings}
  {agents}

  <circle cx="{CX}" cy="{CY}" r="31" fill="url(#core-{theme})">
    <animate attributeName="r" values="31;33;31" dur="4.6s" repeatCount="indefinite"/>
  </circle>
  <text x="{CX}" y="{CY + 6}" text-anchor="middle" font-family="{serif}"
        font-size="17" font-style="italic" fill="{c['ink']}">Rix</text>

  <g transform="translate(505,104)">
    <text x="0" y="0" font-family="{serif}" font-size="47" fill="{c['text']}"
          letter-spacing="-1.2">RixAI</text>
    <text x="0" y="32" font-family="{serif}" font-size="17" font-style="italic"
          fill="{c['accent']}">системы, которые работают сами</text>

    <line x1="0" y1="58" x2="300" y2="58" stroke="{c['faint']}" stroke-opacity="0.15"/>

    <g font-family="{mono}" font-size="12.5" fill="{c['dim']}">
      <text x="14" y="86">skills для Claude</text>
      <text x="14" y="110">агентные системы</text>
      <text x="14" y="134">сложные автоматизации</text>
    </g>
    <g fill="{c['accent']}">
      <circle cx="3" cy="82" r="2.5"/>
      <circle cx="3" cy="106" r="2.5"/>
      <circle cx="3" cy="130" r="2.5"/>
    </g>

    <g transform="translate(0,180)">{fact_svg}</g>
  </g>

  <text x="28" y="{H - 22}" font-family="{mono}" font-size="10.5" fill="{c['dim']}">
    каждая точка на орбите — живой проект · обновлено {d['updated']}
  </text>
  <text x="{W - 28}" y="{H - 22}" text-anchor="end" font-family="{mono}"
        font-size="10.5" fill="{c['dim']}">{d['days']} дней в работе</text>
</svg>
"""


def verify(data):
    """Сверяет собранные цифры с тем, что отдаёт публичный REST API.

    Если панель разойдётся с реальностью — падаем, а не публикуем враньё.
    """
    req = urllib.request.Request(
        f"https://api.github.com/users/{LOGIN}",
        headers={"User-Agent": "rixai-orbit"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        public = json.load(resp)

    if data["repos"] != public["public_repos"]:
        raise SystemExit(
            f"репозитории разошлись: панель={data['repos']}, "
            f"публичный API={public['public_repos']} — публикация отменена"
        )
    if data["followers"] != public["followers"]:
        raise SystemExit(
            f"подписчики разошлись: панель={data['followers']}, "
            f"публичный API={public['followers']} — публикация отменена"
        )
    print("сверка с публичным API пройдена", file=sys.stderr)


def main():
    data = collect(fetch())
    verify(data)
    print(
        f"repos={data['repos']} stars={data['stars']} forks={data['forks']} "
        f"agents={len(data['top'])}",
        file=sys.stderr,
    )
    for theme in THEMES:
        path = f"orbit-{theme}.svg"
        with open(path, "w", encoding="utf-8") as f:
            f.write(render(data, theme))
        print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
