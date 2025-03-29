import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import os
from call_api import client
from datetime import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 🔹 타이틀
st.title("🎬 Movie Script Analyzer V.0329")
st.write("대본을 업로드하면 GPT가 분석하고, 결과를 구글 시트에 저장합니다.")

# 🔹 Google Sheets 인증
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

# 🔹 분석 질문 정의
QUESTIONS = {
    "summary": {
        "prompt": "이 대본의 줄거리를 기승전결이 드러나게 1000자 이내로 요약해주세요.",
        "output_format": "문장"
    },
    "conflict_structure": {
        "prompt": "이 대본의 기승전결 구조에서 핵심 갈등 요소를 [기:갈등요소, 승:갈등요소, 전:갈등요소, 결:갈등요소] 형태로 리스트만 출력하세요.",
        "output_format": "리스트"
    },
    "character_ratio": {
        "prompt": "등장인물 비중을 [이름-%, 이름-%, ...] 형태로 리스트만 출력하세요.",
        "output_format": "리스트"
    },
    "emotion_curve": {
        "prompt": "주인공의 감정변화를 [기:감정, 승:감정, 전:감정, 결:감정] 형태로 리스트만 출력하세요.",
        "output_format": "리스트"
    },
    "casting": {
        "prompt": "주인공에 적합한 한국 배우 3명을 [배우1-이유, 배우2-이유, 배우3-이유] 형태로 리스트만 출력하세요.",
        "output_format": "리스트"
    },
    "location_scene_ratio": {
        "prompt": "장소별 장면 비중을 [장소1:비중%, 장소2:비중%] 형태로 리스트만 출력하세요.",
        "output_format": "리스트"
    },
    "genre_mix": {
        "prompt": "이 영화의 장르 구성 비율을 분석해 [장르1 40%, 장르2 30%, 장르3 30%] 형태로 출력하세요. 장르는 [드라마, 로맨스, 코미디, 범죄, 스릴러, 공포, SF/판타지, 액션, 어드벤처, 전쟁, 재난, 뮤지컬, 아동/청소년, 종교, 시대극] 중에서 고르세요.",
        "output_format": "리스트"
    },
    "similar_movies": {
        "prompt": "유사한 한국 영화 5편을 [(제목,감독,주제), ...] 형태로 리스트만 출력하세요.",
        "output_format": "리스트"
    },
    "hit_pos": {
        "prompt": "흥행 가능성이 높은 긍정 요소 3가지를 [요소1, 요소2, 요소3] 형태로 리스트만 출력하세요.",
        "output_format": "리스트"
    },
    "hit_neg": {
        "prompt": "흥행에 불리한 부정 요소 3가지를 [요소1, 요소2, 요소3] 형태로 리스트만 출력하세요.",
        "output_format": "리스트"
    },
    "hit_ganre": {
        "prompt": "장르 측면에서 흥행 가능성을 한 문장으로 평가해 주세요.",
        "output_format": "문장"
    },
    "hit_charactor": {
        "prompt": "주인공 감정선과 매력도 측면에서 흥행 가능성을 한 문장으로 평가해 주세요.",
        "output_format": "문장"
    },
    "hit_story": {
        "prompt": "주제 측면에서 흥행 가능성을 한 문장으로 평가해 주세요.",
        "output_format": "문장"
    }
}

# 🔹 GPT 호출 함수
def ask_gpt(question, script_text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 영화 시나리오 분석 전문가입니다."},
            {"role": "user", "content": f"대본 내용: {script_text}...\n\n{question}"}
        ]
    )
    return response.choices[0].message.content

# 🔹 PDF 텍스트 추출 함수
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = "".join([page.get_text("text") for page in doc])
    return text

# 🔹 파일 업로드 및 분석 흐름
uploaded_file = st.file_uploader("🎞️ PDF 대본을 업로드하세요", type=["pdf"])

if uploaded_file is not None:
    filename = uploaded_file.name
    movie_title = os.path.splitext(filename)[0]
    today = datetime.today().strftime("%Y-%m-%d")

    # 📌 이전 파일과 다르면 세션 초기화
    if st.session_state.get("last_uploaded_filename") != filename:
        st.session_state.analysis_results = {}
        st.session_state.already_saved = False
        st.session_state.last_uploaded_filename = filename

    # 분석이 아직 안된 경우
    if not st.session_state.get("analysis_results"):
        with st.spinner("📄 대본을 분석 중입니다..."):
            script_text = extract_text_from_pdf(uploaded_file)
            results = {}
            for key, info in QUESTIONS.items():
                answer = ask_gpt(info["prompt"], script_text)
                if info["output_format"] == "리스트":
                    answer = answer.strip("[]")  # 괄호 제거
                results[key] = answer
            st.session_state.analysis_results = results
        st.success("✅ GPT 분석 완료!")

    # 📤 Google Sheets 중복 저장 방지
    if not st.session_state.get("already_saved"):
        existing_rows = sheet.get_all_values()
        already_logged = any(
            row[0] == today and row[1] == movie_title for row in existing_rows
        )
        if not already_logged:
            for key, val in st.session_state.analysis_results.items():
                sheet.append_row([today, movie_title, key, val])
            st.session_state.already_saved = True
            st.success("✅ 결과가 Google Sheets에 저장되었습니다.")
        else:
            st.info("⚠️ 이미 저장된 분석 결과입니다.")

    # 📊 결과 출력
    results_df = pd.DataFrame([
        {"항목": key, "응답": val} for key, val in st.session_state.analysis_results.items()
    ])
    st.write("### 🎯 분석 결과")
    st.dataframe(results_df)
