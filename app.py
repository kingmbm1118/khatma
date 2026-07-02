# -*- coding: utf-8 -*-
"""
ختمة قرآن — صدقة جارية على روح الحاجة رضا سعد على
يسمح بتعدد القرّاء للجزء الواحد، وعدّ الختمات تلقائيًا، مع لوحة شرف ومراحل إنجاز.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
APP_DIR = Path(__file__).parent
ASSETS = APP_DIR / "assets"
MOTHER_IMG = ASSETS / "mother.jpg"
YASIN_MP3 = ASSETS / "yasin.mp3"


def get_secret(key, default=""):
    """st.secrets.get raises if no secrets.toml exists at all — make it safe."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


MOTHER_NAME = get_secret("MOTHER_NAME", "أمي")
ADMIN_PASSWORD = get_secret("ADMIN_PASSWORD", "")

JUZ_NAMES = [
    "آلم", "سيقول", "تلك الرسل", "لن تنالوا", "والمحصنات",
    "لا يحب الله", "وإذا سمعوا", "ولو أننا", "قال الملأ", "واعلموا",
    "يعتذرون", "وما من دابة", "وما أبرئ", "ربما", "سبحان الذي",
    "قال ألم", "اقترب للناس", "قد أفلح", "وقال الذين", "أمن خلق",
    "اتل ما أوحي", "ومن يقنت", "وما لي", "فمن أظلم", "إليه يرد",
    "حم", "قال فما خطبكم", "قد سمع الله", "تبارك الذي", "عم",
]

# Madina mushaf (Hafs) juz boundaries: (start_surah, start_ayah, end_surah, end_ayah)
JUZ_RANGES = [
    (1, 1, 2, 141), (2, 142, 2, 252), (2, 253, 3, 92), (3, 93, 4, 23), (4, 24, 4, 147),
    (4, 148, 5, 81), (5, 82, 6, 110), (6, 111, 7, 87), (7, 88, 8, 40), (8, 41, 9, 92),
    (9, 93, 11, 5), (11, 6, 12, 52), (12, 53, 14, 52), (15, 1, 16, 128), (17, 1, 18, 74),
    (18, 75, 20, 135), (21, 1, 22, 78), (23, 1, 25, 20), (25, 21, 27, 55), (27, 56, 29, 45),
    (29, 46, 33, 30), (33, 31, 36, 27), (36, 28, 39, 31), (39, 32, 41, 46), (41, 47, 45, 37),
    (46, 1, 51, 30), (51, 31, 57, 29), (58, 1, 66, 12), (67, 1, 77, 50), (78, 1, 114, 6),
]

_AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

ORDINALS_F = ["الأولى", "الثانية", "الثالثة", "الرابعة", "الخامسة",
              "السادسة", "السابعة", "الثامنة", "التاسعة", "العاشرة"]


def ar_num(n):
    return str(n).translate(_AR_DIGITS)


def khatma_ordinal(n):
    return ORDINALS_F[n - 1] if 1 <= n <= 10 else f"رقم {ar_num(n)}"


st.set_page_config(
    page_title=f"ختمة على روح {MOTHER_NAME}",
    page_icon="📖",
    layout="wide",
)

# ----------------------------------------------------------------------------
# Storage layer — readings log (many readers per juz)
# Supabase (persistent, for Streamlit Cloud) or SQLite (local testing)
# ----------------------------------------------------------------------------
USING_SUPABASE = bool(get_secret("SUPABASE_URL"))


def _supabase_client():
    from supabase import create_client
    return create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))


