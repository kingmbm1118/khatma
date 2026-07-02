# -*- coding: utf-8 -*-
"""
ختمة قرآن مبسطة — صدقة جارية على روح الحاجة رضا سعد على
نصوص موثقة 100% مستوحاة مباشرة من سيرفرات معهد الـ Quran API الرسمي.
"""

import sqlite3
import urllib.request
import json
from datetime import datetime, timezone
from pathlib import Path
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
# Premium Fixed Online Quran Engine (Official Quran.com Core V4 API)
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=True)
def fetch_juz_verses_online(juz_no: int):
    """جلب نصوص الجزء المعين بالتشكيل العثماني مباشرة وثابت من خوادم قراءات المصحف العالمية الشريكة"""
    # نستخدم المخطط المعتمد العثماني المشكّل من خوادم قوقل/تنزيل الصديقة للموقع الرسمي
    url = f"https://api.quran.com/api/v4/quran/verses/uthmani?juz_number={juz_no}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            verses = data.get("verses", [])
            return verses
    except Exception as e:
        st.error(f"تعذر جلب آيات القرآن من الخادم الرئيسي: {e}")
        return []

def get_surah_name_ar(surah_id: int) -> str:
    # قائمة أسماء السور لتبويب المصحف ديناميكياً
    names = [
        "الفاتحة","البقرة","آل عمران","النساء","المائدة","الأنعام","الأعراف","الأنفال","التوبة","يونس","هود",
        "يوسف","الرعد","إبراهيم","الحجر","النحل","الإسراء","الكهف","مريم","طه","الأنبياء","الحج","المؤمنون",
        "النور","الفرقان","الشعراء","النمل","القصص","العنكبوت","الروم","لقمان","السجدة","الأحزاب","سبأ",
        "فاطر","يس","الصافات","ص","الزمر","غافر","فصلت","الشورى","الزخرف","الدخان","الجاثية","الأحقاف",
        "محمد","الفتح","الحجرات","ق","الذاريات","الطور","النجم","القمر","الرحمن","الواقعة","الحديد","المجادلة",
        "الحشر","الممتحنة","الصف","الجمعة","المنافقون","التغابن","الطلاق","التحريم","الملك","القلم","الحاقة",
        "المعارج","نوح","الجن","المزمل","المدثر","القيامة","الإنسان","المرسلات","النبأ","النازعات","عبس",
        "التكوير","الانفطار","المطففين","الانشقاق","البروج","الطارق","الأعلى","الغاشية","الفجر","البلد",
        "الشمس","الليل","الضحى","الشرح","التين","العلق","القدر","البينة","الزلزلة","العاديات","القارعة",
        "التكاثر","العصر","الهمزة","الفيل","قريش","الماعون","الكوثر","الكافرون","النصر","المسد","الإخلاص",
        "الفلق","الناس"
    ]
    return names[surah_id - 1] if 1 <= surah_id <= 114 else ""

BASMALA = "بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ"

