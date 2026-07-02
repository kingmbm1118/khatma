# 📖 Khatma App — ختمة قرآن صدقة جارية

A shared Quran Khatma website: 30 Juz', each person picks one or more, adds their name, and marks them done. Progress is shared live between all readers with a **persistent database**.

---

## Project structure

```
khatma/
├── app.py                  # the Streamlit app
├── requirements.txt
├── supabase_setup.sql      # run once in Supabase
├── .streamlit/
│   └── config.toml         # theme
└── assets/
    ├── mother.jpg          # ✅ already included
    ├── quran.json          # ✅ full Quran text (Uthmani) — already included
    └── yasin.mp3           # ⬅️ ADD THIS: Surah Yasin (El-Minshawy) mp3
```

## 1) Add the audio

Put your Yasin recitation file in `assets/yasin.mp3` (exact name). The player appears automatically with loop enabled. Keep it under ~100 MB (GitHub file limit) — a 128 kbps mp3 of Yasin is ~20–30 MB, which is fine.

To add more photos later, you can add `st.image(...)` calls or I can extend the app with a photo gallery section.

## 2) Set up the free persistent database (Supabase) — ~3 minutes

Streamlit Cloud's free tier **wipes local files on every restart**, so SQLite alone would lose the data. Supabase gives you a free, permanent Postgres database:

1. Go to <https://supabase.com> → sign up (free) → **New project** (any name, any region, set a DB password).
2. In the project: **SQL Editor → New query** → paste the contents of `supabase_setup.sql` → **Run**.
3. Go to **Project Settings → API** and copy:
   - `Project URL` → this is `SUPABASE_URL`
   - `anon public` key → this is `SUPABASE_KEY`

> Local testing without Supabase works too — the app automatically falls back to a local SQLite file (`khatma.db`).

## 3) Deploy on Streamlit Community Cloud (free)

1. Push this folder to a GitHub repo (public or private).
2. Go to <https://share.streamlit.io> → **New app** → pick the repo → main file: `app.py` → Deploy.
3. In the app's **Settings → Secrets**, paste:

```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "eyJhbGciOi..."
ADMIN_PASSWORD = "choose-a-secret-password"
# MOTHER_NAME is already set in the app to "الحاجة رضا سعد على" — override here only if needed
```

4. Share the app URL with family and friends. Everyone sees the same live board.

## Features

- **Multiple readers per Juz'** — anyone can read any Juz', even one already being read; every reading counts
- **Automatic khatma counting** — completed khatmas = the minimum "done" count across all 30 ajza'. When every Juz' has been read once, khatma 1 completes and khatma 2 starts automatically — no reset needed
- **Milestones** — progress bar with ⅓ / ½ / ⅔ markers and motivational messages as the khatma nears completion
- **Remaining panel** — shows exactly which ajza' still need a reader (⭐), and they appear first in the pick list
- **🏆 Leaderboard** — top readers by completed ajza', with medals, «وفي ذلك فليتنافس المتنافسون»
- **Stats row** — completed khatmas 🌙, current khatma progress, total readings, number of readers
- **Full Quran reading built in** — select any Juz' and read it in Uthmani script directly in the app (bundled, no external API)
- 30 Juz' cards with traditional names (آلم، سيقول، تلك الرسل، ...) showing who is reading and how many times each was completed
- Duplicate guard: the same person can't start the same Juz' twice while still reading it
- Admin sidebar (password-protected): cancel an abandoned reading, or wipe everything
- Surah Yasin background audio with loop; her photo with a du'aa dedication

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

اللهم اجعلها صدقة جارية في ميزان حسناتها 🤲