def _sqlite_conn():
    conn = sqlite3.connect(APP_DIR / "khatma.db")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            juz INTEGER NOT NULL,
            reader_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'reading',
            created_at TEXT,
            updated_at TEXT
        )"""
    )
    conn.commit()
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat()


@st.cache_data(ttl=5, show_spinner=False)
def load_readings():
    """Return list of {'id', 'juz', 'reader_name', 'status'}."""
    if USING_SUPABASE:
        sb = _supabase_client()
        return sb.table("readings").select("id, juz, reader_name, status").execute().data
    conn = _sqlite_conn()
    rows = conn.execute("SELECT id, juz, reader_name, status FROM readings").fetchall()
    conn.close()
    return [{"id": r[0], "juz": r[1], "reader_name": r[2], "status": r[3]} for r in rows]


def add_readings(juz_list, name):
    """Start readings. Skips ajza' this same person is already actively reading."""
    active_same = {
        r["juz"] for r in load_readings()
        if r["reader_name"] == name and r["status"] == "reading"
    }
    new = [j for j in juz_list if j not in active_same]
    skipped = [j for j in juz_list if j in active_same]
    if new:
        rows = [
            {"juz": j, "reader_name": name, "status": "reading",
             "created_at": _now(), "updated_at": _now()}
            for j in new
        ]
        if USING_SUPABASE:
            _supabase_client().table("readings").insert(rows).execute()
        else:
            conn = _sqlite_conn()
            conn.executemany(
                "INSERT INTO readings (juz, reader_name, status, created_at, updated_at) "
                "VALUES (:juz, :reader_name, :status, :created_at, :updated_at)",
                rows,
            )
            conn.commit()
            conn.close()
    load_readings.clear()
    return new, skipped


def mark_done(reading_ids):
    if USING_SUPABASE:
        sb = _supabase_client()
        for rid in reading_ids:
            sb.table("readings").update({"status": "done", "updated_at": _now()}).eq("id", rid).execute()
    else:
        conn = _sqlite_conn()
        conn.executemany(
            "UPDATE readings SET status='done', updated_at=? WHERE id=?",
            [(_now(), rid) for rid in reading_ids],
        )
        conn.commit()
        conn.close()
    load_readings.clear()


def delete_readings(reading_ids):
    if USING_SUPABASE:
        sb = _supabase_client()
        for rid in reading_ids:
            sb.table("readings").delete().eq("id", rid).execute()
    else:
        conn = _sqlite_conn()
        conn.executemany("DELETE FROM readings WHERE id=?", [(rid,) for rid in reading_ids])
        conn.commit()
        conn.close()
    load_readings.clear()


def reset_all():
    if USING_SUPABASE:
        _supabase_client().table("readings").delete().gte("juz", 1).execute()
    else:
        conn = _sqlite_conn()
        conn.execute("DELETE FROM readings")
        conn.commit()
        conn.close()
    load_readings.clear()


# ----------------------------------------------------------------------------
# Quran text (bundled locally: assets/quran.json — Uthmani script)
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_quran():
    import json
    with open(ASSETS / "quran.json", encoding="utf-8") as f:
        return json.load(f)


BASMALA = "بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ"


@st.cache_data(show_spinner=False)
def render_juz_html(juz_no: int) -> str:
    quran = load_quran()
    s1, a1, s2, a2 = JUZ_RANGES[juz_no - 1]
    parts = []
    for s in range(s1, s2 + 1):
        surah = quran[s - 1]
        start = a1 if s == s1 else 1
        end = a2 if s == s2 else surah["total_verses"]
        if start == 1:
            parts.append(f'<div class="surah-header">سُورَةُ {surah["name"]}</div>')
            if s not in (1, 9):  # Al-Fatiha's basmala is verse 1; At-Tawbah has none
                parts.append(f'<div class="basmala">{BASMALA}</div>')
        else:
            parts.append(
                f'<div class="surah-header cont">تكملة سُورَةِ {surah["name"]} — من الآية {ar_num(start)}</div>'
            )
        ayat = [
            f'{v["text"]} <span class="aya-num">﴿{ar_num(v["id"])}﴾</span>'
            for v in surah["verses"][start - 1 : end]
        ]
        parts.append(f'<div class="quran-text">{" ".join(ayat)}</div>')
    return "".join(parts)


# ----------------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Amiri+Quran&family=Cairo:wght@400;600;700&display=swap');

