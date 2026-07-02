# -*- coding: utf-8 -*-
"""
ختمة قرآن مبسطة — صدقة جارية على روح الحاجة رضا سعد على
تعتمد على جلب النص الموثوق مباشرة من خوادم الـ Quran المفتوحة والموثقة رسميًا.
"""

import sqlite3
import urllib.request
import json
from datetime import datetime, timezone
from pathlib import Path
import base64
import os

import streamlit as st

# ----------------------------------------------------------------------------
# Configuration & Setup
# ----------------------------------------------------------------------------
APP_DIR = Path(__file__).parent
ASSETS = APP_DIR / "assets"
os.makedirs(ASSETS, exist_ok=True)

def get_secret(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

MOTHER_NAME = get_secret("MOTHER_NAME", "أمي")

JUZ_NAMES = [
    "الفاتحة", "1 البقرة", "2 البقرة", "آل عمران", "1 النساء", "2 النساء",
    "المائدة", "الأنعام", "الأعراف", "الأنفال", "التوبة", "هود", "يوسف",
    "الحجر", "الإسراء", "الكهف", "الأنبياء", "المؤمنون", "الفرقان", "النمل",
    "العنكبوت", "الأحزاب", "يس", "الزمر", "فصلت", "الأحقاف", "الذاريات",
    "المجادلة", "الملك", "النبأ"
]

# حدود الأجزاء الدقيقة 100% حسب المصحف العثماني الشريف:
# (سورة البداية، آية البداية، سورة النهاية، آية النهاية)
JUZ_RANGES = [
    (1, 1, 2, 141),    # 1
    (2, 142, 2, 252),  # 2
    (2, 253, 3, 92),   # 3
    (3, 93, 4, 23),    # 4
    (4, 24, 4, 147),   # 5
    (4, 148, 5, 81),   # 6
    (5, 82, 6, 110),   # 7
    (6, 111, 7, 87),   # 8
    (7, 88, 8, 40),    # 9
    (8, 41, 9, 92),    # 10
    (9, 93, 11, 5),    # 11
    (11, 6, 12, 52),   # 12
    (12, 53, 14, 52),  # 13
    (15, 1, 16, 128),  # 14
    (17, 1, 18, 74),   # 15
    (18, 75, 20, 135), # 16
    (21, 1, 22, 78),   # 17
    (23, 1, 25, 20),   # 18
    (25, 21, 27, 55),  # 19
    (27, 56, 29, 45),  # 20
    (29, 46, 33, 30),  # 21
    (33, 31, 36, 27),  # 22
    (36, 28, 39, 31),  # 23
    (39, 32, 41, 46),  # 24
    (41, 47, 45, 37),  # 25
    (46, 1, 51, 30),   # 26
    (51, 31, 57, 29),  # 27
    (58, 1, 66, 12),   # 28
    (67, 1, 77, 50),   # 29
    (78, 1, 114, 6),   # 30
]

_AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

def ar_num(n):
    return str(n).translate(_AR_DIGITS)

st.set_page_config(
    page_title=f"ختمة على روح {MOTHER_NAME}",
    page_icon="📖",
    layout="wide",
)

if "mushaf_juz" not in st.session_state:
    st.session_state["mushaf_juz"] = 1

# ----------------------------------------------------------------------------
# Database Layer (SQLite / Supabase)
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

@st.cache_data(ttl=2, show_spinner=False)
def load_readings():
    if USING_SUPABASE:
        sb = _supabase_client()
        return sb.table("readings").select("id, juz, reader_name, status").execute().data
    conn = _sqlite_conn()
    rows = conn.execute("SELECT id, juz, reader_name, status FROM readings").fetchall()
    conn.close()
    return [{"id": r[0], "juz": r[1], "reader_name": r[2], "status": r[3]} for r in rows]

def add_reading(juz_no, name):
    rows = [{"juz": juz_no, "reader_name": name, "status": "reading", "created_at": _now(), "updated_at": _now()}]
    if USING_SUPABASE:
        _supabase_client().table("readings").insert(rows).execute()
    else:
        conn = _sqlite_conn()
        conn.execute("INSERT INTO readings (juz, reader_name, status, created_at, updated_at) VALUES (?, ?, 'reading', ?, ?)", (juz_no, name, _now(), _now()))
        conn.commit()
        conn.close()
    load_readings.clear()

def confirm_done(reading_id):
    if USING_SUPABASE:
        _supabase_client().table("readings").update({"status": "done", "updated_at": _now()}).eq("id", reading_id).execute()
    else:
        conn = _sqlite_conn()
        conn.execute("UPDATE readings SET status='done', updated_at=? WHERE id=?", (_now(), reading_id))
        conn.commit()
        conn.close()
    load_readings.clear()

# ----------------------------------------------------------------------------
# Online Trusted Source Quran Data Engine (Tanzil API Delivery)
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=True)
def fetch_trusted_quran():
    """يجلب المصحف العثماني بالتشكيل كاملاً ومقسمًا بالسور من مستودع بيانات القرآن المفتوح المعتمد"""
    url = "https://cdn.jsdelivr.net/gh/semarketir/quranjson@master/source/surah.json"
    try:
        with urllib.request.urlopen(url) as response:
            surahs_list = json.loads(response.read().decode('utf-8'))
            
            # ترتيب وتحويل البيانات لتوافق محرك التصفح الداخلي للأجزاء
            structured_quran = []
            for s in surahs_list:
                surah_url = f"https://cdn.jsdelivr.net/gh/semarketir/quranjson@master/source/surah/surah_{s['index']}.json"
                with urllib.request.urlopen(surah_url) as s_res:
                    s_data = json.loads(s_res.read().decode('utf-8'))
                    verses_list = []
                    # تحويل آيات السورة إلى الشكل القياسي المطلوب للمصحف
                    for k, v in s_data["verse"].items():
                        # تنظيف مفاتيح الآيات وتحويلها لأرقام صحيحة
                        v_id = int(k.replace("verse_", ""))
                        verses_list.append({"id": v_id, "text": v})
                    
                    # ترتيب الآيات تصاعدياً للتأكد من تسلسل النص
                    verses_list.sort(key=lambda x: x["id"])
                    
                    structured_quran.append({
                        "id": int(s["index"]),
                        "name": s["titleAr"],
                        "total_verses": int(s["count"]),
                        "verses": verses_list
                    })
            return structured_quran
    except Exception as e:
        st.error(f"حدث خطأ أثناء جلب المصحف الشريف عبر الإنترنت: {e}. يرجى التحقق من الاتصال بالشبكة.")
        return []

