import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import os
from call_api import client
from datetime import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

#  타이틀
st.title(" Movie Script Analyzer V.032900")
st.write("대본을 업로드하면 GPT가 분석하고, 결과를 구글 시트에 저장합니다.")

#  Google Sheets 인증
if "MOVIEANALYSIS_GSHEET" not in st.secrets:
    st.error("❌ Streamlit secrets에 'MOVIEANALYSIS_GSHEET' 키가 없습니다.")
    st.stop()
else:
    with open("google-credentials.json", "w") as f:
        json.dump(json.loads(st.secrets["MOVIEANALYSIS_GSHEET"]), f)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("google-credentials.json", scope)
gs_client = gspread.authorize(creds)
sheet = gs_client.open("Movie_Analysis").worksheet("Data")

#  분석 함수 정의
def analyze_script_to_plots(text, movie_title):
    scenes = re.split(r'\n{2,}', text)[:8]  # 앞부분 8개 플롯만 분석
    results = []
    for i, scene in enumerate(scenes):
        plot_num = i + 1
        progress = int((plot_num - 1) / max(len(scenes) - 1, 1) * 100)
        
        # GPT를 사용하여 감정, 긴박도, 장르 분석
        main_emotion = ask_gpt(f"플롯 {plot_num}의 주인공 감정을 0~100 사이의 숫자로 답변해주세요. 플롯 내용: {scene}", text)
        sub_emotion = ask_gpt(f"플롯 {plot_num}의 인물2 감정을 0~100 사이의 숫자로 답변해주세요. 플롯 내용: {scene}", text)
        tension = ask_gpt(f"플롯 {plot_num}의 긴박도를 0~100 사이의 숫자로 답변해주세요. 플롯 내용: {scene}", text)
        genre = ask_gpt(f"플롯 {plot_num}의 핵심 장르를 [드라마, 로맨스, 코미디, 범죄, 스릴러, 공포, SF/판타지, 액션, 어드벤처, 전쟁, 재난, 뮤지컬, 아동/청소년, 종교, 시대극] 중에서 하나만 선택하여 답변해주세요. 플롯 내용: {scene}", text)
        
        results.append([
            movie_title,
            plot_num,
            f"플롯 {plot_num}",
            scene.strip()[:60].replace("\n", " ") + "...",
            progress,
            main_emotion,
            sub_emotion,
            tension,
            genre
        ])
    df = pd.DataFrame(results, columns=[
        "영화제목", "플롯번호", "플롯 구간", "주요 사건", "진행도(%)",
        "주인공 감정", "인물2 감정", "긴박도", "핵심 장르"
    ])
    return df

#  GPT 호출 함수
def ask_gpt(question, script_text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 영화 시나리오 분석 전문가입니다. 주어진 대본의 텍스트와 문맥에 기반해서 분석합니다."},
            {"role": "user", "content": f"대본 내용: {script_text}...\n\n{question}"}
        ]
    )
    return response.choices[0].message.content

#  PDF 텍스트 추출 함수
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = "".join([page.get_text("text") for page in doc])
    return text

#  파일 업로드 및 분석 흐름
uploaded_file = st.file_uploader("️ PDF 대본을 업로드하세요", type=["pdf"])

if uploaded_file is not None:
    filename = uploaded_file.name
    movie_title = os.path.splitext(filename)[0]
    today = datetime.today().strftime("%Y-%m-%d")

    #  이전 파일과 다르면 세션 초기화
    if st.session_state.get("last_uploaded_filename") != filename:
        st.session_state.analysis_results = None
        st.session_state.already_saved = False
        st.session_state.last_uploaded_filename = filename

    # 분석이 아직 안된 경우
    if st.session_state.get("analysis_results") is None:
        with st.spinner(" 대본을 분석 중입니다..."):
            script_text = extract_text_from_pdf(uploaded_file)
            st.session_state.analysis_results = analyze_script_to_plots(script_text, movie_title)
        st.success("✅ GPT 분석 완료!")

    #  Google Sheets 중복 저장 방지
    if not st.session_state.get("already_saved"):
        existing_rows = sheet.get_all_values()
        already_logged = any(
            len(row) >= 2 and row[0] == today and row[1] == movie_title for row in existing_rows
        )
        if not already_logged:
            for index, row in st.session_state.analysis_results.iterrows():
                sheet.append_row([today] + row.tolist())
            st.session_state.already_saved = True
            st.success("✅ 결과가 Google Sheets에 저장되었습니다.")
        else:
            st.info("⚠️ 이미 저장된 분석 결과입니다.")

    #  결과 출력
    st.write("###  분석 결과")
    st.dataframe(st.session_state.analysis_results)
