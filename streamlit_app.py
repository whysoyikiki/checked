import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(layout="wide")
st.title("📊 카카오톡 출퇴근 기록 분석")

# =========================
# 사용자 입력
# =========================
uploaded_file = st.file_uploader("카카오톡 txt 파일 업로드", type="txt")
target_name = st.text_input("분석 대상 이름 (예: NEB 김기범 대리님)")
start_monday = st.text_input("시작 월요일 (YYYYMMDD)")

if not uploaded_file or not target_name or not start_monday:
    st.stop()

start_date = datetime.strptime(start_monday, "%Y%m%d").date()
end_date = datetime.today().date()

# =========================
# 유틸 함수
# =========================
def parse_time(ampm, h, m):
    h = int(h)
    m = int(m)
    if ampm == "오후" and h != 12:
        h += 12
    if ampm == "오전" and h == 12:
        h = 0
    return h, m

def format_diff(mins):
    sign = "+" if mins >= 0 else "-"
    mins = abs(mins)
    return f"{sign}{mins//60}시간 {mins%60}분"

# =========================
# TXT 파싱
# =========================
lines = uploaded_file.read().decode("utf-8").splitlines()

date_pattern = re.compile(r"-+\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(월|화|수|목|금|토|일)요일")
msg_pattern = re.compile(r"\[(.*?)\]\s*\[(오전|오후)\s*(\d+):(\d+)\]")

records = []
current_date = None
current_weekday = None

for line in lines:
    date_match = date_pattern.search(line)
    if date_match:
        y, m, d, wd = date_match.groups()
        current_date = datetime(int(y), int(m), int(d)).date()
        current_weekday = wd
        continue

    if not current_date or not (start_date <= current_date <= end_date):
        continue

    msg_match = msg_pattern.search(line)
    if not msg_match:
        continue

    name, ampm, h, m = msg_match.groups()
    if name != target_name:
        continue

    hour, minute = parse_time(ampm, h, m)

    records.append({
        "이름": name,
        "날짜": current_date,
        "요일": current_weekday,
        "hour": hour,
        "minute": minute
    })

df = pd.DataFrame(records)
if df.empty:
    st.warning("해당 기간에 데이터가 없습니다.")
    st.stop()

# =========================
# 일자별 출퇴근 계산
# =========================
rows = []
weekly_minutes = 0
current_week = None

for date, g in df.groupby("날짜"):
    g = g.sort_values(["hour", "minute"])
    weekday = g.iloc[0]["요일"]

    start = g.iloc[0]
    end = g.iloc[-1] if len(g) > 1 else None

    start_dt = datetime.combine(date, datetime.min.time()) + timedelta(
        hours=int(start["hour"]), minutes=int(start["minute"])
    )

    end_dt = None
    diff_min = None

    if end is not None:
        end_dt = datetime.combine(date, datetime.min.time()) + timedelta(
            hours=int(end["hour"]), minutes=int(end["minute"])
        )
        diff_min = int((end_dt - start_dt).total_seconds() // 60) - 540

    week_id = date - timedelta(days=date.weekday())

    if current_week is None:
        current_week = week_id

    if week_id != current_week:
        rows.append({
            "이름": "",
            "날짜": "",
            "요일": "주간합계",
            "출근": "",
            "퇴근": "",
            "시간": "",
            "주간합계": format_diff(weekly_minutes)
        })
        weekly_minutes = 0
        current_week = week_id

    if diff_min is not None:
        weekly_minutes += diff_min + 540

    rows.append({
        "이름": target_name,
        "날짜": date.strftime("%Y-%m-%d"),
        "요일": weekday,
        "출근": start_dt.strftime("%H:%M"),
        "퇴근": end_dt.strftime("%H:%M") if end_dt else "",
        "시간": format_diff(diff_min) if diff_min is not None else "",
        "주간합계": ""
    })

rows.append({
    "이름": "",
    "날짜": "",
    "요일": "주간합계",
    "출근": "",
    "퇴근": "",
    "시간": "",
    "주간합계": format_diff(weekly_minutes)
})

result_df = pd.DataFrame(rows)

# =========================
# 스타일 함수
# =========================
def highlight_weekly(val):
    if isinstance(val, str) and val.startswith("-"):
        return "background-color: #ffcccc"
    return ""

def summary_color(val):
    if isinstance(val, str):
        if val.startswith("+"):
            return "background-color: #ccffcc"
        if val.startswith("-"):
            return "background-color: #ffcccc"
    return ""

# =========================
# 상세 테이블 출력
# =========================
st.subheader("📋 상세 기록")

styled = result_df.style.applymap(
    highlight_weekly,
    subset=["주간합계"]
)

st.dataframe(styled, use_container_width=True)

# =========================
# 요약 테이블
# =========================
st.subheader("📊 주간 요약")

weekdays = ["월", "화", "수", "목", "금"]
summary = {d: "" for d in weekdays}
weekly_sum = ""

for _, r in result_df.iterrows():
    if r["요일"] == "주간합계":
        weekly_sum = r["주간합계"]
    elif r["요일"] in weekdays:
        summary[r["요일"]] = r["시간"]

summary["주간합계"] = weekly_sum
summary_df = pd.DataFrame([summary])

st.dataframe(summary_df.style.applymap(summary_color), use_container_width=True)

# =========================
# 엑셀 다운로드
# =========================
buffer = BytesIO()
result_df.to_excel(buffer, index=False)

st.download_button(
    "⬇ 엑셀 다운로드",
    data=buffer.getvalue(),
    file_name="출퇴근_분석.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