html, body, [class*="css"] { direction: rtl; }
.stApp {
    background: linear-gradient(180deg, #0d2b23 0%, #123a2f 55%, #0d2b23 100%);
    font-family: 'Cairo', sans-serif;
}
h1, h2, h3, .amiri { font-family: 'Amiri', serif !important; }

.hero { text-align: center; padding: 1.4rem 1rem 0.6rem 1rem; color: #f4ecd6; }
.hero .bismillah { font-family:'Amiri',serif; font-size: 2.0rem; color: #d9b64a; margin-bottom: 0.4rem; }
.hero .title { font-family:'Amiri',serif; font-size: 2.4rem; font-weight: 700; color: #f4ecd6; }
.hero .dua {
    font-family:'Amiri',serif; font-size: 1.25rem; color: #cfe3d6;
    max-width: 720px; margin: 0.6rem auto 0 auto; line-height: 2.1;
}
.photo-frame img {
    border-radius: 50%; border: 4px solid #d9b64a;
    box-shadow: 0 0 40px rgba(217,182,74,0.35);
}

/* ---------- stats row ---------- */
.stat-row { display:flex; gap:12px; flex-wrap:wrap; justify-content:center; margin-top:8px; }
.stat-box {
    background: rgba(244,236,214,0.06); border: 1px solid rgba(217,182,74,0.45);
    border-radius: 14px; padding: 10px 22px; text-align:center; color:#f4ecd6;
    min-width: 130px;
}
.stat-box .big { font-family:'Amiri',serif; font-size: 1.9rem; color:#d9b64a; font-weight:700; }
.stat-box .lbl { font-size: 0.85rem; opacity: 0.9; }

/* ---------- milestones ---------- */
.milestone-track { display:flex; gap:8px; justify-content:center; flex-wrap:wrap; margin: 10px 0 4px 0; }
.milestone {
    border-radius: 999px; padding: 5px 16px; font-size: 0.9rem; font-weight: 600;
    border: 1.5px solid rgba(217,182,74,0.5); color: #d9c99a; background: rgba(244,236,214,0.05);
}
.milestone.hit { background: linear-gradient(160deg,#d9b64a,#b9932f); color: #1d2a17; border-color:#f0d98a; }

.remaining-panel {
    background: rgba(217,182,74,0.08); border: 1.5px dashed rgba(217,182,74,0.6);
    border-radius: 14px; padding: 12px 16px; margin-top: 10px; text-align:center;
}
.remaining-panel .head { font-family:'Amiri',serif; color:#f0d98a; font-size:1.2rem; margin-bottom:6px; }
.chip {
    display:inline-block; margin: 3px; padding: 4px 12px; border-radius: 999px;
    background: rgba(244,236,214,0.08); border: 1px solid #d9b64a; color: #f4ecd6; font-size: 0.88rem;
}

/* ---------- juz grid ---------- */
.juz-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(158px, 1fr));
    gap: 12px; direction: rtl; margin-top: 0.5rem;
}
.juz-card {
    border-radius: 14px; padding: 12px 10px; text-align: center; min-height: 122px;
    display: flex; flex-direction: column; justify-content: center;
}
.juz-card .num { font-family:'Amiri',serif; font-size: 1.15rem; font-weight: 700; }
.juz-card .jname { font-family:'Amiri',serif; font-size: 0.95rem; opacity: 0.85; margin-top: 2px;}
.juz-card .reader { font-size: 0.82rem; margin-top: 6px; font-weight: 600; }
.juz-card .badge { font-size: 0.74rem; margin-top: 4px; }
.juz-needs { background: rgba(244,236,214,0.07); border: 1.5px dashed rgba(217,182,74,0.65); color: #f0d98a; }
.juz-reading { background: rgba(217,182,74,0.12); border: 1.5px solid #d9b64a; color: #f4ecd6; }
.juz-done { background: linear-gradient(160deg, #d9b64a, #b9932f); border: 1.5px solid #f0d98a; color: #1d2a17; }

/* ---------- leaderboard ---------- */
.board { margin-top: 8px; }
.board-row {
    display:flex; align-items:center; gap:12px;
    background: rgba(244,236,214,0.06); border: 1px solid rgba(217,182,74,0.35);
    border-radius: 12px; padding: 8px 16px; margin-bottom: 6px; color:#f4ecd6;
}
.board-row .rank { font-size: 1.2rem; width: 2rem; text-align:center; }
.board-row .bname { font-weight: 700; flex-grow: 1; }
.board-row .score { font-family:'Amiri',serif; color:#d9b64a; font-weight:700; }
.board-row.top1 { border-color:#f0d98a; background: rgba(217,182,74,0.16); }

.section-title {
    font-family:'Amiri',serif; color: #d9b64a; font-size: 1.5rem;
    border-bottom: 1px solid rgba(217,182,74,0.35); padding-bottom: 6px; margin-top: 1.4rem;
}
div.stButton > button, div.stFormSubmitButton > button {
    background: #d9b64a; color: #14301f; font-weight: 700; border: none; border-radius: 10px;
}
div.stButton > button:hover, div.stFormSubmitButton > button:hover { background: #e8ca6a; color:#14301f; }
.stProgress > div > div > div > div { background-color: #d9b64a; }
footer, #MainMenu { visibility: hidden; }

/* ---------- Quran reading panel ---------- */
.mushaf {
    background: #f9f4e3; border: 2px solid #d9b64a; border-radius: 18px;
    padding: 28px 30px; margin-top: 10px;
    box-shadow: inset 0 0 60px rgba(185,147,47,0.15), 0 6px 24px rgba(0,0,0,0.35);
    max-height: 75vh; overflow-y: auto; direction: rtl;
}
.surah-header {
    font-family:'Amiri',serif; text-align:center; color:#7a5c12;
    background: linear-gradient(90deg, transparent, rgba(217,182,74,0.30), transparent);
    border-top: 1px solid #c9a94f; border-bottom: 1px solid #c9a94f;
    font-size: 1.6rem; font-weight: 700; padding: 8px 0; margin: 20px 0 6px 0;
}
.surah-header.cont { font-size: 1.15rem; opacity: 0.85; }
.basmala { font-family:'Amiri Quran','Amiri',serif; text-align:center; color:#3a2e10; font-size:1.7rem; margin: 8px 0 12px 0; }
.quran-text { font-family:'Amiri Quran','Amiri',serif; color:#26200e; font-size:1.75rem; line-height:2.7; text-align:justify; }
.aya-num { color: #a9821f; font-size: 1.25rem; }
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Header: photo + dedication
# ----------------------------------------------------------------------------
st.markdown('<div class="hero"><div class="bismillah">﷽</div></div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 1, 1])
with c2:
    if MOTHER_IMG.exists():
        st.markdown('<div class="photo-frame" style="text-align:center;">', unsafe_allow_html=True)
        st.image(str(MOTHER_IMG), width=230)
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    f"""
<div class="hero">
  <div class="title">ختمة قرآن على روح {MOTHER_NAME}</div>
  <div class="dua">
    اللهم اغفر لها وارحمها، وعافها واعفُ عنها، وأكرم نُزلها، ووسّع مُدخلها،
    واجعل قبرها روضةً من رياض الجنة، واجعل كل حرفٍ يُقرأ في هذه الختمة نورًا لها ورحمة
    <br>«وَقُل رَّبِّ ارْحَمْهُمَا كَمَا رَبَّيَانِي صَغِيرًا»
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Yasin audio
# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# Yasin — hidden background audio, plays once on page load
# (served via Streamlit static serving so the page stays lightweight)
# ----------------------------------------------------------------------------
def _ensure_static_audio():
    static_dst = APP_DIR / "static" / "yasin.mp3"
    if static_dst.exists():
        return True
    if YASIN_MP3.exists():
        static_dst.parent.mkdir(exist_ok=True)
        import shutil
        shutil.copy(YASIN_MP3, static_dst)
        return True
    return False


if _ensure_static_audio():
    st.markdown(
        '<audio autoplay preload="auto" src="./app/static/yasin.mp3" style="display:none"></audio>',
        unsafe_allow_html=True,
    )

# ----------------------------------------------------------------------------
# Compute state from readings log
# ----------------------------------------------------------------------------
readings = load_readings()
done_counts = {j: 0 for j in range(1, 31)}
active_by_juz = {j: [] for j in range(1, 31)}          # names currently reading
done_names_by_juz = {j: [] for j in range(1, 31)}
active_rows = []                                        # readings with status='reading'
scores = {}                                             # reader -> done count

for r in readings:
    j = int(r["juz"])
    if r["status"] == "done":
        done_counts[j] += 1
        done_names_by_juz[j].append(r["reader_name"])
        scores[r["reader_name"]] = scores.get(r["reader_name"], 0) + 1
    else:
        active_by_juz[j].append(r["reader_name"])
        active_rows.append(r)

completed_khatmas = min(done_counts.values())           # full khatmas finished
current_no = completed_khatmas + 1                      # the khatma in progress
covered = {j for j in range(1, 31) if done_counts[j] >= current_no}
remaining = [j for j in range(1, 31) if j not in covered]
progress = len(covered)
total_done_readings = sum(done_counts.values())
readers_count = len({r["reader_name"] for r in readings})

# ----------------------------------------------------------------------------
# Progress, milestones, remaining
# ----------------------------------------------------------------------------
st.markdown(f'<div class="section-title">📿 الختمة {khatma_ordinal(current_no)} — تقدّمنا معًا</div>', unsafe_allow_html=True)

st.markdown(
    f"""
<div class="stat-row">
  <div class="stat-box"><div class="big">{ar_num(completed_khatmas)}</div><div class="lbl">ختمات مكتملة 🌙</div></div>
  <div class="stat-box"><div class="big">{ar_num(progress)} / ٣٠</div><div class="lbl">أجزاء الختمة الحالية</div></div>
  <div class="stat-box"><div class="big">{ar_num(total_done_readings)}</div><div class="lbl">إجمالي الأجزاء المقروءة</div></div>
  <div class="stat-box"><div class="big">{ar_num(readers_count)}</div><div class="lbl">عدد القرّاء 🤲</div></div>
</div>
""",
    unsafe_allow_html=True,
)

st.progress(progress / 30)

MILESTONES = [(5, "٥ أجزاء"), (10, "ثلث الختمة"), (15, "نصف الختمة"), (20, "ثلثا الختمة"), (25, "٢٥ جزءًا"), (30, "ختمة كاملة 🌙")]
ms_html = "".join(
    f'<span class="milestone {"hit" if progress >= v else ""}">{"✓ " if progress >= v else ""}{lbl}</span>'
    for v, lbl in MILESTONES
)
st.markdown(f'<div class="milestone-track">{ms_html}</div>', unsafe_allow_html=True)

if progress == 30:
    st.balloons()
    st.success(f"🌙 اكتملت الختمة {khatma_ordinal(current_no)} بفضل الله — تقبّل الله منا ومنكم! الختمة {khatma_ordinal(current_no + 1)} تبدأ الآن، فلا تتوقفوا 🤲")
elif remaining:
    if len(remaining) <= 5:
        head = f"🔥 اقتربنا جدًا! لم يبقَ سوى {ar_num(len(remaining))} — من يكسب شرف إتمام الختمة؟"
    elif len(remaining) <= 15:
        head = f"💪 قطعنا أكثر من النصف — بقي {ar_num(len(remaining))} جزءًا فقط لإتمام الختمة {khatma_ordinal(current_no)}"
    else:
        head = f"الأجزاء المتبقية لإتمام الختمة {khatma_ordinal(current_no)}: {ar_num(len(remaining))} جزءًا — اختر منها جزءك"
    chips = "".join(f'<span class="chip">الجزء {ar_num(j)} — {JUZ_NAMES[j-1]}</span>' for j in remaining)
    st.markdown(f'<div class="remaining-panel"><div class="head">{head}</div>{chips}</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Juz grid
# ----------------------------------------------------------------------------
st.markdown('<div class="section-title">📖 الأجزاء الثلاثون</div>', unsafe_allow_html=True)
st.markdown(
    '<div style="color:#cfe3d6;font-size:0.95rem;">يمكن لأكثر من قارئ قراءة الجزء نفسه — كل قراءة تُحسب في الختمات القادمة بإذن الله</div>',
    unsafe_allow_html=True,
)


def names_snippet(names, limit=2):
    if not names:
        return ""
    shown = "، ".join(names[:limit])
    extra = len(names) - limit
    return shown + (f" +{ar_num(extra)}" if extra > 0 else "")


cards = []
for j in range(1, 31):
    n_active = len(active_by_juz[j])
    n_done = done_counts[j]
    if j in covered:
        cls = "juz-done"
        badge = f"✓ تمّت {ar_num(n_done)} مرة" if n_done > 1 else "✓ تمّت القراءة"
        reader = names_snippet(done_names_by_juz[j])
    elif n_active > 0:
        cls = "juz-reading"
        badge = f"⏳ يقرؤه الآن {ar_num(n_active)}" if n_active > 1 else "⏳ جارٍ القراءة"
        reader = names_snippet(active_by_juz[j])
    else:
        cls, badge, reader = "juz-needs", "⭐ يحتاج قارئًا", ""
    cards.append(
        f'<div class="juz-card {cls}">'
        f'<div class="num">الجزء {ar_num(j)}</div>'
        f'<div class="jname">{JUZ_NAMES[j-1]}</div>'
        f'<div class="reader">{reader}</div>'
        f'<div class="badge">{badge}</div>'
        f"</div>"
    )
st.markdown(f'<div class="juz-grid">{"".join(cards)}</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Actions
# ----------------------------------------------------------------------------
col_a, col_b = st.columns(2)


def juz_pick_label(j):
    tags = []
    if j in remaining and not active_by_juz[j]:
        tags.append("⭐ يحتاج قارئًا")
    elif active_by_juz[j]:
        tags.append(f"يقرؤه {ar_num(len(active_by_juz[j]))}")
    return f"الجزء {ar_num(j)} — {JUZ_NAMES[j-1]}" + (f"  ({'، '.join(tags)})" if tags else "")


# needy ajza' first, to encourage completing the khatma
pick_order = sorted(range(1, 31), key=lambda j: (j not in remaining, len(active_by_juz[j]) > 0, j))

with col_a:
    st.markdown('<div class="section-title">✍️ ابدأ قراءة جزء</div>', unsafe_allow_html=True)
    with st.form("reserve_form", clear_on_submit=True):
        name = st.text_input("اسمك", placeholder="اكتب اسمك هنا")
        chosen = st.multiselect(
            "اختر جزءًا أو أكثر — الأجزاء التي تحتاج قارئًا تظهر أولًا ⭐",
            options=pick_order,
            format_func=juz_pick_label,
        )
        submitted = st.form_submit_button("ابدأ القراءة 🤲")
    if submitted:
        if not name.strip():
            st.warning("من فضلك اكتب اسمك أولًا")
        elif not chosen:
            st.warning("اختر جزءًا واحدًا على الأقل")
        else:
            new, skipped = add_readings(chosen, name.strip())
            if new:
                st.success(f"تقبّل الله منك يا {name.strip()} — بدأتَ قراءة: {'، '.join('الجزء ' + ar_num(x) for x in new)}")
            if skipped:
                st.info(f"أنت تقرأ بالفعل: {'، '.join('الجزء ' + ar_num(x) for x in skipped)}")
            st.rerun()

with col_b:
    st.markdown('<div class="section-title">✅ أتممتَ القراءة؟</div>', unsafe_allow_html=True)
    with st.form("done_form", clear_on_submit=True):
        finished = st.multiselect(
            "اختر قراءاتك التي أنهيتها",
            options=[r["id"] for r in active_rows],
            format_func=lambda rid: next(
                f"الجزء {ar_num(r['juz'])} — {r['reader_name']}" for r in active_rows if r["id"] == rid
            ),
        )
        done_sub = st.form_submit_button("تمّت القراءة ✓")
    if done_sub:
        if not finished:
            st.warning("اختر القراءات التي أنهيتها")
        else:
            mark_done(finished)
            st.success("تقبّل الله — جُعلت في ميزان حسناتها 🌿")
            st.rerun()

# ----------------------------------------------------------------------------
# Leaderboard
# ----------------------------------------------------------------------------
if scores:
    st.markdown('<div class="section-title">🏆 لوحة الشرف — أكثر القرّاء عطاءً لها</div>', unsafe_allow_html=True)
    medals = ["🥇", "🥈", "🥉"]
    top = sorted(scores.items(), key=lambda kv: -kv[1])[:10]
    rows_html = []
    for i, (rname, sc) in enumerate(top):
        medal = medals[i] if i < 3 else ar_num(i + 1)
        rows_html.append(
            f'<div class="board-row {"top1" if i == 0 else ""}">'
            f'<span class="rank">{medal}</span>'
            f'<span class="bname">{rname}</span>'
            f'<span class="score">{ar_num(sc)} {"جزء" if sc <= 10 else "جزءًا"}</span>'
            f"</div>"
        )
    st.markdown(f'<div class="board">{"".join(rows_html)}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="text-align:center;color:#cfe3d6;font-family:Amiri,serif;font-size:1.05rem;margin-top:4px;">'
        "«وَفِي ذَٰلِكَ فَلْيَتَنَافَسِ الْمُتَنَافِسُونَ»</div>",
        unsafe_allow_html=True,
    )

# ----------------------------------------------------------------------------
# Read the Quran online (bundled Uthmani text)
# ----------------------------------------------------------------------------
st.markdown('<div class="section-title">🕌 اقرأ جزءك هنا مباشرة</div>', unsafe_allow_html=True)
st.markdown(
    '<div style="color:#cfe3d6;font-family:Amiri,serif;font-size:1.1rem;">'
    "اختر الجزء واقرأه من المصحف مباشرة — بنية أن يكون ثوابه لها بإذن الله"
    "</div>",
    unsafe_allow_html=True,
)
sel_juz = st.selectbox(
    "اختر الجزء",
    options=list(range(1, 31)),
    format_func=lambda j: f"الجزء {ar_num(j)} — {JUZ_NAMES[j-1]}",
    label_visibility="collapsed",
)
st.markdown(f'<div class="mushaf">{render_juz_html(sel_juz)}</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Admin (sidebar)
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ الإدارة")
    if ADMIN_PASSWORD:
        pw = st.text_input("كلمة السر", type="password")
        if pw == ADMIN_PASSWORD:
            st.success("مرحبًا بك")
            cancel = st.multiselect(
                "إلغاء قراءات جارية",
                options=[r["id"] for r in active_rows],
                format_func=lambda rid: next(
                    f"الجزء {ar_num(r['juz'])} — {r['reader_name']}" for r in active_rows if r["id"] == rid
                ),
            )
            if st.button("إلغاء المحدد") and cancel:
                delete_readings(cancel)
                st.rerun()
            st.divider()
            confirm = st.checkbox("أؤكد حذف كل السجلات نهائيًا")
            if st.button("🗑️ تصفير كل شيء") and confirm:
                reset_all()
                st.rerun()
    else:
        st.caption("أضف ADMIN_PASSWORD في الإعدادات لتفعيل لوحة الإدارة")
    st.divider()
    st.caption("قاعدة البيانات: " + ("سحابية دائمة ☁️" if USING_SUPABASE else "محلية للتجربة فقط 💻"))
