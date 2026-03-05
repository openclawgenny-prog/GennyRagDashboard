# HEARTBEAT.md

## Morning Greeting
On the first message or heartbeat of each day (after 07:00 local time):
1. Greet: "Hello Master Andrei. Today is {date}"
2. Planned tasks for today (from memory/calendar)
3. Weather today — Den Haag (Open-Meteo)
4. Freezing warning — if any day in next 3 days drops below 2°C → warn about sauna pipes
5. Top 5 world news headlines (yesterday) — fetch via agent-browser
6. Top 5 AI world news headlines (yesterday) — web_search or agent-browser
7. Top 5 OpenClaw tips — sourced from Reddit/YouTube
8. Word of the Day — advanced Dutch word, definition + usage examples (interactive)

Track delivery in memory/heartbeat-state.json key: "morning_greeting_date"
Only deliver once per calendar day.
