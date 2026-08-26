import os
import sqlite3
import pandas as pd
import streamlit as st
from typing import Dict, List, Tuple, Optional, Any

# =========================================================
# 1. 頁面配置與全局常量定義
# =========================================================
st.set_page_config(
    page_title="全自動姓名學分析器",
    page_icon="🔮",
    layout="centered",
    initial_sidebar_state="collapsed",
)

DB_FILE_NAME = "hanzi_strokes_v2.db"
LEFT_B = "170"
RIGHT_B = "163"

CHAR_EXCEPTIONS = {
    "王": (4, " (王部本字/部首: 4劃)"),
    "黄": (14, " (艹字頭艸部校正: 14劃)"),
    "黃": (12, " (黃部本字: 12劃)"),
    "玉": (5, " (玉部本字: 原劃數5劃不校正)"),
    "成": (7, " (特例預設: 7劃)"),
    "悅": (11, " (忄心部偏旁: +1劃校正，計 4劃)"),
}

WUXING_ORDER = ["木", "火", "土", "金", "水"]
WUXING_TO_INDEX = {w: i for i, w in enumerate(WUXING_ORDER)}
STAR_ORDER = ["比", "食", "財", "官", "印"]

SHENG_MAP = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE_MAP = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

NAYIN_TABLE = {
    "甲子": "金", "乙丑": "金", "壬申": "金", "癸酉": "金", "庚辰": "金", "辛巳": "金",
    "甲午": "金", "乙未": "金", "壬寅": "金", "癸卯": "金", "庚戌": "金", "辛亥": "金",
    "戊辰": "木", "己巳": "木", "壬午": "木", "癸未": "木", "庚寅": "木", "辛卯": "木",
    "戊戌": "木", "己亥": "木", "壬子": "木", "癸丑": "木", "庚申": "木", "辛酉": "木",
    "丙子": "水", "丁丑": "水", "甲申": "水", "乙酉": "水", "壬辰": "水", "癸巳": "水",
    "丙午": "水", "丁未": "水", "甲寅": "水", "乙卯": "水", "壬戌": "水", "癸亥": "水",
    "戊子": "火", "己丑": "火", "丙申": "火", "丁酉": "火", "甲辰": "火", "乙巳": "火",
    "戊午": "火", "己未": "火", "丙寅": "火", "丁卯": "火", "甲戌": "火", "乙亥": "火",
    "庚午": "土", "辛未": "土", "戊寅": "土", "己卯": "土", "丙戌": "土", "丁亥": "土",
    "庚子": "土", "辛丑": "土", "戊申": "土", "己酉": "土", "丙辰": "土", "丁巳": "土"
}

GAN = ["庚", "辛", "壬", "癸", "甲", "乙", "丙", "丁", "戊", "己"]
ZHI = ["申", "酉", "戌", "亥", "子", "丑", "寅", "卯", "辰", "巳", "午", "未"]

PATTERN_MAP = {
    frozenset(["金", "木"]): ("金木局", "剋"),
    frozenset(["水", "火"]): ("水火局", "剋"),
    frozenset(["火", "金"]): ("火金局", "剋"),
    frozenset(["木", "土"]): ("木土局", "剋"),
    frozenset(["土", "水"]): ("土水局", "剋"),
}

PATTERN_DETAILS = {
    "金木局": {
        "advantage": "積極，執行力強，行動派，實踐能力蠻強，先做再說；在家中表現積極，做家事勤快，家中看起來乾淨整齊。",
        "disadvantage": "個性急、壓力感比較大。",
    },
    "水火局": {
        "advantage": "熱心、情緒化、情緒容易上臉，會直接表現出來。",
        "disadvantage": "脾氣不會很好；黑道衝突中水火局者較多。",
        "face": "<b>招風耳</b>：熱心、個性雞婆、具服務熱忱。<br><b>刀眉</b>：個性強，脾氣差，但可能隨社會、家庭打磨改善。",
    },
    "火金局": {
        "advantage": "個性理性，做事前會考慮多。",
        "disadvantage": "行動慢易錯失機會，不會很快下決定，不了解的人會認為其龜毛。",
        "face": "<b>單眼皮</b>：不盡人情。<br><b>雙眼皮</b>：感性。",
    },
    "木土局": {
        "advantage": "若都照規矩來，講好後就不會改變。",
        "disadvantage": "正直（固執、不知變通），個性一板一眼，死腦筋，認定的事情不容易改變，照規矩行事。",
        "special_note": "上下（外在與內在）都是木土局者：講不通、難溝通。",
        "face": "<b>鼻樑直</b>：個性死板，喜歡講場面話。<br><b>鼻樑歪</b>：像政治人物般好講場面話。",
    },
    "土水局": {
        "advantage": "圓融（隨和），樂觀，個性軟，船到橋頭自然直。",
        "disadvantage": "懶、容易喪失自己的立場（不堅持）。",
        "face": "體態較豐滿、圓潤。",
    }
}

PAIR_COMBINATIONS = [
    ("天格", "人格"), ("人格", "地格"), ("人格", "外格"), ("人格", "總格"),
    ("天格", "地格"), ("天格", "外格"), ("天格", "總格"), ("外格", "地格"),
    ("地格", "總格"), ("外格", "總格")
]