BASMALA = "بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ"

def render_juz_html(juz_no: int) -> str:
    quran = fetch_trusted_quran()
    if not quran:
        return '<div style="color:red; text-align:center;">تعذر تحميل صفحات المصحف الشريف حالياً.</div>'
        
    s1, a1, s2, a2 = JUZ_RANGES[juz_no - 1]
    parts = []
    
    for s in range(s1, s2 + 1):
        surah = quran[s - 1]
        start = a1 if s == s1 else 1
        end = a2 if s == s2 else surah["total_verses"]
        
        if start == 1:
            parts.append(f'<div class="surah-header">سُورَةُ {surah["name"]}</div>')
            if s not in (1, 9): # الفاتحة والتوبة لا تكرر البسملة في أولهما كالعادة
                parts.append(f'<div class="basmala">{BASMALA}</div>')
        else:
            parts.append(f'<div class="surah-header cont">تكملة سُورَةِ {surah["name"]} — من الآية {ar_num(start)}</div>')
            
        ayat = [f'{v["text"]} <span class="aya-num">﴿{ar_num(v["id"])}﴾</span>' for v in surah["verses"][start - 1 : end]]
        parts.append(f'<div class="quran-text">{" ".join(ayat)}</div>')
        
    return "".join(parts)

# ----------------------------------------------------------------------------
# CSS Styles Injection
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
.hero .dua { font-family:'Amiri',serif; font-size: 1.25rem; color: #cfe3d6; max-width: 720px; margin: 0.6rem auto; line-height: 2.1; }

.stat-row { display:flex; gap:12px; flex-wrap:wrap; justify-content:center; margin-top:8px; }
.stat-box {
    background: rgba(244,236,214,0.06); border: 1px solid rgba(217,182,74,0.45);
    border-radius: 14px; padding: 10px 22px; text-align:center; color:#f4ecd6; min-width: 130px;
}
.stat-box .big { font-family:'Amiri',serif; font-size: 1.9rem; color:#d9b64a; font-weight:700; }
.stat-box .lbl { font-size: 0.85rem; opacity: 0.9; }

div[data-testid="stColumn"] div.stButton > button {
    width: 100% !important;
    min-height: 120px !important;
    border-radius: 14px !important;
    padding: 10px !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    white-space: pre-line !important;
    line-height: 1.4 !important;
    transition: all 0.2s ease-in-out !important;
}

.juz-btn-available > button { background: rgba(244,236,214,0.06) !important; border: 1.5px dashed rgba(217,182,74,0.6) !important; color: #f0d98a !important; }
.juz-btn-reading > button { background: rgba(217,182,74,0.15) !important; border: 1.5px solid #d9b64a !important; color: #f4ecd6 !important; font-weight: bold !important;}
.juz-btn-done > button { background: linear-gradient(160deg, #d9b64a, #b9932f) !important; border: 1.5px solid #f0d98a !important; color: #1d2a17 !important; font-weight: bold !important; }

div[data-testid="stColumn"] div.stButton > button:hover { transform: translateY(-3px) !important; box-shadow: 0 4px 15px rgba(0,0,0,0.2) !important; }
.section-title { font-family:'Amiri',serif; color: #d9b64a; font-size: 1.6rem; border-bottom: 1px solid rgba(217,182,74,0.35); padding-bottom: 6px; margin-top: 1.8rem; }

.mushaf {
    background: #f9f4e3; border: 2px solid #d9b64a; border-radius: 18px; padding: 28px 30px; margin-top: 10px;
    box-shadow: inset 0 0 60px rgba(185,147,47,0.15), 0 6px 24px rgba(0,0,0,0.35); max-height: 75vh; overflow-y: auto; direction: rtl;
}
.surah-header { font-family:'Amiri',serif; text-align:center; color:#7a5c12; background: linear-gradient(90deg, transparent, rgba(217,182,74,0.30), transparent); border-top: 1px solid #c9a94f; border-bottom: 1px solid #c9a94f; font-size: 1.6rem; font-weight: 700; padding: 8px 0; margin: 20px 0 6px 0; }
.surah-header.cont { font-size: 1.15rem; opacity: 0.85; }
.basmala { font-family:'Amiri Quran','Amiri',serif; text-align:center; color:#3a2e10; font-size:1.7rem; margin: 8px 0 12px 0; }
.quran-text { font-family:'Amiri Quran','Amiri',serif; color:#26200e; font-size:1.75rem; line-height:2.7; text-align:justify; }
.aya-num { color: #a9821f; font-size: 1.25rem; }

footer, #MainMenu { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Header & Dedication
# ----------------------------------------------------------------------------
st.markdown('<div class="hero"><div class="bismillah">﷽</div></div>', unsafe_allow_html=True)
st.markdown(f'<div class="hero"><div class="title">ختمة قرآن على روح {MOTHER_NAME}</div><div class="dua">اللهم اجعل كل حرفٍ يُقرأ في هذه الختمة نورًا لها ورحمة وجافِ القبر عن جنبيها واجعلها في جنات النعيم...<br>«وَقُل رَّبِّ ارْحَمْهُمَا كَمَا رَبَّيَانِي صَغِيرًا»</div></div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Calculations
# ----------------------------------------------------------------------------
readings = load_readings()
done_counts = {j: 0 for j in range(1, 31)}
active_by_juz = {j: [] for j in range(1, 31)}

for r in readings:
    j = int(r["juz"])
    if r["status"] == "done":
        done_counts[j] += 1
    else:
        active_by_juz[j].append((r["id"], r["reader_name"]))

completed_khatmas = min(done_counts.values())
current_no = completed_khatmas + 1
progress = sum(1 for j in range(1, 31) if done_counts[j] >= current_no)
total_done_readings = sum(done_counts.values())
readers_count = len({r["reader_name"] for r in readings})

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

# ----------------------------------------------------------------------------
# Popup Dialogues (Simplified Secure Flow)
# ----------------------------------------------------------------------------
@st.dialog("📝 حجز جزء للقراءة")
def show_reserve_dialog(juz_no):
    st.write(f"لقد اخترت: **الجزء {ar_num(juz_no)} — {JUZ_NAMES[juz_no-1]}**")
    name_input = st.text_input("اكتب اسمك الكريم هنا لبدء القراءة:", key="input_res_name", placeholder="مثال: أحمد محمد")
    if st.button("تأكيد وحجز الجزء الآن 🤲", use_container_width=True):
        if not name_input.strip():
            st.error("الرجاء كتابة الاسم أولاً")
        else:
            add_reading(juz_no, name_input.strip())
            st.session_state["mushaf_juz"] = juz_no
            st.success("تم الحجز بنجاح! تقبل الله منك.")
            st.rerun()

@st.dialog("✅ تأكيد إتمام القراءة")
def show_complete_dialog(juz_no, active_list):
    st.write(f"تأكيد إنهاء: **الجزء {ar_num(juz_no)} — {JUZ_NAMES[juz_no-1]}**")
    readers_text = " ، ".join([f"[{r[1]}]" for r in active_list])
    st.warning(f"هذا الجزء محجوز حالياً باسم: {readers_text}")
    st.markdown("⚠️ **لحماية القراءات ومنع الأخطاء:** يرجى كتابة اسمك تماماً كما سجلته لتأكيد الختم:")
    confirm_name = st.text_input("اكتب اسمك المسجّل:", key="input_conf_name")
    
    if st.button("نعم، أتممت قراءته كاملاً الحين ✓", use_container_width=True):
        matched_record = next((r for r in active_list if r[1].strip() == confirm_name.strip()), None)
        if matched_record:
            confirm_done(matched_record[0])
            st.session_state["mushaf_juz"] = juz_no
            st.success("جزاك الله خيراً! 🌿")
            st.rerun()
        else:
            st.error("❌ الاسم غير مطابق للاسم المحجوز به هذا الجزء حالياً! يرجى التأكد.")

# ----------------------------------------------------------------------------
# Grid Generation
# ----------------------------------------------------------------------------
st.markdown('<div class="section-title">📖 لوحة الأجزاء الثلاثون (اضغط مباشرة على أي جزء)</div>', unsafe_allow_html=True)

grid_columns = st.columns(6)
for index, j in enumerate(range(1, 31)):
    actives = active_by_juz[j]
    is_covered = (done_counts[j] >= current_no)
    
    if is_covered:
        btn_class = "juz-btn-done"
        lbl = f"الجزء {ar_num(j)}\n{JUZ_NAMES[j-1]}\n✓ تم ختمه"
    elif len(actives) > 0:
        btn_class = "juz-btn-reading"
        lbl = f"الجزء {ar_num(j)}\n{JUZ_NAMES[j-1]}\n⏳ يقرؤه: {actives[0][1]}"
    else:
        btn_class = "juz-btn-available"
        lbl = f"الجزء {ar_num(j)}\n{JUZ_NAMES[j-1]}\n⭐ اضغط لحجزه"
        
    with grid_columns[index % 6]:
        st.markdown(f'<div class="juz-container {btn_class}">', unsafe_allow_html=True)
        if st.button(lbl, key=f"j_btn_{j}"):
            st.session_state["mushaf_juz"] = j
            if is_covered:
                show_reserve_dialog(j)
            elif len(actives) > 0:
                show_complete_dialog(j, actives)
            else:
                show_reserve_dialog(j)
        st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# The Quran Reader Panel
# ----------------------------------------------------------------------------
selected_juz = st.session_state["mushaf_juz"]
st.markdown(f'<div class="section-title" id="mushaf-view">🕌 مصحف التلاوة المباشر — يعرض الآن (الجزء {ar_num(selected_juz)})</div>', unsafe_allow_html=True)
st.markdown('<div class="mushaf">' + render_juz_html(selected_juz) + '</div>', unsafe_allow_html=True)
