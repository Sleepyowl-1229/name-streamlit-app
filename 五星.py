import os
import sqlite3
import urllib.request
import zipfile

# 設定檔名與下載網址
UNIHAN_ZIP_URL = "https://www.unicode.org/Public/UNIDATA/Unihan.zip"
ZIP_FILE_NAME = "Unihan.zip"
TARGET_TXT_FILE = "Unihan_IRGSources.txt"
DB_FILE_NAME = "hanzi_strokes_v2.db"

# =========================================================
# 特殊字/特定字形姓名學筆畫覆蓋 (優先權最高)
# =========================================================
CHAR_EXCEPTIONS = {
    "黄": (14, " (艹字頭艸部校正: 14劃)"),
    "黃": (12, " (黃部本字: 12劃)"),
}

LEFT_B = "170"  # 阜部 (左阝)
RIGHT_B = "163"  # 邑部 (右阝)


def download_and_extract_unihan():
    """下載 Unihan.zip 並解壓縮出指定的 TXT 檔"""
    if not os.path.exists(TARGET_TXT_FILE):
        if not os.path.exists(ZIP_FILE_NAME):
            print("正在從 Unicode 官方下載 Unihan.zip...")
            req = urllib.request.Request(
                UNIHAN_ZIP_URL, headers={"User-Agent": "Mozilla/5.0"}
            )
            with (
                urllib.request.urlopen(req) as response,
                open(ZIP_FILE_NAME, "wb") as out_file,
            ):
                out_file.write(response.read())
            print("下載完成！")

        print(f"正在解壓縮 {TARGET_TXT_FILE}...")
        with zipfile.ZipFile(ZIP_FILE_NAME, "r") as zip_ref:
            zip_ref.extract(TARGET_TXT_FILE)
        print("解壓縮完成！")