STAR_GRID_INTERPRETATIONS = {
    "比": {
        "天格": "有主見、有想法。",
        "地格": "有主見、有想法。",
        "外格": "個性獨立，獨立性強，很早離家賺錢、生活(也可能早婚)。",
        "總格": "年紀大時反而有自己的想法；越老越固執(固執不是壞事)、喜好越鮮明。",
    },
    "食": {
        "天格": "理解能力強、反應快、聰明。",
        "總格": "儲蓄觀念很強、危機意識強；容易找第2專長，一旦錢變少，不安全感增加。",
    },
    "財": {
        "天格": "個性務實，實際衡量事情會看有沒有好處，追求最大利益化(付出多少拿回多少)，當老闆不錯。",
        "外格": "求財在外，待人和氣，對陌生人互動也較客氣。",
        "總格": "分到祖產機會高或父母容易留些財產繼承。 <span class='premise-tag'>【前提：位不能受傷】</span>",
    },
    "官": {
        "天格": "小時候父母管教嚴格，1~12歲比較聽話；重視名聲，責任心強，責任感重。",
        "外格": "女性愛面子、好打扮；男性則外型不錯，身材高大、長相容貌端正。",
        "總格": "不喜亂花錢，用錢謹慎保守，錢花在刀口上(容易省小錢，花大錢)。",
    },
    "印": {
        "天格": "女性外型不會差(含天生好看或後天打扮)，也包含周厚人對其之目光及期待。",
        "地格": "注重人情世故，很會察言觀色，重視禮節，禮貌很會做人。",
        "外格": "朋友多(比較不準確~通常不論)。",
        "總格": "晚年享福，對自己不會太差，比較有享受觀念。",
    },
}

RELATION_TRAITS = {
    "人生總": {"優點": "有風險儲蓄觀念 (喜在工作時找備胎、喜買保險)", "缺點": "勞碌；賺錢方式不輕鬆 (體力活)"},
    "地生總": {"優點": "善藏私房錢", "缺點": "易受家人拖累，老來較孤寂。"},
    "外生總": {"優點": "懂儲蓄、惜財愛物；善體人意，察言觀色", "缺點": "小氣；喜走捷徑。"},
    "地剋總": {"優點": "自我要求高", "缺點": "易寅食卯糧，舉債度日。"},
    "外剋總": {"優點": "心直、厚重老實", "缺點": "少心機不設防，禁不起外在誘因。"},
    "外剋天": {"優點": "具俠士風，抗上擁下，有男子氣概；較喜自我創業。", "缺點": "較獨來獨往，服從性、合群性較佳。"},
    "外剋人": {"優點": "個性上小心，早出社會，異鄉發展", "缺點": "防衛心強。"},
    "外剋地": {"優點": "小心、仔細", "缺點": "主觀強 (不聽別人建議)，自築心強 (防別人)，人際關係不佳。"},
    "總生人": {"優點": "能包裝、促銷自己，有品味能散發出魅力，手腕佳，具享福命", "缺點": "外華內虛，好面子。"},
    "總生地": {"優點": "孝順父母", "缺點": "財洩漏。"},
    "總生外": {"優點": "知人善任，懂用方法達到目的，錢花在刀口上 (大老闆、高階主管)", "缺點": "善用優勢掌握他人，自以為是；喜賺輕鬆財。"},
    "總剋人": {"優點": "勤檢致富，有風險意識", "缺點": "勞碌。"},
    "總剋地": {"優點": "注重子女教育 (願意花時間看小孩功課，關心孩子聯絡簿)", "缺點": "管教子女嚴厲，與子女有代溝。"},
    "總剋外": {"優點": "實行家，不空談，處事積極，重事業，賺錢點子多", "缺點": "財慾心過重，投機心重，財來財去。"},
    "地生天": {"優點": "喜家族觀念 (順從)，敬天畏地，有孝恩，對長上尊崇", "缺點": "無特殊明顯缺點"},
    "地生人": {"優點": "注重人士細節，心思細密，懂禮數，人際圓滿", "缺點": "矯柔，著眼在財利。"},
    "地生外": {"優點": "好相處，人際關係好，真心對人好 (對朋友好)", "缺點": "有求必應，不懂拒絕別人，為人容易受騙 (容易替人作保，做超出自己能力範圍之事)。"},
    "人剋總": {"優點": "易繼承祖產 (父母會留有價值的東西)", "缺點": "易耗財，不知節約，不懂惜福，晚景不佳。"},
    "人剋天": {"優點": "意志堅定，很踏實，不易改變初衷，對事業專注", "缺點": "易得罪人，暗藏賭性，專制不服人。"},
    "人剋地": {"優點": "有口才，言之有務，善分析，腦筋靈活", "缺點": "缺責任感，行事由別人收尾，輕諾不實現 (很會畫餅)。"},
    "人剋外": {"優點": "有藝術眼光，穿著有格調，有品味", "缺點": "佔有慾，意氣用事，易給別人壓力。"},
    "天生人": {"優點": "女生長相斯文，具人緣，畢生於積善之家，善體人意，思維正面", "缺點": "未必有實力，卻有神氣樣，恃寵而驕。"},
    "天生地": {"優點": "重視子女教育 (疼小孩，很願意花錢在孩子身上)、穩重、保守、深思熟慮、設身處地", "缺點": "遇事猶豫不決，長上預干預家中事。"},
    "天生外": {"優點": "喜擴展事業與分支機構，喜搞下線", "缺點": "對親友或部屬卻難得回報。"},
    "天剋人": {"優點": "思維守禮教 (聽話)，負責任", "缺點": "易背長上債，拖累或壓迫。"},
    "天剋地": {"優點": "為人較實在，給人信賴感", "缺點": "手腳或腹部以下容易受傷 (不見血)。"},
    "天剋外": {"優點": "易得好友與部屬相助，長上注重外在行為與舉止形象", "缺點": "易成/易敗/易有外傷 (流血、割傷)。"},
}

