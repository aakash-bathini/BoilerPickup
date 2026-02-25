# Boiler Pickup — AI-Powered Pickup Basketball Matchmaking

An AI-powered platform for organizing pickup basketball games at Purdue's France A. Córdova Recreational Sports Center (CoRec) in West Lafayette, Indiana. Built as a grad-level AI project for ECE 570.

## AI Components (Grad-Level)

| Component | Location | Description |
|-----------|----------|-------------|
| **Skill Rating System** | `backend/app/ai/rating.py` | Position-aware, game-type normalized (5v5/3v3/2v2), K-factor decay (one bad game ≈ 8% impact after 25 games), game-type weight (5v5 full, 2v2 slightly less). Bayesian confidence, anti-sandbagging. |
| **Neural Team Balancing** | `backend/app/ai/skill_model.py` | PyTorch 16-dim player embeddings, stat projection, MLP win predictor. Balances teams by minimizing win-probability imbalance. |
| **Matchmaking Algorithm** | `backend/app/ai/matchmaking.py` | **Team balancing at game start** — users join games they want (self-select by skill range); when creator clicks Start, matchmaking splits roster into Team A vs B to minimize imbalance. Exhaustive/sampled splits, greedy fallback. |
| **Win Predictor** | `backend/app/ai/win_predictor.py` | Betting-style Gradient Boosting model. Features: skill, height, PPG/RPG/APG, win rate, experience, position diversity. Shows P(Team A wins) when roster is full. Trains on completed games (20+). |
| **Similar Player Matching** | `backend/app/ai/player_match.py` | `find_matches()` — ML-style weighted Euclidean distance (skill, height, position, games). For 1v1 or similar-level games. |
| **Complementary Teammate Matching** | `backend/app/ai/player_match.py` | `find_complementary_teammates()` — Finds players who complement your stats (scorer + rebounder, guard + big). Position-diversity scoring. |
| **Coach Pete (LLM)** | `backend/app/routers/assistant.py` | Google Gemini with RAG-style context injection. User stats, 1v1 history, all players, Players on Fire, weather (date-aware: "Feb 26", "in 2 days"). Rule-based fallback when no API key. |
| **Synthetic Simulation** | `backend/app/ai/simulate.py` | Synthetic game data for model training and baseline evaluation. |

### How Matchmaking Works (Users Join, We Balance)

- **Users join games** — Games have `skill_min`/`skill_max`. Users self-select into games where their `ai_skill_rating` falls within range. No algorithm assigns users to games.
- **Matchmaking runs at Start** — When the roster is full and the creator clicks "Start", `assign_teams()` runs. It splits the roster into Team A vs Team B to minimize win-probability imbalance (fair teams). Uses PyTorch model when trained, else greedy skill-sort.
- **Why keep it**: Without matchmaking, teams would be random or self-picked (stacked). Matchmaking ensures balanced, competitive games.

### How player_match Works

- **find_matches()**: Similar players (skill, height, position) — for 1v1 or finding opponents.
- **find_complementary_teammates()**: Players who complement your stats — for teaming up.
- Same `ai_skill_rating` source as matchmaking; different purpose (discovery vs balancing).

### Rating System (Less Overreaction)

- **Self-report only for matching** — User selects 1–10 at registration to join first game. Not used in rating formula.
- **First game: opponent's rating as prior** — New user's rating is based purely on performance vs opponent(s). Team: avg opponent rating. 1v1: opponent's rating. No self-report in formula.
- **Higher rating = truly better** — Takes many wins and strong team performance (stats, margins) to climb. K-factor decays with games.
- **1v1 matters more** — Higher K-factor for 1v1 than team games. Same unified skill rating for both.
- First few games have reduced K-factor so one 15-0 win or big loss doesn't overcorrect.

### Data We Track (All Used in AI)

- **Skill**: `ai_skill_rating` (1–10), `skill_confidence`, `SkillHistory` (game-by-game)
- **Stats**: PPG, RPG, APG, SPG, BPG, TOPG, FG%, 3P%, FT% (from `CareerStats` / `PlayerGameStats`)
- **1v1**: Win/loss affects rating (Elo-style with K-factor decay)

---

## Features

### Core Platform
- **User Registration & Profiles** — Purdue email (@purdue.edu) required. Verification code sent before account creation. Track height, weight, position, skill rating, game history, career stats.
- **Game Organization** — Create and join 5v5, 3v3, or 2v2 pickup games at the CoRec with skill-range restrictions. Edit game (date/time) inline from the dashboard without navigating away.
- **AI Team Balancing** — When game starts, matchmaking splits roster into balanced Team A vs B.
- **Win Predictor** — ML model shows which team is favored (skill, height, stats, wins) when roster is full.
- **Stat Tracking** — PTS, REB, AST, STL, BLK, TOV, FGM/FGA, 3PM/3PA, FTM/FTA per game.
- **Leaderboard & Rankings** — Two systems: (1) **Skill Rankings** — best overall, by position, Players on Fire (skill gain past 7 days); (2) **1v1 Head-to-Head** — most 1v1 wins all-time or last 7 days. Skill table shows 1v1 record prominently + team record. 1v1 table shows wins and record. Self-reported rating discarded after first game; rating purely from results.

