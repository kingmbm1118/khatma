# -*- coding: utf-8 -*-
"""
ختمة قرآن — صدقة جارية على روح أمي
تجربة مبسطة: اضغط على الجزء ← اكتب اسمك ← اقرأ ← اضغط "أنهيت".
كل قارئ لا يرى إلا أزرار إنهاء قراءاته هو، فلا تُنهى قراءة غيره بالخطأ.
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
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


MOTHER_NAME = get_secret("MOTHER_NAME", "أمي")

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
    layout="centered",
)

# ----------------------------------------------------------------------------
# Storage — readings log (many readers per juz)
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
    if USING_SUPABASE:
        sb = _supabase_client()
        return sb.table("readings").select("id, juz, reader_name, status").execute().data
    conn = _sqlite_conn()
    rows = conn.execute("SELECT id, juz, reader_name, status FROM readings").fetchall()
    conn.close()
    return [{"id": r[0], "juz": r[1], "reader_name": r[2], "status": r[3]} for r in rows]


def add_reading(juz, name):
    """Start a reading. Returns False if this person is already reading this juz."""
    for r in load_readings():
        if r["reader_name"] == name and r["status"] == "reading" and int(r["juz"]) == juz:
            return False
    row = {"juz": juz, "reader_name": name, "status": "reading",
           "created_at": _now(), "updated_at": _now()}
    if USING_SUPABASE:
        _supabase_client().table("readings").insert(row).execute()
    else:
        conn = _sqlite_conn()
        conn.execute(
            "INSERT INTO readings (juz, reader_name, status, created_at, updated_at) "
            "VALUES (:juz, :reader_name, :status, :created_at, :updated_at)", row)
        conn.commit()
        conn.close()
    load_readings.clear()
    return True


def mark_done(reading_id):
    if USING_SUPABASE:
        _supabase_client().table("readings").update(
            {"status": "done", "updated_at": _now()}).eq("id", reading_id).execute()
    else:
        conn = _sqlite_conn()
        conn.execute("UPDATE readings SET status='done', updated_at=? WHERE id=?", (_now(), reading_id))
        conn.commit()
        conn.close()
    load_readings.clear()


# ----------------------------------------------------------------------------
# Quran text (bundled: assets/quran.json — Uthmani script)
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
            if s not in (1, 9):
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


@st.cache_data(show_spinner=False)
def juz_surah_labels():
    """Label each juz by the surahs it spans, e.g. 'الفاتحة – البقرة'."""
    quran = load_quran()
    labels = []
    for s1, _, s2, _ in JUZ_RANGES:
        if s1 == s2:
            labels.append(quran[s1 - 1]["name"])
        else:
            labels.append(f'{quran[s1 - 1]["name"]} – {quran[s2 - 1]["name"]}')
    return labels


JUZ_NAMES = juz_surah_labels()

# ----------------------------------------------------------------------------
# Styling — mobile-first
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
.block-container { max-width: 860px; padding-top: 1.2rem; }
h1, h2, h3 { font-family: 'Amiri', serif !important; }

.hero { text-align: center; color: #f4ecd6; }
.hero .bismillah { font-family:'Amiri',serif; font-size: 1.9rem; color: #d9b64a; margin-bottom: 0.3rem; }
.hero .title { font-family:'Amiri',serif; font-size: 2.1rem; font-weight: 700; }
.hero .dua {
    font-family:'Amiri',serif; font-size: 1.2rem; color: #cfe3d6;
    max-width: 680px; margin: 0.5rem auto 0 auto; line-height: 2.0;
}
.photo-frame img {
    border-radius: 50%; border: 4px solid #d9b64a;
    box-shadow: 0 0 40px rgba(217,182,74,0.35);
}

.big-hint {
    text-align:center; font-family:'Amiri',serif; color:#f0d98a;
    font-size: 1.35rem; margin: 10px 0 2px 0; line-height: 1.9;
}
.sub-hint { text-align:center; color:#cfe3d6; font-size: 0.98rem; margin-bottom: 6px; }

.greet {
    text-align:center; background: rgba(217,182,74,0.12); border: 1.5px solid #d9b64a;
    border-radius: 14px; padding: 10px 14px; color: #f4ecd6;
    font-size: 1.15rem; font-weight: 600; margin: 8px 0;
}

.section-title {
    font-family:'Amiri',serif; color: #d9b64a; font-size: 1.4rem;
    border-bottom: 1px solid rgba(217,182,74,0.35); padding-bottom: 6px; margin-top: 1.3rem;
}

/* ---------- stats / milestones ---------- */
.stat-row { display:flex; gap:10px; flex-wrap:wrap; justify-content:center; margin-top:8px; }
.stat-box {
    background: rgba(244,236,214,0.06); border: 1px solid rgba(217,182,74,0.45);
    border-radius: 14px; padding: 8px 14px; text-align:center; color:#f4ecd6; flex: 1 1 40%;
    min-width: 120px; max-width: 200px;
}
.stat-box .big { font-family:'Amiri',serif; font-size: 1.6rem; color:#d9b64a; font-weight:700; }
.stat-box .lbl { font-size: 0.8rem; opacity: 0.9; }
.milestone-track { display:flex; gap:6px; justify-content:center; flex-wrap:wrap; margin: 8px 0 4px 0; }
.milestone {
    border-radius: 999px; padding: 4px 12px; font-size: 0.82rem; font-weight: 600;
    border: 1.5px solid rgba(217,182,74,0.5); color: #d9c99a; background: rgba(244,236,214,0.05);
}
.milestone.hit { background: linear-gradient(160deg,#d9b64a,#b9932f); color: #1d2a17; border-color:#f0d98a; }

.remaining-panel {
    background: rgba(217,182,74,0.08); border: 1.5px dashed rgba(217,182,74,0.6);
    border-radius: 14px; padding: 10px 12px; margin-top: 10px; text-align:center;
}
.remaining-panel .head { font-family:'Amiri',serif; color:#f0d98a; font-size:1.15rem; margin-bottom:4px; }

/* ---------- leaderboard ---------- */
.board-row {
    display:flex; align-items:center; gap:10px;
    background: rgba(244,236,214,0.06); border: 1px solid rgba(217,182,74,0.35);
    border-radius: 12px; padding: 7px 14px; margin-bottom: 6px; color:#f4ecd6;
}
.board-row .rank { font-size: 1.1rem; width: 1.9rem; text-align:center; }
.board-row .bname { font-weight: 700; flex-grow: 1; }
.board-row .score { font-family:'Amiri',serif; color:#d9b64a; font-weight:700; }
.board-row.top1 { border-color:#f0d98a; background: rgba(217,182,74,0.16); }

/* ---------- juz buttons grid ---------- */
div.stButton > button, div[data-testid="stDialog"] button[kind="primary"] {
    border-radius: 14px; font-family: 'Cairo', sans-serif; font-weight: 700;
    white-space: normal; line-height: 1.55;
}
div.stButton > button[kind="primary"] {
    background: linear-gradient(160deg, #d9b64a, #c3a038); color: #14301f; border: 1.5px solid #f0d98a;
}
div.stButton > button[kind="primary"]:hover { background: #e8ca6a; color:#14301f; }
div.stButton > button[kind="secondary"] {
    background: rgba(244,236,214,0.07); color: #f4ecd6; border: 1.5px solid rgba(217,182,74,0.55);
}
div.stButton > button[kind="secondary"]:hover { border-color: #f0d98a; color: #f0d98a; }
.juz-btn div.stButton > button { min-height: 92px; }

/* keep columns side-by-side on phones (Streamlit stacks them by default) */
@media (max-width: 640px) {
    div[data-testid="stHorizontalBlock"] { flex-direction: row !important; flex-wrap: wrap !important; gap: 8px !important; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        min-width: calc(33.3% - 8px) !important; flex: 1 1 calc(33.3% - 8px) !important; width: auto !important;
    }
}

.stProgress > div > div > div > div { background-color: #d9b64a; }
footer, #MainMenu { visibility: hidden; }

/* ---------- Quran reading panel ---------- */
.mushaf {
    background: #f9f4e3; border: 2px solid #d9b64a; border-radius: 18px;
    padding: 26px 28px; margin-top: 10px;
    box-shadow: inset 0 0 60px rgba(185,147,47,0.15), 0 6px 24px rgba(0,0,0,0.35);
    max-height: 75vh; overflow-y: auto; direction: rtl;
}
.surah-header {
    font-family:'Amiri',serif; text-align:center; color:#7a5c12;
    background: linear-gradient(90deg, transparent, rgba(217,182,74,0.30), transparent);
    border-top: 1px solid #c9a94f; border-bottom: 1px solid #c9a94f;
    font-size: 1.55rem; font-weight: 700; padding: 8px 0; margin: 18px 0 6px 0;
}
.surah-header.cont { font-size: 1.1rem; opacity: 0.85; }
.basmala { font-family:'Amiri Quran','Amiri',serif; text-align:center; color:#3a2e10; font-size:1.65rem; margin: 8px 0 12px 0; }
.quran-text { font-family:'Amiri Quran','Amiri',serif; color:#26200e; font-size:1.7rem; line-height:2.65; text-align:justify; }
.aya-num { color: #a9821f; font-size: 1.2rem; }

/* ---------- Mobile ---------- */
@media (max-width: 640px) {
    .block-container { padding-left: 0.7rem; padding-right: 0.7rem; }
    .hero .bismillah { font-size: 1.5rem; }
    .hero .title { font-size: 1.4rem; line-height: 1.7; }
    .hero .dua { font-size: 0.98rem; line-height: 1.85; }
    .big-hint { font-size: 1.15rem; }
    .section-title { font-size: 1.2rem; }
    .stat-box .big { font-size: 1.3rem; }
    .stat-box .lbl { font-size: 0.72rem; }
    .milestone { padding: 3px 9px; font-size: 0.74rem; }
    .remaining-panel .head { font-size: 1.0rem; }
    .juz-btn div.stButton > button { min-height: 96px; font-size: 0.82rem; padding: 6px 4px; }
    .board-row { padding: 6px 10px; }
    .board-row .bname { font-size: 0.9rem; }
    .mushaf { padding: 14px 12px; max-height: 68vh; border-radius: 14px; }
    .surah-header { font-size: 1.25rem; }
    .basmala { font-size: 1.35rem; }
    .quran-text { font-size: 1.4rem; line-height: 2.35; }
    .aya-num { font-size: 1.0rem; }
    .photo-hero img { width: 140px !important; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------
st.markdown('<div class="hero"><div class="bismillah">﷽</div></div>', unsafe_allow_html=True)

if MOTHER_IMG.exists():
    import base64
    _img_b64 = base64.b64encode(MOTHER_IMG.read_bytes()).decode()
    st.markdown(
        f'<div class="photo-frame photo-hero" style="text-align:center;">'
        f'<img src="data:image/jpeg;base64,{_img_b64}" width="210" alt=""/></div>',
        unsafe_allow_html=True,
    )

st.markdown(
    f"""
