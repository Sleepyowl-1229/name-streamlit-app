import os
import sqlite3
import pandas as pd
import streamlit as st

# =========================================================
# 1. 頁面基本配置
# =========================================================
st.set_page_config(
    page_title="全自動姓名學分析器",
    page_icon="🔮",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =========================================================
# 2. 美工 CSS: 十字象限網格樣式設計
# =========================================================
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
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# 3. 核心計算邏輯演算法
# =========================================================
DB_FILE_NAME = "hanzi_strokes_v2.db"

CHAR_EXCEPTIONS = {
    "黄": (14, " (艹字頭艸部校正: 14劃)"),
    "黃": (12, " (黃部本字: 12劃)"),
}

LEFT_B = "170"  # 阜部 (左阝)
RIGHT_B = "163"  # 邑部 (右阝)

WUXING_ORDER = ["木", "火", "土", "金", "水"]
WUXING_TO_INDEX = {w: i for i, w in enumerate(WUXING_ORDER)}
STAR_ORDER = ["比", "食", "財", "官", "印"]


def get_name_stroke_count(char: str) -> tuple[int, int, str]:
    if char in CHAR_EXCEPTIONS:
        stroke, note = CHAR_EXCEPTIONS[char]
        return stroke, stroke, note

    if not os.path.exists(DB_FILE_NAME):
        return 0, 0, "無資料庫"

    conn = sqlite3.connect(DB_FILE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT stroke_count, radical_id FROM strokes WHERE char = ?", (char,)
    )
    result = cursor.fetchone()
    conn.close()

    if not result:
        return 0, 0, "無資料"

    base_stroke, rad_id = result[0], result[1]
    final_stroke = base_stroke
    note = ""

    if rad_id == LEFT_B:
        final_stroke += 6
        note = " (左阝阜部: +6劃)"
    elif rad_id == RIGHT_B:
        final_stroke += 5
        note = " (右阝邑部: +5劃)"
    else:
        if rad_id == "140" or "艹" in char:
            final_stroke = base_stroke + 3
            note = " (艹艸部: +3劃)"
        elif rad_id == "85":
            final_stroke = base_stroke + 1
            note = " (氵水部: +1劃)"
        elif rad_id == "96" or "王" in char or "𤣩" in char:
            final_stroke = base_stroke + 1
            note = " (𤣩玉部: +1劃)"
        elif rad_id == "162":
            final_stroke = base_stroke + 4
            note = " (辶辵部: +4劃)"
        elif rad_id == "64":
            final_stroke = base_stroke + 1
            note = " (扌手部: +1劃)"
        elif rad_id == "61":
            final_stroke = base_stroke + 1
            note = " (忄心部: +1劃)"
        elif rad_id == "94":
            final_stroke = base_stroke + 1
            note = " (犭犬部: +1劃)"
        elif rad_id == "145":
            final_stroke = base_stroke + 1
            note = " (衤衣部: +1劃)"
        elif rad_id == "113":
            final_stroke = base_stroke + 1
            note = " (礻示部: +1劃)"
        elif rad_id == "130":
            final_stroke = base_stroke + 2
            note = " (月肉部: +2劃)"

    return final_stroke, base_stroke, note


def get_gan_zhi_wuxing(num: int) -> tuple[str, str]:
    tiangan_map = {
        1: "甲", 2: "乙", 3: "丙", 4: "丁", 5: "戊",
        6: "己", 7: "庚", 8: "辛", 9: "壬", 0: "癸"
    }
    gan = tiangan_map[num % 10]

    wuxing_map = {
        "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
        "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"
    }
    wuxing = wuxing_map[gan]

    dizhi_map = {
        1: "子", 2: "丑", 3: "寅", 4: "卯", 5: "辰", 6: "巳",
        7: "午", 8: "未", 9: "申", 10: "酉", 11: "戌", 0: "亥"
    }
    zhi = dizhi_map[num % 12]

    return f"{wuxing}{gan}{zhi}", wuxing


def get_star(base_wuxing: str, target_wuxing: str) -> str:
    base_idx = WUXING_TO_INDEX[base_wuxing]
    target_idx = WUXING_TO_INDEX[target_wuxing]
    diff = (target_idx - base_idx) % 5
    return STAR_ORDER[diff]


# =========================================================
# 4. Streamlit 主視覺介面
# =========================================================
def main():
    st.title("🔮 全自動姓名學分析器")
    st.caption("輸入姓名，自動計算姓名學筆畫、五格干支與五星關係盤")

    if not os.path.exists(DB_FILE_NAME):
        st.error(
            f"⚠️ 找不到資料庫檔案 `{DB_FILE_NAME}`！請確認資料庫已放置於同目錄下。"
        )
        return

    # 輸入區塊
    col1, col2 = st.columns(2)
    with col1:
        surname = st.text_input("請輸入姓氏", placeholder="例如：張")
    with col2:
        given_name = st.text_input("請輸入名字", placeholder="例如：三丰")

    if st.button("✨ 開始分析姓名", type="primary", use_container_width=True):
        surname = surname.strip()
        given_name = given_name.strip()

        if not surname or not given_name:
            st.warning("⚠️ 姓氏與名字皆不能為空！")
            return

        full_name = surname + given_name
        st.divider()

        # 計算筆劃
        surname_strokes = [get_name_stroke_count(c)[0] for c in surname]
        name_strokes = [get_name_stroke_count(c)[0] for c in given_name]

        s_len, n_len = len(surname_strokes), len(name_strokes)

        if s_len == 1 and n_len == 2:
            A, (B, C) = surname_strokes[0], name_strokes
            name_type, tiange, renge, dige, waige, zongge = (
                "單姓複名", A + 1, A + B, B + C, C + 1, A + B + C
            )
        elif s_len == 1 and n_len == 1:
            A, B = surname_strokes[0], name_strokes[0]
            name_type, tiange, renge, dige, waige, zongge = (
                "單姓單名", A + 1, A + B, B + 1, 2, A + B
            )
        elif s_len == 2 and n_len == 2:
            (A, B), (C, D) = surname_strokes, name_strokes
            name_type, tiange, renge, dige, waige, zongge = (
                "複姓複名", A + B, B + C, C + D, A + D, A + B + C + D
            )
        elif s_len == 2 and n_len == 1:
            (A, B), C = surname_strokes, name_strokes[0]
            name_type, tiange, renge, dige, waige, zongge = (
                "複姓單名", A + B, B + C, C + 1, A + 1, A + B + C
            )
        else:
            st.error("⚠️ 目前僅支援 2~4 字的姓名組合。")
            return

        # 解析干支與五星
        tiange_str, t_wx = get_gan_zhi_wuxing(tiange)
        renge_str, r_wx = get_gan_zhi_wuxing(renge)
        dige_str, d_wx = get_gan_zhi_wuxing(dige)
        waige_str, w_wx = get_gan_zhi_wuxing(waige)
        zongge_str, z_wx = get_gan_zhi_wuxing(zongge)

        tab1, tab2 = st.tabs(["📊 十字五格五星盤", "✍️ 筆劃解析明細"])

        # 分頁一：十字盤
        with tab1:
            st.subheader(f"👤 {full_name}（{name_type}）")

            t_star = get_star(r_wx, t_wx)
            d_star = get_star(r_wx, d_wx)
            w_star = get_star(r_wx, w_wx)
            z_star = get_star(r_wx, z_wx)

            html_content = (
                '<div class="quadrant-container">'
                '<div class="quad-box border-right border-bottom" style="background-color: #fafafa;"><div style="color: #ccc; font-size: 13px;">（左上留空）</div></div>'
                '<div class="quad-box border-bottom" style="padding: 15px 10px;">'
                f'<div class="inner-divider"><div class="q-title">【天格】</div><div class="q-star">{t_star}</div><div class="q-sub"><span class="q-stroke">{tiange}劃</span>｜{tiange_str}</div></div>'
                f'<div class="inner-divider renge-item"><div class="q-title" style="color:#7E57C2;">★ 【人格】(核心)</div><div class="q-sub" style="color:#5e35b1; margin-top: 6px;"><span class="q-stroke">{renge}劃</span>｜{renge_str}</div></div>'
                f'<div><div class="q-title">【地格】</div><div class="q-star">{d_star}</div><div class="q-sub"><span class="q-stroke">{dige}劃</span>｜{dige_str}</div></div>'
                "</div>"
                f'<div class="quad-box border-right"><div class="q-title">【外格】</div><div class="q-star">{w_star}</div><div class="q-sub"><span class="q-stroke">{waige}劃</span>｜{waige_str}</div></div>'
                f'<div class="quad-box"><div class="q-title">【總格】</div><div class="q-star">{z_star}</div><div class="q-sub"><span class="q-stroke">{zongge}劃</span>｜{zongge_str}</div></div>'
                "</div>"
            )

            st.markdown(html_content, unsafe_allow_html=True)

        # ---------------------------------------------------------
        # 分頁二：筆劃詳細說明 (方案 2-B: 清單表格風格)
        # ---------------------------------------------------------
        with tab2:
            st.markdown("##### ✍️ 漢字姓名學筆劃詳細解析")

            records = []
            for char, role in [(c, "姓氏") for c in surname] + [
                (c, "名字") for c in given_name
            ]:
                final_s, base_s, note = get_name_stroke_count(char)
                records.append(
                    {
                        "類別": role,
                        "漢字": char,
                        "傳統筆劃 (校正後)": f"{final_s} 劃",
                        "原始筆劃": f"{base_s} 劃",
                        "部首校正說明": note.strip() if note else "無校正",
                    }
                )

            df = pd.DataFrame(records)
            st.dataframe(df, use_container_width=True, hide_index=True)

    # 底部說明
    with st.expander("ℹ️ 關於姓名學筆劃計算規則說明"):
        st.write(
            "本系統筆劃採用傳統姓名學部首校正標準（例如 氵水部以4劃計、艹艸部以6劃計、左阝阜部以14劃計、右阝邑部以12劃計...等），結合 Unicode Unihan 資料庫全自動檢索計算。"
        )


if __name__ == "__main__":
    main()