def init_sqlite_db():
    """建立包含部首資訊的 SQLite 資料庫"""
    conn = sqlite3.connect(DB_FILE_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strokes (
            char TEXT PRIMARY KEY,
            stroke_count INTEGER,
            radical_id TEXT
        )
    """)
    conn.commit()
    return conn, cursor


def parse_and_import_to_db():
    """解析 kTotalStrokes 與 kRSUnicode 部首資訊並匯入 SQLite"""
    if os.path.exists(DB_FILE_NAME):
        return

    download_and_extract_unihan()
    conn, cursor = init_sqlite_db()

    print("首次執行，正在構建包含部首分析的漢字資料庫...")

    strokes_dict = {}
    radical_dict = {}

    with open(TARGET_TXT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue

            parts = line.strip().split("\t")
            if len(parts) >= 3:
                code_point_str, attribute, value = parts[0], parts[1], parts[2]

                try:
                    code_point = int(code_point_str.replace("U+", ""), 16)
                    char = chr(code_point)
                except ValueError:
                    continue

                if attribute == "kTotalStrokes":
                    strokes_dict[char] = int(value.split()[0])
                elif attribute == "kRSUnicode":
                    rad_id = value.split()[0].split(".")[0].replace("'", "")
                    radical_dict[char] = rad_id

    records = []
    for char, stroke in strokes_dict.items():
        rad_id = radical_dict.get(char, "")
        records.append((char, stroke, rad_id))

    cursor.executemany(
        """
        INSERT OR REPLACE INTO strokes (char, stroke_count, radical_id)
        VALUES (?, ?, ?)
    """,
        records,
    )

    conn.commit()
    conn.close()
    print(f"資料庫建立完成！共匯入 {len(records)} 個漢字資訊。\n")


def get_name_stroke_count(char: str) -> tuple[int, int, str]:
    """獲取姓名學筆畫"""
    if char in CHAR_EXCEPTIONS:
        stroke, note = CHAR_EXCEPTIONS[char]
        return stroke, stroke, note

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


# =========================================================
# 干支、五行與五星計算模組
# =========================================================
# 五行與五星的固定順序表
WUXING_ORDER = ["木", "火", "土", "金", "水"]
WUXING_TO_INDEX = {w: i for i, w in enumerate(WUXING_ORDER)}
STAR_ORDER = ["比", "食", "財", "官", "印"]


def get_gan_zhi_wuxing(num: int) -> tuple[str, str]:
    """
    根據數值計算 (五行天干地支字串, 五行名)
    例如 26 -> ("土己巳", "土")
    """
    tiangan_map = {
        1: "甲",
        2: "乙",
        3: "丙",
        4: "丁",
        5: "戊",
        6: "己",
        7: "庚",
        8: "辛",
        9: "壬",
        0: "癸",
    }
    gan = tiangan_map[num % 10]

    wuxing_map = {
        "甲": "木",
        "乙": "木",
        "丙": "火",
        "丁": "火",
        "戊": "土",
        "己": "土",
        "庚": "金",
        "辛": "金",
        "壬": "水",
        "癸": "水",
    }
    wuxing = wuxing_map[gan]

    dizhi_map = {
        1: "子",
        2: "丑",
        3: "寅",
        4: "卯",
        5: "辰",
        6: "巳",
        7: "午",
        8: "未",
        9: "申",
        10: "酉",
        11: "戌",
        0: "亥",
    }
    zhi = dizhi_map[num % 12]

    return f"{wuxing}{gan}{zhi}", wuxing


def get_star(base_wuxing: str, target_wuxing: str) -> str:
    """
    計算目標五行相對於基準五行（人格）對應的五星 (比、食、財、官、印)
    """
    base_idx = WUXING_TO_INDEX[base_wuxing]
    target_idx = WUXING_TO_INDEX[target_wuxing]

    # 計算順向距離 (木->火->土->金->水)
    diff = (target_idx - base_idx) % 5
    return STAR_ORDER[diff]


# =========================================================
# 五格與五星呈現模組
# =========================================================
def calculate_wuge(surname_strokes: list[int], name_strokes: list[int]) -> str:
    """計算姓名五格並呈現五行干支與五星關係"""
    s_len = len(surname_strokes)
    n_len = len(name_strokes)

    if s_len == 1 and n_len == 2:
        # 1. 單姓複名 (姓A 名BC)
        A, (B, C) = surname_strokes[0], name_strokes
        name_type = "單姓複名"
        tiange, renge, dige, waige, zongge = A + 1, A + B, B + C, C + 1, A + B + C

    elif s_len == 1 and n_len == 1:
        # 2. 單姓單名 (姓A 名B)
        A, B = surname_strokes[0], name_strokes[0]
        name_type = "單姓單名"
        tiange, renge, dige, waige, zongge = A + 1, A + B, B + 1, 2, A + B

    elif s_len == 2 and n_len == 2:
        # 3. 複姓複名 (姓AB 名CD)
        (A, B), (C, D) = surname_strokes, name_strokes
        name_type = "複姓複名"
        tiange, renge, dige, waige, zongge = (
            A + B,
            B + C,
            C + D,
            A + D,
            A + B + C + D,
        )

    elif s_len == 2 and n_len == 1:
        # 4. 複姓單名 (姓AB 名C)
        (A, B), C = surname_strokes, name_strokes[0]
        name_type = "複姓單名"
        tiange, renge, dige, waige, zongge = A + B, B + C, C + 1, A + 1, A + B + C

    else:
        return "⚠️ 目前僅支援 2~4 字的姓名組合。"

    # 解析各格之 (干支字串, 五行)
    tiange_str, t_wx = get_gan_zhi_wuxing(tiange)
    renge_str, r_wx = get_gan_zhi_wuxing(renge)  # r_wx 作為基準「比」
    dige_str, d_wx = get_gan_zhi_wuxing(dige)
    waige_str, w_wx = get_gan_zhi_wuxing(waige)
    zongge_str, z_wx = get_gan_zhi_wuxing(zongge)

    # 依序呈現五格，人格不填星宿，其餘四格對應人格五行計算星宿
    result = [
        f"--- 【{name_type} 五格+干支+五星分析】 ---",
        f"天格({tiange})={tiange_str}→{get_star(r_wx, t_wx)}",
        f"人格({renge})={renge_str}",  # 人格不用填星宿
        f"地格({dige})={dige_str}→{get_star(r_wx, d_wx)}",
        f"外格({waige})={waige_str}→{get_star(r_wx, w_wx)}",
        f"總格({zongge})={zongge_str}→{get_star(r_wx, z_wx)}",
    ]

    return "\n".join(result)


def process_name_analysis(surname: str, given_name: str):
    """主程序"""
    surname = surname.strip()
    given_name = given_name.strip()

    if not surname or not given_name:
        print("⚠️ 姓氏與名字皆不能為空！\n")
        return

    full_name = surname + given_name
    print(f"\n====================================")
    print(f"  姓名：{full_name}（姓: {surname} / 名: {given_name}）")
    print(f"====================================")

    surname_strokes = []
    print("\n【姓氏筆劃明細】")
    for char in surname:
        final_stroke, _, note = get_name_stroke_count(char)
        surname_strokes.append(final_stroke)
        print(f"  字：{char}  -->  姓名學筆畫：{final_stroke} 畫{note}")

    name_strokes = []
    print("\n【名字筆劃明細】")
    for char in given_name:
        final_stroke, _, note = get_name_stroke_count(char)
        name_strokes.append(final_stroke)
        print(f"  字：{char}  -->  姓名學筆畫：{final_stroke} 畫{note}")

    print("\n" + "=" * 40)

    # 計算並呈現五格干支與五星
    wuge_output = calculate_wuge(surname_strokes, name_strokes)
    print(wuge_output)
    print("=" * 40 + "\n")


if __name__ == "__main__":
    parse_and_import_to_db()

    print("====================================")
    print(" 全自動姓名學（筆畫+五格+干支+五星）器 ")
    print("====================================")

    while True:
        surname_input = input("請輸入姓氏（輸入 exit 離開）：").strip()
        if surname_input.lower() == "exit":
            print("\n感謝使用，程式已結束！")
            break

        name_input = input("請輸入名字：").strip()

        process_name_analysis(surname_input, name_input)