<div class="hero">
  <div class="title">ختمة قرآن على روح {MOTHER_NAME}</div>
  <div class="dua">
    اللهم اغفر لها وارحمها، واجعل قبرها روضةً من رياض الجنة،
    واجعل كل حرفٍ يُقرأ في هذه الختمة نورًا لها ورحمة
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Hidden background audio (plays once on load)
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
# Identity: remember the visitor's name (session + URL so refresh keeps it)
# ----------------------------------------------------------------------------
if "reader_name" not in st.session_state:
    qp_name = st.query_params.get("name", "")
    if qp_name:
        st.session_state["reader_name"] = qp_name

my_name = st.session_state.get("reader_name", "").strip()

# ----------------------------------------------------------------------------
# Compute state
# ----------------------------------------------------------------------------
readings = load_readings()
done_counts = {j: 0 for j in range(1, 31)}
active_by_juz = {j: [] for j in range(1, 31)}
scores = {}
my_active = []  # this visitor's unfinished readings

for r in readings:
    j = int(r["juz"])
    if r["status"] == "done":
        done_counts[j] += 1
        scores[r["reader_name"]] = scores.get(r["reader_name"], 0) + 1
    else:
        active_by_juz[j].append(r["reader_name"])
        if my_name and r["reader_name"] == my_name:
            my_active.append(r)