# =========================================================
# 2. 注入 CSS 樣式
# =========================================================
def inject_custom_css():
    st.markdown(
        """
    <style>
    .main { background-color: #f8f9fa; }
    .quadrant-container {
        display: grid;
        grid-template-columns: 1fr 2fr;
        gap: 0px;
        background: #ffffff;
        border-radius: 16px;
        box-shadow: 0 10px 25px rgba(126, 87, 194, 0.12);
        overflow: hidden;
        margin: 20px 0;
        border: 2px solid #e0d7f3;
    }
    .quad-box {
        padding: 20px 15px;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .border-right { border-right: 2px solid #7E57C2; }
    .border-bottom { border-bottom: 2px solid #e0e0e0; }
    .inner-divider {
        border-bottom: 1px dashed #e0d7f3;
        width: 100%;
        padding-bottom: 12px;
        margin-bottom: 12px;
    }
    .renge-item {
        background-color: #f3f0ff;
        padding: 12px 10px;
        border-radius: 10px;
        border-left: 4px solid #7E57C2;
        width: 90%;
    }
    .q-title { font-size: 13px; color: #666; font-weight: bold; margin-bottom: 6px; }
    .q-star { 
        font-size: 22px; 
        font-weight: 800; 
        color: #7E57C2;
        background-color: #f3f0ff;
        padding: 2px 14px;
        border-radius: 20px;
        display: inline-block;
        margin-bottom: 4px;
    }
    .q-sub { font-size: 14px; color: #4A5568; font-weight: 600; }
    .q-stroke { font-size: 15px; font-weight: 700; color: #2C3E50; }
    .special-card-container {
        background-color: #fff9c4;
        border: 1px solid #fbc02d;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 20px;
    }
    .special-card-title {
        font-size: 16px;
        font-weight: bold;
        color: #f57f17;
        margin-bottom: 10px;
        border-bottom: 1px dashed #fbc02d;
        padding-bottom: 6px;
    }
    .special-item {
        font-size: 14px;
        color: #333333;
        padding: 6px 0;
        border-bottom: 1px dashed rgba(0,0,0,0.06);
    }
    .alert-tag {
        background-color: #ff5252;
        color: white;
        font-size: 12px;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: bold;
        margin-left: 6px;
    }
    .premise-tag {
        background-color: #d50000;
        color: #ffffff;
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
        display: inline-block;
        margin-right: 6px;
        box-shadow: 0 2px 4px rgba(213, 0, 0, 0.3);
    }
    .star-card {
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .star-title {
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 8px;
        border-bottom: 1px dashed rgba(0,0,0,0.15);
        padding-bottom: 6px;
    }
    .star-item { font-size: 14px; padding: 4px 0; line-height: 1.5; }
    .star-card-bi { background-color: #f3e5f5; border: 1px solid #ce93d8; }
    .star-title-bi { color: #6a1b9a; }
    .star-card-shi { background-color: #e8f5e9; border: 1px solid #a5d6a7; }
    .star-title-shi { color: #2e7d32; }
    .star-card-cai { background-color: #fff8e1; border: 1px solid #ffe082; }
    .star-title-cai { color: #f57f17; }
    .star-card-guan { background-color: #ffebee; border: 1px solid #ef9a9a; }
    .star-title-guan { color: #c62828; }
    .star-card-yin { background-color: #e3f2fd; border: 1px solid #90caf9; }
    .star-title-yin { color: #1565c0; }
    .all-stars-card {
        background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
        border: 2px solid #fb8c00;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
        color: #e65100;
        font-weight: bold;
        font-size: 16px;
        box-shadow: 0 4px 10px rgba(251, 140, 0, 0.2);
    }
    .star-pattern-card {
        background-color: #f4ecf7;
        border: 1.5px solid #8e44ad;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 20px;
    }
    .star-pattern-title {
        font-size: 16px;
        font-weight: bold;
        color: #6c3483;
        margin-bottom: 10px;
        border-bottom: 1px dashed #8e44ad;
        padding-bottom: 6px;
    }
    .relation-card-sheng {
        background-color: rgba(232, 245, 233, 0.65);
        border: 1px solid #a5d6a7;
        border-radius: 12px;
        padding: 15px;
        margin-top: 10px;
        height: 100%;
    }
    .relation-card-ke {
        background-color: rgba(255, 235, 238, 0.65);
        border: 1px solid #ef9a9a;
        border-radius: 12px;
        padding: 15px;
        margin-top: 10px;
        height: 100%;
    }
    .card-title-sheng {
        font-size: 16px;
        font-weight: bold;
        color: #2e7d32;
        margin-bottom: 10px;
        border-bottom: 2px solid #a5d6a7;
        padding-bottom: 5px;
    }
    .card-title-ke {
        font-size: 16px;
        font-weight: bold;
        color: #c62828;
        margin-bottom: 10px;
        border-bottom: 2px solid #ef9a9a;
        padding-bottom: 5px;
    }
    .card-item {
        font-size: 14px;
        color: #333333;
        padding: 8px 0;
        border-bottom: 1px dashed rgba(0,0,0,0.08);
    }
    .trait-good { color: #2e7d32; font-size: 13px; margin-top: 2px; }
    .trait-bad { color: #c62828; font-size: 13px; margin-top: 2px; }
    .pattern-card-ke {
        background-color: #f5eeef;
        border: 2px solid #6c3483;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 15px;
    }
    .pattern-title-ke {
        color: #6c3483;
        font-size: 18px;
        font-weight: bold;
        border-bottom: 1.5px dashed #6c3483;
        padding-bottom: 6px;
        margin-bottom: 10px;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

# =========================================================
# 3. 資料庫查詢與基礎計算
# =========================================================
@st.cache_data(ttl=3600)
def query_char_stroke_from_db(char: str) -> Optional[Tuple[int, str]]:
    if not os.path.exists(DB_FILE_NAME):
        return None
    try:
        with sqlite3.connect(f"file:{DB_FILE_NAME}?mode=ro", uri=True) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT stroke_count, radical_id FROM strokes WHERE char = ?", (char,))
            row = cursor.fetchone()
            if row:
                return int(row[0]), str(row[1])
    except Exception:
        pass
    return None

def get_name_stroke_count(char: str) -> Tuple[int, int, str]:
    if char in CHAR_EXCEPTIONS:
        stroke, note = CHAR_EXCEPTIONS[char]
        return stroke, stroke, note

    db_res = query_char_stroke_from_db(char)
    if not db_res:
        return 0, 0, "無資料庫或無此字記錄"

    base_stroke, rad_id = db_res
    final_stroke = base_stroke
    note = ""

    if rad_id == LEFT_B:
        final_stroke += 6
        note = " (左阝阜部: +6劃)"
    elif rad_id == RIGHT_B:
        final_stroke += 5
        note = " (右阝邑部: +5劃)"
    elif rad_id == "61":  # 心部 (含『心』字本體與『忄』豎心旁)
        if "忄" in char:
            final_stroke += 1
            note = " (忄心部偏旁: +1劃校正，計 4劃)"
        else:
            note = " (心部字本體: 原劃數不變，計 4劃)"
    else:
        rad_offsets = {
            "140": (3, " (艹艸部: +3劃)"),
            "85": (1, " (氵水部: +1劃)"),
            "162": (4, " (辶辵部: +4劃)"),
            "64": (1, " (扌手部: +1劃)"),
            "94": (1, " (犭犬部: +1劃)"),
            "145": (1, " (衤衣部: +1劃)"),
            "113": (1, " (礻示部: +1劃)"),
            "130": (2, " (月肉部: +2劃)"),
        }
        if rad_id in rad_offsets:
            offset, note = rad_offsets[rad_id]
            final_stroke += offset
        elif "艹" in char:
            final_stroke += 3
            note = " (艹艸部: +3劃)"
        elif (rad_id == "96" or "𤣩" in char) and char not in ("玉", "王"):
            final_stroke += 1
            note = " (𤣩玉部偏旁: +1劃)"

    return final_stroke, base_stroke, note

def get_nayin_element(year: int) -> str:
    try:
        gan = GAN[year % 10]
        zhi = ZHI[year % 12]
        return NAYIN_TABLE.get(f"{gan}{zhi}", "未知")
    except Exception:
        return "未知"

def get_gan_zhi_wuxing(num: int) -> Tuple[str, str]:
    GAN_MAP = ["癸", "甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬"]
    ZHI_MAP = ["亥", "子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌"]
    GAN_WUXING = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土", "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}

    gan = GAN_MAP[num % 10]
    zhi = ZHI_MAP[num % 12]
    wuxing = GAN_WUXING[gan]
    return f"{wuxing}{gan}{zhi}", wuxing

def get_star(base_wuxing: str, target_wuxing: str) -> str:
    diff = (WUXING_TO_INDEX[target_wuxing] - WUXING_TO_INDEX[base_wuxing]) % 5
    return STAR_ORDER[diff]

def calculate_pattern(elem1: str, elem2: str) -> Tuple[Optional[str], Optional[str]]:
    if elem1 == elem2:
        return None, None
    return PATTERN_MAP.get(frozenset([elem1, elem2]), (None, None))

# =========================================================
# 4. 分析邏輯模組
# =========================================================
def analyze_special_numbers(grid_strokes: Dict[str, int]) -> List[str]:
    results = []
    for grid_name, num in grid_strokes.items():
        if num in (12, 21, 22):
            results.append(f"🌸 <strong>{grid_name} ({num}劃) - 【桃花數】</strong>：對男性影響力較大，太多容易外遇。")
        elif num % 10 == 7:
            desc = f"🦅 <strong>{grid_name} ({num}劃) - 【孤數】</strong>：能力之展現！"
            if num == 27:
                desc += " <span class='alert-tag'>⚠️ 重點提示</span><br>↳ 能力最強，表現出來比較強勢，離婚率高，賺錢能力好，容易被人攻擊。"
                if grid_name in ("人格", "地格"):
                    desc += " <strong>(男性較果決、狠戾)</strong>"
            elif num == 37:
                desc += " <span class='alert-tag'>⚠️ 重點提示</span><br>↳ 理財數，對數字有概念，可以管錢。"
            results.append(desc)
        elif num in (28, 39):
            desc = f"👑 <strong>{grid_name} ({num}劃) - 【寡數】</strong> <span class='alert-tag'>⚠️ 重點提示</span>：獨裁、個性強硬、霸道但也很會賺錢；對婚姻感情會有殺傷力。"
            if num == 28:
                desc += "<br>↳ 驕傲。"
            elif num == 39:
                desc += "<br>↳ 喜與人保持距離，不好親近。"
                if grid_name == "總格":
                    desc += " <strong>(放在總格：配偶身體不好，容易早離世)</strong>"
            results.append(desc)
        elif num == 24:
            results.append(f"🗣️ <strong>{grid_name} ({num}劃) - 【口舌】</strong>：愛講話、嘮叨；工作上健談，適合從事業務員 / 老師 / 房仲 / 保險員。")
        elif num == 25:
            results.append(f"🍃 <strong>{grid_name} ({num}劃) - 【溫和數】</strong>：能力好、較內斂 (不喜展現給人看)。")
        elif num == 26:
            results.append(f"🌑 <strong>{grid_name} ({num}劃) - 【黑暗數】</strong>：個性悶、話少、有事會憋在心裡 (得憂鬱症比例高)、內向害羞 (不容易衝動、得罪人，較沉穩)。")
        elif num == 44 and grid_name == "總格":
            results.append(f"☠️ <strong>{grid_name} ({num}劃) - 【死亡星】</strong> <span class='alert-tag'>⚠️ 重點提示</span>：個性悶、話少、有事會憋在心裡 (得憂鬱症比例高)、內向害羞 (不容易衝動、得罪人，較沉穩)。")
        elif num == 41:
            results.append(f"🌟 <strong>{grid_name} ({num}劃) - 【領導數】</strong>：有領導魅力，會主動找人聚會 / 聚餐 / 旅遊組團。")
        elif num == 32:
            results.append(f"♟️ <strong>{grid_name} ({num}劃) - 【軍師數】</strong>：不喜出頭、扛責任；幕後指揮，一樣可為領導人。")
    return results

def analyze_five_stars_in_grids(grid_stars: Dict[str, str]) -> Tuple[Dict[str, List[str]], bool]:
    categorized_results = {k: [] for k in STAR_ORDER}

    for grid_name, star in grid_stars.items():
        if grid_name == "人格":
            continue
        if grid_name in STAR_GRID_INTERPRETATIONS.get(star, {}):
            text = STAR_GRID_INTERPRETATIONS[star][grid_name]
            categorized_results[star].append(f"🔹 <strong>{star}在{grid_name[:1]}</strong>─{text}")

    other_stars = set(v for k, v in grid_stars.items() if k != "人格")
    is_all_five_stars = (
        len(other_stars) == 4
        and "比" not in other_stars
        and set(STAR_ORDER) == (other_stars | {"比"})
    )

    return {k: v for k, v in categorized_results.items() if v}, is_all_five_stars

def analyze_special_star_patterns(grid_stars: Dict[str, str], gender: str) -> List[str]:
    other_stars = [star for grid, star in grid_stars.items() if grid != "人格"]
    counts = {s: other_stars.count(s) for s in STAR_ORDER}
    results = []

    if counts["比"] == 1:
        results.append("<b>【1比】</b>：有想法。")
    elif counts["比"] == 2:
        results.append("<b>【2比】</b>：很有想法、主見，有點固執。")
    elif counts["比"] >= 3:
        results.append("<b>【3比/4比】</b>：太重視自我(眼裡沒有別人)、太過在乎自己；男女人際關係不佳(尤其是男女之間的感情) / 本氣太重：其他地方氣不均衡、突發病變/癌症；比太多=錢少，財留不住，沒那麼旺，看不到好處。")

    if counts["比"] == 2 and counts["財"] == 2:
        results.append("<b>【比肩劫財】</b> <span class='premise-tag'>【前提條件：2比2財】</span>：財被比幹掉，錢被人幹掉或花掉，留不住。")

    if counts["比"] == 2 and counts["食"] == 2:
        results.append("<b>【比劫生食傷】</b> <span class='premise-tag'>【前提條件：2比2食】</span>：自己靠自己生出才華，通常成為專業人士(師字輩)。")

    if counts["比"] == 2 and counts["印"] == 2:
        results.append("<b>【印比用神】</b> <span class='premise-tag'>【前提條件：2比2印】</span>：喜歡賺投資財(有錢時很有錢、沒錢時沒錢)。")

    if counts["食"] >= 1:
        if gender == "女":
            if counts["食"] == 2:
                results.append("<b>【2食女】</b>：很愛付出、很愛做事，能幹(努力性質很高)；(聰明才智)累、勞碌、辛苦；但不要碎念嘮叨，否則付出容易被打折扣；多處幹部、主管、老闆娘。")
            elif counts["食"] >= 3:
                results.append("<b>【3食女】</b>：更愛付出、更累、更勞碌；但洩氣太多，對身體不好，身體差、毛病多。")
        else:
            results.append("<b>【男生食多】</b>：聰明、腦筋轉得快、理解能力佳。")
            if counts["食"] == 2:
                results.append("<b>【2食男】</b>：因為聰明，所以懶，有方法、有效率地做事，找輕鬆的工作。")
            elif counts["食"] >= 3:
                results.append("<b>【3食男】</b>：非常聰明、有本事；但洩氣太重，身體差(須注重身體)。")

    if counts["印"] >= 1 and counts["食"] >= 1 and (counts["印"] + counts["食"] >= 3):
        if counts["印"] >= 2 and counts["食"] == 2:
            tag = "<b>【梟印奪食 (2印2食)】</b> <span class='premise-tag'>【前提條件：2印2食】</span>："
        elif counts["印"] >= 2:
            tag = "<b>【梟印奪食 (1食多印)】</b> <span class='premise-tag'>【前提條件：1食多印】</span>："
        else:
            tag = "<b>【梟印奪食 (1印多食)】</b> <span class='premise-tag'>【前提條件：1印多食】</span>："

        gender_desc = "男性─膽大容易做蠢事、沒智商、沒理智，容易走偏路；" if gender == "男" else "女性─(理智被蓋掉，事情會往負面方向思考)容易想不開、負能量強，自殺風險高；"
        common_desc = "印會把食傷蓋掉，印對食傷造成傷害➔付出不被肯定、不被看見。不利於工作事業；易受騙，做錯判斷；癌症機率高(病變、腫瘤)。"
        results.append(f"{tag}{gender_desc}{common_desc}")

    shang_guan, zheng_guan = counts["食"], counts["官"]
    if (shang_guan >= 1 and zheng_guan >= 1 and (shang_guan + zheng_guan >= 3)) or (shang_guan == 2 and zheng_guan == 2):
        if shang_guan == 2 and zheng_guan == 2:
            tag = "<b>【傷官見官 (2食2官)】</b> <span class='premise-tag'>【前提條件：2食2官】</span>："
        elif shang_guan >= 2:
            tag = "<b>【傷官見官 (多食1官)】</b> <span class='premise-tag'>【前提條件：多食1官】</span>："
        else:
            tag = "<b>【傷官見官 (1食多官)】</b> <span class='premise-tag'>【前提條件：1食多官】</span>："

        desc = f"{tag}男性─食傷把官剋掉➔個性衝動、容易起衝突、意外受傷，留心官司糾紛。" if gender == "男" else f"{tag}女性─官代表丈夫，傷到丈夫➔容易離婚。"
        results.append(desc)

    if counts["財"] == 2:
        results.append("<b>【2財】</b>：有錢人比例高、愛賺錢且企圖心強、注重待遇；可能找副業或斜槓、投資；愛當老闆(較實際)，純粹賺錢，領固定薪者少；但易血光、意外受傷或突發疾病，即便癌症也是來得快，致死快。")
    elif counts["財"] >= 3:
        desc = "<b>【3財】</b>：更愛賺錢，更容易死得快。"
        if counts["印"] == 1:
            desc += "<br>↳ <b>【3財1印】</b> <span class='premise-tag'>【前提條件：3財1印】</span>：容易有金錢糾紛，犯小人(注意財不露白)。"
        results.append(desc)

    if counts["財"] == 2 and counts["食"] == 2:
        results.append("<b>【食傷生財】</b> <span class='premise-tag'>【前提條件：2財2食】</span>：用智慧賺錢，常見為生意人，付出多少回收多少，成本效益高；很會畫餅、賣東西。")

    if counts["財"] == 2 and counts["官"] == 2:
        results.append("<b>【財官雙美】</b> <span class='premise-tag'>【前提條件：2財2官】</span>：喜歡當老大，財會升官，錢越多，別人越看得起；常見為藝人、名人。")

    if counts["官"] == 2:
        results.append("<b>【2官】</b>：做事盡心盡力，責任感重，責任心強；管理受約束，對自己要求太高導致壓力大；中規中矩、使命感強、壓力感重。")
    elif counts["官"] >= 3:
        results.append("<b>【3官】</b>：膽子小，責任感發揮不出來，很多是因為害怕；男女皆重視外表、愛打扮，外表光鮮但不見得真有錢。")

    if counts["官"] == 2 and counts["印"] == 2:
        results.append("<b>【2官2印】</b> <span class='premise-tag'>【前提條件：2官2印】</span>：因官印相生，也喜歡當主管、當老大、中小企業老闆，但不一定有錢；或公務員(職位較高)、軍公教、個人工作室。")

    if counts["官"] == 2 and (counts["比"] in (1, 2)) and counts["財"] == 0:
        results.append(f"<b>【雙官帶比 (2官{counts['比']}比)】</b> <span class='premise-tag'>【前提條件：2官帶比(2官1比或2官2比)且無財】</span>：好面子、好勝心強、喜出風頭，容易有當老闆的念頭，但沒有財星，所以容易賺不到錢；容易因為追捧而逾越法律界限。")

    if counts["印"] >= 1:
        if gender == "女":
            desc = "<b>【印女】</b>：群眾對其期待及目光、從小受人關注、漂亮、氣質不錯。"
            if counts["印"] == 2:
                desc += "<br>↳ <b>【2印女】</b>：因群眾目光導致壓力變大，易鑽牛角尖、思想侷促，精神壓力大、鬱結於心。"
            elif counts["印"] >= 3:
                desc += "<br>↳ <b>【3印女】</b>：刁鑽、個性難搞、容易難到他人或事物之缺點；超過30歲婚姻感情不好，出狀況比率高或不婚主義；容易介入別人感情。"
        else:
            desc = "<b>【印男】</b>：貴人、靠山很多➔懦弱、懶惰、膽大。"
            if counts["印"] == 2:
                desc += "<br>↳ <b>【2印男】</b>：懶惰又膽大、喜當老闆、玩股票，賺投機財；若走黑道，則大膽敢做事(有個特點：我做到這個程度就夠好~)"
            elif counts["印"] >= 3:
                desc += "<br>↳ <b>【3印男】</b>：更懶更膽大，優秀者很優秀，沒用者沒用；社會地位高。"
        results.append(desc)

    return results

def get_single_relation(elem1: str, elem2: str) -> Tuple[str, str]:
    if elem1 == elem2:
        return "比和", "⇄"
    if SHENG_MAP.get(elem1) == elem2:
        return "相生", "➔"
    if SHENG_MAP.get(elem2) == elem1:
        return "相生", "⬅"
    if KE_MAP.get(elem1) == elem2:
        return "相剋", "➔"
    return "相剋", "⬅"

def analyze_all_grid_relations(grid_elements: Dict[str, str]) -> List[Dict[str, Any]]:
    grid_abbr = {"天格": "天", "人格": "人", "地格": "地", "外格": "外", "總格": "總"}
    results = []

    for g1, g2 in PAIR_COMBINATIONS:
        e1, e2 = grid_elements[g1], grid_elements[g2]
        rel_type, arrow = get_single_relation(e1, e2)

        if rel_type == "比和":
            desc = f"{g1}【{e1}】 ⇄ {g2}【{e2}】（同氣比和）"
            key = None
        elif arrow == "➔":
            desc = f"{g1}【{e1}】 ➔ {g2}【{e2}】"
            key = f"{grid_abbr[g1]}{rel_type[1]}{grid_abbr[g2]}"
        else:
            desc = f"{g2}【{e2}】 ➔ {g1}【{e1}】"
            key = f"{grid_abbr[g2]}{rel_type[1]}{grid_abbr[g1]}"

        traits = RELATION_TRAITS.get(key, {})
        results.append({
            "g1": g1, "g2": g2, "e1": e1, "e2": e2,
            "type": rel_type, "desc": desc,
            "good": traits.get("優點"), "bad": traits.get("缺點"),
        })
    return results

# =========================================================
# 5. 主程式入口 (Streamlit UI)
# =========================================================
def main():
    inject_custom_css()

    st.title("🔮 全自動姓名學分析器")
    st.caption("輸入姓名、出生年與性別，自動計算姓名學筆畫、五格干支、五星特殊格局與格局辨性格面相分析")

    if not os.path.exists(DB_FILE_NAME):
        st.error(f"⚠️ 找不到資料庫檔案 `{DB_FILE_NAME}`！請確認資料庫已放置於同目錄下。")
        return

    col1, col2 = st.columns(2)
    with col1:
        surname = st.text_input("請輸入姓氏", placeholder="例如：張", key="input_surname")
    with col2:
        given_name = st.text_input("請輸入名字", placeholder="例如：三丰", key="input_given_name")

    col3, col4 = st.columns(2)
    with col3:
        birth_year = st.text_input("請輸入出生西元年", placeholder="例如：1988 或 1990", key="input_birth_year")
    with col4:
        gender = st.radio("請選擇性別", ["男", "女"], horizontal=True, key="input_gender")

    if st.button("✨ 開始分析姓名", type="primary", use_container_width=True):
        s_clean, g_clean = surname.strip(), given_name.strip()
        if not s_clean or not g_clean:
            st.warning("⚠️ 姓氏與名字皆不能為空！")
            st.session_state["analyzed"] = False
        else:
            st.session_state["analyzed"] = True
            st.session_state["surname"] = s_clean
            st.session_state["given_name"] = g_clean
            st.session_state["birth_year"] = birth_year.strip()
            st.session_state["gender"] = gender

    if st.session_state.get("analyzed", False):
        s_val = st.session_state["surname"]
        g_val = st.session_state["given_name"]
        by_val = st.session_state["birth_year"]
        gender_val = st.session_state["gender"]

        birth_year_num = None
        if by_val.isdigit():
            birth_year_num = int(by_val)
            if birth_year_num < 200:
                birth_year_num += 1911

        full_name = s_val + g_val
        st.divider()

        surname_strokes = [get_name_stroke_count(c)[0] for c in s_val]
        name_strokes = [get_name_stroke_count(c)[0] for c in g_val]
        s_len, n_len = len(surname_strokes), len(name_strokes)

        if s_len == 1 and n_len == 2:
            A, (B, C) = surname_strokes[0], name_strokes
            name_type, tiange, renge, dige, waige, zongge = "單姓複名", A + 1, A + B, B + C, C + 1, A + B + C
        elif s_len == 1 and n_len == 1:
            A, B = surname_strokes[0], name_strokes[0]
            name_type, tiange, renge, dige, waige, zongge = "單姓單名", A + 1, A + B, B + 1, 2, A + B
        elif s_len == 2 and n_len == 2:
            (A, B), (C, D) = surname_strokes, name_strokes
            name_type, tiange, renge, dige, waige, zongge = "複姓複名", A + B, B + C, C + D, A + D, A + B + C + D
        elif s_len == 2 and n_len == 1:
            (A, B), C = surname_strokes, name_strokes[0]
            name_type, tiange, renge, dige, waige, zongge = "複姓單名", A + B, B + C, C + 1, A + 1, A + B + C
        else:
            st.error("⚠️ 目前僅支援 2~4 字的姓名組合。")
            return

        tiange_str, t_wx = get_gan_zhi_wuxing(tiange)
        renge_str, r_wx = get_gan_zhi_wuxing(renge)
        dige_str, d_wx = get_gan_zhi_wuxing(dige)
        waige_str, w_wx = get_gan_zhi_wuxing(waige)
        zongge_str, z_wx = get_gan_zhi_wuxing(zongge)

        grid_elements = {"天格": t_wx, "人格": r_wx, "地格": d_wx, "外格": w_wx, "總格": z_wx}
        grid_strokes = {"天格": tiange, "人格": renge, "地格": dige, "外格": waige, "總格": zongge}

        t_star = get_star(r_wx, t_wx)
        d_star = get_star(r_wx, d_wx)
        w_star = get_star(r_wx, w_wx)
        z_star = get_star(r_wx, z_wx)

        grid_stars = {"天格": t_star, "人格": "比", "地格": d_star, "外格": w_star, "總格": z_star}

        tab1, tab2, tab3 = st.tabs(["📊 十字五格五星盤", "🎭 五行格局與性格面相", "✍️ 筆劃解析明細"])

        with tab1:
            year_info = f"｜{by_val}年生" if by_val else ""
            st.subheader(f"👤 {full_name}（{gender_val}性｜{name_type}{year_info}）")

            html_content = f"""
            <div class="quadrant-container">
                <div class="quad-box border-right border-bottom" style="background-color: #fafafa;">
                    <div style="color: #ccc; font-size: 13px;">（全格局比較）</div>
                </div>
                <div class="quad-box border-bottom" style="padding: 15px 10px;">
                    <div class="inner-divider">
                        <div class="q-title">【天格】</div>
                        <div class="q-star">{t_star}</div>
                        <div class="q-sub"><span class="q-stroke">{tiange}劃</span>｜{tiange_str}</div>
                    </div>
                    <div class="inner-divider renge-item">
                        <div class="q-title" style="color:#7E57C2;">★ 【人格】(核心)</div>
                        <div class="q-sub" style="color:#5e35b1; margin-top: 6px;"><span class="q-stroke">{renge}劃</span>｜{renge_str}</div>
                    </div>
                    <div>
                        <div class="q-title">【地格】</div>
                        <div class="q-star">{d_star}</div>
                        <div class="q-sub"><span class="q-stroke">{dige}劃</span>｜{dige_str}</div>
                    </div>
                </div>
                <div class="quad-box border-right">
                    <div class="q-title">【外格】</div>
                    <div class="q-star">{w_star}</div>
                    <div class="q-sub"><span class="q-stroke">{waige}劃</span>｜{waige_str}</div>
                </div>
                <div class="quad-box">
                    <div class="q-title">【總格】</div>
                    <div class="q-star">{z_star}</div>
                    <div class="q-sub"><span class="q-stroke">{zongge}劃</span>｜{zongge_str}</div>
                </div>
            </div>
            """
            st.markdown(html_content, unsafe_allow_html=True)

            special_analysis = analyze_special_numbers(grid_strokes)
            if special_analysis:
                st.markdown("#### 🔢 五格靈數 / 特殊數解析")
                items_html = "".join(f'<div class="special-item">{item}</div>' for item in special_analysis)
                st.markdown(
                    f"""
                    <div class="special-card-container">
                        <div class="special-card-title">✨ 格局特殊筆劃提示</div>
                        {items_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            star_analysis, is_all_five = analyze_five_stars_in_grids(grid_stars)
            st.markdown("#### ⭐ 五星於五格之意義解析")

            if is_all_five:
                st.markdown('<div class="all-stars-card">✨ 【五星俱全】</div>', unsafe_allow_html=True)

            if star_analysis:
                star_style_map = {
                    "比": ("star-card-bi", "star-title-bi", "💜 【比】解析"),
                    "食": ("star-card-shi", "star-title-shi", "💚 【食】解析"),
                    "財": ("star-card-cai", "star-title-cai", "💛 【財】解析"),
                    "官": ("star-card-guan", "star-title-guan", "❤️ 【官】解析"),
                    "印": ("star-card-yin", "star-title-yin", "💙 【印】解析"),
                }
                for star_key, items in star_analysis.items():
                    card_cls, title_cls, title_txt = star_style_map[star_key]
                    items_html = "".join(f'<div class="star-item">{item}</div>' for item in items)
                    st.markdown(
                        f"""
                        <div class="star-card {card_cls}">
                            <div class="star-title {title_cls}">{title_txt}</div>
                            {items_html}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            special_patterns = analyze_special_star_patterns(grid_stars, gender_val)
            if special_patterns:
                st.markdown("#### 🔮 五星之特殊格局解析")
                pattern_items_html = "".join(f'<div class="special-item">{p}</div>' for p in special_patterns)
                st.markdown(
                    f"""
                    <div class="star-pattern-card">
                        <div class="star-pattern-title">🌌 命中特殊格局與多星傾向 ({gender_val}性專屬視角)</div>
                        {pattern_items_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("#### 🔄 各格五行生剋解析")
            all_relations = analyze_all_grid_relations(grid_elements)
            sheng_list = [r for r in all_relations if r["type"] in ("相生", "比和")]
            ke_list = [r for r in all_relations if r["type"] == "相剋"]

            col_left, col_right = st.columns(2)

            with col_left:
                sheng_blocks = []
                for r in sheng_list:
                    item_html = f'<div class="card-item">🟢 <strong>{r["desc"]}</strong>'
                    if r["good"]:
                        item_html += f'<div class="trait-good">👍 優點：{r["good"]}</div>'
                    if r["bad"]:
                        item_html += f'<div class="trait-bad">👎 缺點：{r["bad"]}</div>'
                    sheng_blocks.append(item_html + '</div>')

                sheng_items_html = "".join(sheng_blocks) or '<div class="card-item" style="color:#888;">無相生關係</div>'
                st.markdown(
                    f"""
                    <div class="relation-card-sheng">
                        <div class="card-title-sheng">🟢 相生 / 比和關係 ({len(sheng_list)})</div>
                        {sheng_items_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with col_right:
                ke_blocks = []
                for r in ke_list:
                    item_html = f'<div class="card-item">🔴 <strong>{r["desc"]}</strong>'
                    if r["good"]:
                        item_html += f'<div class="trait-good">👍 優點：{r["good"]}</div>'
                    if r["bad"]:
                        item_html += f'<div class="trait-bad">👎 缺點：{r["bad"]}</div>'
                    ke_blocks.append(item_html + '</div>')

                ke_items_html = "".join(ke_blocks) or '<div class="card-item" style="color:#888;">無相剋關係</div>'
                st.markdown(
                    f"""
                    <div class="relation-card-ke">
                        <div class="card-title-ke">🔴 相剋關係 ({len(ke_list)})</div>
                        {ke_items_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with tab2:
            st.markdown("##### 🎭 五行對剋格局「格局辨性格」與面相對照")

            ext_pattern, ext_type = calculate_pattern(t_wx, r_wx)
            int_pattern, int_type = calculate_pattern(r_wx, d_wx)
            is_double = (ext_pattern is not None) and (ext_pattern == int_pattern)

            nayin_elem = get_nayin_element(birth_year_num) if birth_year_num else "未提供或無法解析"

            st.info(
                f"**出生年納音五行**：{birth_year_num if birth_year_num else '未知'} 年（{nayin_elem}） "
                f"| **雙格局判定**：{'是 (雙' + str(ext_pattern) + ')' if is_double else '否'}"
            )

            st.markdown("---")

            def render_pattern_card(pattern_name: str, position_label: str):
                if not pattern_name:
                    return
                info = PATTERN_DETAILS.get(pattern_name, {})

                title_suffix = f"（雙{pattern_name}）" if is_double else ""

                content_html = f"""
                <div class="pattern-card-ke">
                    <div class="pattern-title-ke">🎴 {position_label}格局：{pattern_name} {title_suffix}</div>
                    <p><b>👍 優點</b>：{info.get('advantage', '無')}</p>
                    <p><b>👎 缺點</b>：{info.get('disadvantage', '無')}</p>
                """
                if "special_note" in info:
                    content_html += f"<p><b>⚠️ 特殊格局備註</b>：{info['special_note']}</p>"
                if "face" in info:
                    content_html += f"<p><b>👤 面相特徵</b>：<br>{info['face']}</p>"
                content_html += "</div>"
                st.markdown(content_html, unsafe_allow_html=True)

            if ext_pattern:
                render_pattern_card(ext_pattern, "外在 (天-人)")
                if ext_pattern == "水火局":
                    st.markdown("##### 🌊🔥 外在水火局調候機制 (對照「六十納音表」出生年)")
                    if nayin_elem == "木":
                        st.warning("• **出生年為木**：木生火，性格可能火氣更大。")
                    elif nayin_elem == "土":
                        st.info("• **出生年為土**：火生土，脾氣不會發的那麼快，不能溝通者才會發脾氣。")
                    elif nayin_elem == "水":
                        st.success("• **出生年為水**：格局中有2水，火被剋掉了，沒脾氣就不會發火了。")
                    else:
                        st.write(f"• **出生年為 {nayin_elem}**：一般水火能量推演。")

            if int_pattern:
                render_pattern_card(int_pattern, "內在 (人-地)")

            if not ext_pattern and not int_pattern:
                st.success("目前天格與人格（外在）、人格與地格（內在）之間未構成五行相剋格局。")

        with tab3:
            st.markdown("##### ✍️ 漢字姓名學筆劃詳細解析")

            records = []
            for char, role in [(c, "姓氏") for c in s_val] + [(c, "名字") for c in g_val]:
                final_s, base_s, note = get_name_stroke_count(char)
                records.append({
                    "類別": role,
                    "漢字": char,
                    "傳統筆劃 (校正後)": f"{final_s} 劃",
                    "原始筆劃": f"{base_s} 劃",
                    "部首校正說明": note.strip() if note else "無校正",
                })

            st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)

            with st.expander("ℹ️ 關於姓名學筆劃計算規則說明"):
                st.write(
                    "本系統筆劃採用傳統姓名學部首校正標準：\n"
                    "• **心部**：『心』字本體算 4 劃；帶有『忄』豎心旁之漢字進行 +1 劃校正（補足心部 4 劃標準）。\n"
                    "• **其他部首**：氵水部（+1劃）、艹艸部（+3劃）、左阝阜部（+6劃）、右阝邑部（+5劃）...等。\n"
                    "• **特例字**：『王』字為王部本字固定計 4 劃；『玉』字算 5 劃。其餘帶有『𤣩』玉部偏旁之漢字進行 +1 劃校正。『成』字預設為 7 劃。"
                )

if __name__ == "__main__":
    main()