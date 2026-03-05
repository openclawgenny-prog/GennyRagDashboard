# MEMORY.md — Long-term Memory

## User
- **Name:** Andrei (MrGreen / mrGreenCat)
- **Telegram:** @mrGreenCat, chat_id: 191406357
- **Timezone:** Europe/Amsterdam (GMT+1)
- **Location:** Den Haag, Netherlands

## Infrastructure
- **Host:** andrei-Venus-series (192.168.178.53), Linux 6.17
- **Portainer:** http://127.0.0.1:9000, API Key: ptr_KIihZqMjydnFofN4j/ypFBa8di1xT9JnXiL4gkQy0R4=, Endpoint ID: 3
- **Ollama:** running on bridge network (172.17.0.2:11434), model: all-minilm:latest
- **Postgres/pgvector:** container postgres-pgvector-db-1, network: postgres-pgvector_default, db: vectordb, user: andrei
- **Haystack:** stack ID=50, image deepset/haystack:base-v2.12.1, port 8000, pipeline at haystack_app volume, connects to postgres + ollama
- **AgentMail:** inbox openclawgenny@agentmail.to (Genny), API key in ~/.openclaw/workspace/.env
- **Telegram bot:** token 8156733398:AAFe9biccx6Ye_ZskwC4q3RZ4tVokJVINIU, bot @OC_Genny_bot

## Skills installed
- agent-browser (0.16.3) — headless Chromium, ~/.openclaw/skills/agent-browser/
- agentmail (0.2.23) — email send/receive, ~/.openclaw/skills/agentmail/

## Behaviors & Preferences
### Morning Greeting (first message of the day)
On the first message each morning, greet with:
1. "Hello Master Andrei. Today is {date}"
2. Planned tasks for today (from calendar / memory)
3. Weather for today (Den Haag) — use Open-Meteo or agent-browser
4. Freezing temperature warning — if <2°C coming in next 3 days, warn about sauna pipes
5. Top 5 world news headlines (from yesterday) — use agent-browser
6. Top 5 AI news headlines (from yesterday) — use agent-browser or web_search
7. Top 5 OpenClaw tips — sourced from Reddit discussions and/or YouTube videos
8. "Word of the Day" — advanced Dutch word: definition + usage examples (interactive)

Track whether morning greeting was delivered today in memory/heartbeat-state.json.

## Notes
- Andrei has a sauna with pipes that can freeze — warn if temps drop below ~2°C
- Disk usage at 89% (67/79 GB) as of 2026-03-04 — needs cleanup