def render_juz_html(juz_no: int) -> str:
    verses = fetch_juz_verses_online(juz_no)
    if not verses:
        return '<div style="color:#d9b64a; text-align:center; padding: 20px;">جاري الاتصال السريع بخوادم القرآن الكريم الموثوقة... برجاء الانتظار ثواني أو إعادة تحديث الصفحة.</div>'
    
    parts = []
    current_surah = None
    
    for v in verses:
        # مفتاح الآية يأتي على شكل "1:1" (رقم السورة : رقم الآية)
        key_parts = v["verse_key"].split(":")
        surah_id = int(key_parts[0])
        verse_num = int(key_parts[1])
        text = v["text_uthmani"]
        
        # إذا دخلنا في سورة جديدة، نقوم بطباعة ترويسة السورة والبسملة
        if surah_id != current_surah:
            current_surah = surah_id
            s_name = get_surah_name_ar(surah_id)
            parts.append(f'<div class="surah-header">سُورَةُ {s_name}</div>')
            if surah_id not in (1, 9) and verse_num == 1:
                parts.append(f'<div class="basmala">{BASMALA}</div>')
                
        # إزالة البسملة من أول الآية إذا كانت مدمجة في النص لتفادي التكرار البصري
        if verse_num == 1 and surah_id not in (1, 9) and text.startswith(BASMALA):
            text = text[len(BASMALA):].strip()
            
        parts.append(f'<span class="quran-word">{text}</span> <span class="aya-num">﴿{ar_num(verse_num)}﴾</span> ')
        
    return f'<div class="quran-text">{"".join(parts)}</div>'

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
.surah-header { font-family:'Amiri',serif; text-align:center; color:#7a5c12; background: linear-gradient(90deg, transparent, rgba(217,182,74,0.30), transparent); border-top: 1px solid #c9a94f; border-bottom: 1px solid #c9a94f; font-size: 1.6rem; font-weight: 700; padding: 8px 0; margin: 25px 0 10px 0; }
.basmala { font-family:'Amiri Quran','Amiri',serif; text-align:center; color:#3a2e10; font-size:1.7rem; margin: 8px 0 12px 0; }
.quran-text { font-family:'Amiri Quran','Amiri',serif; color:#26200e; font-size:1.75rem; line-height:2.8; text-align:justify; }
.aya-num { color: #a9821f; font-size: 1.25rem; white-space: nowrap; }

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
# Smart Dynamic Popup Dialogue (Supports Multi-Reading & Safe Complete)
# ----------------------------------------------------------------------------
@st.dialog("📝 خيارات الجزء للقراءة والمتابعة")
def show_juz_action_dialog(juz_no, active_list):
    st.write(f"لقد اخترت: **الجزء {ar_num(juz_no)} — {JUZ_NAMES[juz_no-1]}**")
    
    # إذا كان الجزء محجوزاً مسبقاً، نعرض أسماء القراء الحاليين للتنبيه
    if active_list:
        readers_text = " ، ".join([f"[{r[1]}]" for r in active_list])
        st.warning(f"⏳ هذا الجزء يقرأه حالياً كل من: {readers_text}")
    
    # التقسيم التبويبي الداخلي للمنبثق لتسهيل الاختيار
    tab_reserve, tab_complete = st.tabs(["⭐ حجز وقراءة الجزء باسم جديد", "✅ تأكيد إتمام القراءة ومارك كمكتمل"])
    
    with tab_reserve:
        st.write("تريد المشاركة في قراءة هذا الجزء أيضاً؟ اكتب اسمك الكريم بالأسفل:")
        new_name = st.text_input("اسم القارئ الجديد:", key=f"new_name_juz_{juz_no}", placeholder="مثال: محمد علي")
        if st.button("تأكيد حجز الجزء والانتقال للمصحف 🤲", key=f"btn_res_{juz_no}", use_container_width=True):
            if not new_name.strip():
                st.error("الرجاء كتابة الاسم أولاً")
            else:
                add_reading(juz_no, new_name.strip())
                st.session_state["mushaf_juz"] = juz_no
                st.success("تم حجز اسمك بنجاح! تقبل الله منك.")
                st.rerun()
                
    with tab_complete:
        if not active_list:
            st.info("لا توجد قراءات معلقة حالياً لتأكيد إنهاؤها في هذا الجزء.")
        else:
            st.markdown("⚠️ **لتأكيد الإنهاء الآمن:** يرجى كتابة اسمك المسجّل تماماً لحماية القراءات الأخرى ومارك كمنتهي:")
            confirm_name = st.text_input("اكتب اسمك الذي حجزت به سابقاً:", key=f"conf_name_juz_{juz_no}")
            if st.button("نعم، أتممت قراءته كاملاً الحين ✓", key=f"btn_cmp_{juz_no}", use_container_width=True):
                matched_record = next((r for r in active_list if r[1].strip() == confirm_name.strip()), None)
                if matched_record:
                    confirm_done(matched_record[0])
                    st.session_state["mushaf_juz"] = juz_no
                    st.success("جزاك الله خيراً وجعلها في ميزان حسناتها! 🌿")
                    st.rerun()
                else:
                    st.error("❌ الاسم غير مطابق لأي قارئ حالي محجوز باسمه هذا الجزء! يرجى التأكد.")

# ----------------------------------------------------------------------------
# Simplified Native Grid Generation
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
            show_juz_action_dialog(j, actives)
        st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# The Quran Reader Panel (Auto-Synchronized via API)
# ----------------------------------------------------------------------------
selected_juz = st.session_state["mushaf_juz"]
st.markdown(f'<div class="section-title" id="mushaf-view">🕌 مصحف التلاوة المباشر — يعرض الآن (الجزء {ar_num(selected_juz)})</div>', unsafe_allow_html=True)
st.markdown('<div class="mushaf">' + render_juz_html(selected_juz) + '</div>', unsafe_allow_html=True)