completed_khatmas = min(done_counts.values())
current_no = completed_khatmas + 1
covered = {j for j in range(1, 31) if done_counts[j] >= current_no}
remaining = [j for j in range(1, 31) if j not in covered]
progress = len(covered)
total_done_readings = sum(done_counts.values())
readers_count = len({r["reader_name"] for r in readings})

# ----------------------------------------------------------------------------
# Dialog: tap a juz → asks for name → confirm
# ----------------------------------------------------------------------------
@st.dialog("🤲 قراءة جزء")
def confirm_read(j):
    st.markdown(
        f'<div style="text-align:center;font-family:Amiri,serif;">'
        f'<div style="font-size:1.7rem;font-weight:700;color:#d9b64a;">الجزء {ar_num(j)}</div>'
        f'<div style="font-size:1.2rem;">{JUZ_NAMES[j-1]}</div></div>',
        unsafe_allow_html=True,
    )
    st.text_input("اكتب اسمك", value=st.session_state.get("reader_name", ""),
                  key="dlg_name", placeholder="الاسم الذي سيظهر للجميع")
    if st.session_state.get("dlg_warn"):
        st.warning(st.session_state.pop("dlg_warn"))

    def _confirm(juz):
        name = st.session_state.get("dlg_name", "").strip()
        if not name:
            st.session_state["dlg_warn"] = "من فضلك اكتب اسمك أولًا"
            return
        st.session_state["reader_name"] = name
        try:
            st.query_params["name"] = name
        except Exception:
            pass
        if add_reading(juz, name):
            st.session_state["flash"] = (
                f"تقبّل الله منك يا {name} — الجزء {ar_num(juz)} لك، "
                "وستجد زر «أنهيت القراءة» بالأعلى عند الانتهاء"
            )
        else:
            st.session_state["flash"] = f"أنت تقرأ الجزء {ar_num(juz)} بالفعل — بارك الله فيك"
        st.session_state["dlg_confirmed"] = True

    if st.button("نعم، سأقرأ هذا الجزء إن شاء الله", type="primary",
                 use_container_width=True, on_click=_confirm, args=(j,)):
        if st.session_state.pop("dlg_confirmed", False):
            st.rerun()