### Social & Competitive
- **1v1 Challenges** — Accessible from nav ("1v1 Challenges"). Challenge any player via Search (Find Players → Search, not Rankings; search includes players who haven't played yet). Both confirm scores. Affects skill rating.
- **Messaging** — Direct messages and game-specific group chat.
- **Player Search** — Search by name, position, skill range, games, wins, PPG, RPG, APG, FG%.

### AI & Intelligence
- **Coach Pete** — AI assistant (Google Gemini). Find teammates, find similar players, compare to user ("Compare me to @username"), analyze stats, weather (current + forecast by date: "Feb 26", "in 2 days"), Players on Fire. Only available when signed in (uses your data).
- **Live Weather** — Open-Meteo API for West Lafayette. 7-day forecast, current conditions on dashboard.

### Safety & Moderation
- **Report & Block** — Report users; 10 strikes total (reports + management) = account disabled. Blocked users hidden in search/games/messages.
- **Game Management** — No strike when deleting before others join. Delete button hidden after others join; use Propose Reschedule instead (all must approve). Strike when deleting after others joined or when game auto-deletes for no stats within 24h.
- **Stats Contest** — 24h review period. Majority vote resolves disputes.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy, Pydantic v2 |
| Database | SQLite (dev); PostgreSQL via `DATABASE_URL` (prod) |
| AI/ML | PyTorch (team balancing), scikit-learn Gradient Boosting (win predictor), Google Gemini (Coach Pete) |
| Weather | Open-Meteo API (free) |
| Auth | JWT, bcrypt |

---

## Project Structure

```
ECE570_Project/
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   │   ├── skill_model.py    # PyTorch embeddings, win predictor
│   │   │   ├── matchmaking.py    # Team balancing
│   │   │   ├── rating.py         # Position-aware skill rating
│   │   │   ├── player_match.py   # find_matches, find_complementary_teammates
│   │   │   ├── win_predictor.py  # Gradient Boosting win probability
│   │   │   └── simulate.py       # Synthetic data
│   │   ├── routers/
│   │   │   ├── users.py          # Auth, profile, search, leaderboard, match
│   │   │   ├── games.py          # CRUD, join, scorekeeper, contests
│   │   │   ├── stats.py          # Stats, career averages, history
│   │   │   ├── messages.py      # DM, game chat
│   │   │   ├── challenges.py    # 1v1 system
│   │   │   ├── moderation.py    # Report, block
│   │   │   └── assistant.py     # Coach Pete
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── auth.py
│   │   └── database.py
│   ├── scripts/
│   │   └── seed_demo_data.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                  # Pages (dashboard, games, challenges, etc.)
│   │   ├── components/          # Navbar, CoachPete
│   │   └── lib/                  # API, auth, types
│   └── package.json
└── README.md
```

---

## Setup (All Steps)

### Prerequisites

- **Python 3.10+** (for backend)
- **Node.js 18+** and **npm** (for frontend)

---

### Step 1: Backend

```bash
cd backend
pip install -r requirements.txt
```

**Environment:** Copy `backend/.env.example` to `backend/.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | JWT secret. Generate: `openssl rand -hex 32` |
| `GEMINI_API_KEY` | No | Coach Pete LLM (free at https://ai.google.dev). Without it, rule-based fallback. |
| `SMTP_*` | For email | See below for Gmail or Purdue Outlook. |

**Email (optional):**

- **Gmail:** Enable 2FA, create App Password at https://myaccount.google.com/apppasswords. Set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER`, `SMTP_PASSWORD`.
- **Purdue Outlook:** Set `SMTP_HOST=smtp.office365.com`, `SMTP_USER=youralias@purdue.edu`, `SMTP_PASSWORD=...`. Omit `SMTP_FROM` (required for Office365).

**Start backend:**

```bash
python run.py
```

- API: http://localhost:8000  
- Docs: http://localhost:8000/docs  

---

### Step 2: Frontend

In a **new terminal**:

```bash
cd frontend
npm install
npm run dev
```

- App: http://localhost:3000  

**Environment (optional):** Create `frontend/.env.local` if the backend is not on localhost:8000:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

### Step 3: Seed Demo Data (Optional)

With the **backend running**, in another terminal:

```bash
cd backend
python scripts/seed_demo_data.py
```

Creates: 60 users, 30 completed games, 20+ 1v1 challenges, 100+ DM messages, game chat, stats contest, reschedule proposal, skill rating backfill.

**Login:** Any seeded user: `<username>@purdue.edu` / `demo123` (e.g. `alexsmith@purdue.edu` / `demo123`)

---

### Step 4: Train AI Models (Optional)

**Neural team balancing (PyTorch)** — ~2 min:

```bash
cd backend
python -m app.ai.simulate
```

**Win predictor (scikit-learn)** — needs 20+ completed games (seed provides 30). With backend running:

```bash
curl -X POST http://localhost:8000/api/train-predictor
```

> **Note:** Visiting `http://localhost:8000/api/train-predictor` in a browser uses GET and shows instructions. Use `curl -X POST` to actually train.

---

### Step 5: Run Tests

```bash
cd backend
python -m pytest tests/ -v
```

Tests use in-memory SQLite (no disk I/O). Includes AI accuracy tests: 1v1 Elo, position-aware rating, K-factor decay, Bayesian confidence, player-matching distance.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| **Login page reloads, no error shown** | Static assets 404. Run: `cd frontend && rm -rf .next && npm run dev` |
| **Wrong password shows no popup** | Same as above — JS may not load. Clear `.next` and restart. |
| **Train predictor: "Method Not Allowed"** | You used GET (browser). Use: `curl -X POST http://localhost:8000/api/train-predictor` |
| **Train predictor: int_parsing error** | Old path. Use `/api/train-predictor` (not `/api/games/train-predictor`) |
| **Email verification not sending** | Configure SMTP in `backend/.env`. See `.env.example`. |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/register | Register (sends verification code) |
| POST | /api/auth/verify-email | Verify code, create account |
| POST | /api/auth/resend-code | Resend verification code |
| POST | /api/auth/login | Login |
| GET | /api/users/me | Current user |
| PUT | /api/users/me | Update profile |
| GET | /api/users/search | Search (position, skill, games, PPG, etc.) |
| GET | /api/users/leaderboard | Skill rankings (sort: overall, position, hot_week) |
| GET | /api/users/leaderboard-1v1 | 1v1 rankings (sort: wins_total, wins_week) |
| GET | /api/users/{id} | Get user profile |
| GET | /api/users/{id}/challenges-history | Completed 1v1 challenges |
| GET | /api/users/match | ML similar players |
| GET | /api/users/compare/{id} | Win probability vs that user (1v1) |
| GET | /api/users/{id}/stats | Career stats |
| GET | /api/users/{id}/stats/by-game-type | Career averages by 5v5, 3v3, 2v2 |
| GET | /api/users/{id}/skill-history | Skill rating progression (for charts) |
| GET | /api/users/{id}/stats/history | Game-by-game stats + skill |
| POST | /api/games | Create game |
| GET | /api/games | List games |
| GET | /api/games/{id} | Get game |
| PATCH | /api/games/{id} | Update game |
| DELETE | /api/games/{id} | Delete game |
| POST | /api/games/{id}/join | Join game |
| POST | /api/games/{id}/leave | Leave game |
| POST | /api/games/{id}/start | Start (AI team balancing) |
| POST | /api/games/{id}/complete | Complete game, submit scores |
| POST | /api/games/{id}/stats | Submit player stats (stats router) |
| POST | /api/games/{id}/invite-scorekeeper | Invite scorekeeper |
| POST | /api/games/{id}/accept-scorekeeper | Accept scorekeeper invite |
| POST | /api/games/{id}/contest | Contest stats |
| POST | /api/games/{id}/contest/{id}/vote | Vote on contest |
| POST | /api/games/{id}/reschedule | Propose reschedule |
| POST | /api/games/{id}/reschedule/{id}/vote | Vote on reschedule |
| POST | /api/train-predictor | Train win predictor (20+ games) |
| POST | /api/challenges | Create 1v1 challenge |
| GET | /api/challenges | List challenges |
| POST | /api/challenges/{id}/accept | Accept challenge |
| POST | /api/challenges/{id}/decline | Decline challenge |
| POST | /api/challenges/{id}/submit-score | Submit score |
| POST | /api/challenges/{id}/confirm | Confirm score |
| POST | /api/messages | Send message |
| GET | /api/messages/conversations | List DM conversations |
| GET | /api/messages/dm/{id} | Get DM thread |
| GET | /api/messages/game/{id} | Get game chat |
| POST | /api/chat | Coach Pete |
| GET | /api/weather | West Lafayette weather |
| POST | /api/report | Report user |
| POST | /api/block/{id} | Block user |
| DELETE | /api/block/{id} | Unblock user |

---

## Design

- **Theme**: Purdue Old Gold (#CFB991) on dark (#0A0A0A)
- **Typography**: Inter
- **Components**: Glassmorphism, gradient accents, smooth transitions
- **Responsive**: Mobile-first

---

## Attribution

ECE 570 (AI) — Purdue University. France A. Córdova Recreational Sports Center, West Lafayette, IN.