# flash message from the previous action
if st.session_state.get("flash"):
    st.success(st.session_state.pop("flash"))

# ----------------------------------------------------------------------------
# My readings — only I can finish MY readings
# ----------------------------------------------------------------------------
if my_name:
    hello = f'أهلًا {my_name} 🌿'
    if not my_active:
        hello += " — اضغط على أي جزء بالأسفل لتقرأه"
    st.markdown(f'<div class="greet">{hello}</div>', unsafe_allow_html=True)

if my_active:
    st.markdown('<div class="section-title">📖 قراءاتي الحالية</div>', unsafe_allow_html=True)
    for r in sorted(my_active, key=lambda x: x["juz"]):
        j = int(r["juz"])
        c1, c2 = st.columns(2)
        with c1:
            if st.button(f"📖 اقرأ الجزء {ar_num(j)}", key=f"read{r['id']}", use_container_width=True):
                st.session_state["mushaf_select"] = j
                st.session_state["scroll_to_mushaf"] = True
                st.rerun()
        with c2:
            if st.button(f"✅ أنهيت الجزء {ar_num(j)}", key=f"done{r['id']}", type="primary",
                         use_container_width=True):
                mark_done(r["id"])
                st.session_state["flash"] = "تقبّل الله منك — جُعلت في ميزان حسناتها 🌿"
                st.rerun()

# ----------------------------------------------------------------------------
# Progress (one glance) + remaining
# ----------------------------------------------------------------------------
st.progress(progress / 30)
st.markdown(
    f'<div style="text-align:center;color:#f4ecd6;font-family:Amiri,serif;font-size:1.15rem;">'
    f'اكتمل {ar_num(progress)} من ٣٠ جزءًا في الختمة {khatma_ordinal(current_no)}'
    + (f' &nbsp;🌙&nbsp; ختمات تمّت: {ar_num(completed_khatmas)}' if completed_khatmas else "")
    + "</div>",
    unsafe_allow_html=True,
)

if progress == 30:
    st.balloons()
    st.success(f"🌙 اكتملت الختمة {khatma_ordinal(current_no)} بفضل الله — تقبّل الله منا ومنكم! الختمة {khatma_ordinal(current_no + 1)} تبدأ الآن 🤲")

# ----------------------------------------------------------------------------
# The juz grid — tap to read
# ----------------------------------------------------------------------------
st.markdown('<div class="big-hint">اضغط على الجزء الذي تريد قراءته 👇</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-hint">يمكن لأكثر من قارئ قراءة الجزء نفسه — كل قراءة لها ثوابها بإذن الله</div>', unsafe_allow_html=True)

st.markdown('<div class="juz-btn">', unsafe_allow_html=True)
for row_start in range(1, 31, 3):
    cols = st.columns(3)
    for i, j in enumerate(range(row_start, min(row_start + 3, 31))):
        n_active = len(active_by_juz[j])
        if j in covered:
            status = f"✅ قُرئ {ar_num(done_counts[j])} مرة" if done_counts[j] > 1 else "✅ تمّت قراءته"
            btype = "secondary"
        elif n_active:
            status = f"⏳ يقرؤه {ar_num(n_active)}"
            btype = "secondary"
        else:
            status = "⭐ يحتاج قارئًا"
            btype = "primary"
        label = f"الجزء {ar_num(j)}  \n{JUZ_NAMES[j-1]}  \n{status}"
        with cols[i]:
            if st.button(label, key=f"juz{j}", type=btype, use_container_width=True):
                confirm_read(j)
st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Stats + milestones
# ----------------------------------------------------------------------------
st.markdown(
    f"""
<div class="stat-row">
  <div class="stat-box"><div class="big">{ar_num(completed_khatmas)}</div><div class="lbl">ختمات مكتملة 🌙</div></div>
  <div class="stat-box"><div class="big">{ar_num(progress)} / ٣٠</div><div class="lbl">الختمة الحالية</div></div>
  <div class="stat-box"><div class="big">{ar_num(total_done_readings)}</div><div class="lbl">أجزاء مقروءة</div></div>
  <div class="stat-box"><div class="big">{ar_num(readers_count)}</div><div class="lbl">قارئ 🤲</div></div>
</div>
""",
    unsafe_allow_html=True,
)

MILESTONES = [(5, "٥ أجزاء"), (10, "ثلث الختمة"), (15, "نصف الختمة"), (20, "ثلثا الختمة"), (25, "٢٥ جزءًا"), (30, "ختمة كاملة 🌙")]
ms_html = "".join(
    f'<span class="milestone {"hit" if progress >= v else ""}">{"✓ " if progress >= v else ""}{lbl}</span>'
    for v, lbl in MILESTONES
)
st.markdown(f'<div class="milestone-track">{ms_html}</div>', unsafe_allow_html=True)

if remaining and progress < 30:
    if len(remaining) <= 5:
        head = f"🔥 اقتربنا! بقي {ar_num(len(remaining))} فقط لإتمام الختمة — من يكسب شرف الإتمام؟"
    else:
        head = f"بقي {ar_num(len(remaining))} جزءًا لإتمام الختمة {khatma_ordinal(current_no)} — الأجزاء ذات النجمة ⭐ تنتظر قارئًا"
    st.markdown(f'<div class="remaining-panel"><div class="head">{head}</div></div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Leaderboard
# ----------------------------------------------------------------------------
if scores:
    st.markdown('<div class="section-title">أكثر القرّاء عطاءً لها</div>', unsafe_allow_html=True)
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
    st.markdown("".join(rows_html), unsafe_allow_html=True)
    st.markdown(
        '<div style="text-align:center;color:#cfe3d6;font-family:Amiri,serif;font-size:1.0rem;margin-top:4px;">'
        "«وَفِي ذَٰلِكَ فَلْيَتَنَافَسِ الْمُتَنَافِسُونَ»</div>",
        unsafe_allow_html=True,
    )

# ----------------------------------------------------------------------------
# Mushaf reader — scrolls to the start of the picked juz
# ----------------------------------------------------------------------------
st.markdown('<div class="section-title">🕌 اقرأ جزءك هنا مباشرة</div>', unsafe_allow_html=True)

sel_juz = st.selectbox(
    "اختر الجزء",
    options=list(range(1, 31)),
    format_func=lambda j: f"الجزء {ar_num(j)} — {JUZ_NAMES[j-1]}",
    key="mushaf_select",
    label_visibility="collapsed",
)
st.markdown(f'<div class="mushaf" id="mushaf-panel">{render_juz_html(sel_juz)}</div>', unsafe_allow_html=True)

# عند اختيار جزء جديد أو الضغط على «اقرأ»: يعود المصحف لبداية الجزء وينتقل إليه على الشاشة
_prev = st.session_state.get("prev_juz")
st.session_state["prev_juz"] = sel_juz
if (_prev is not None and _prev != sel_juz) or st.session_state.pop("scroll_to_mushaf", False):
    import streamlit.components.v1 as components
    components.html(
        f"""<script>
        const doc = window.parent.document;
        const m = doc.getElementById('mushaf-panel');
        if (m) {{
            m.scrollTop = 0;
            m.scrollIntoView({{behavior: 'smooth', block: 'start'}});
        }}
        // juz={sel_juz}
        </script>""",
        height=0,
    )
