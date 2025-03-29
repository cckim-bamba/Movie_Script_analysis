import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import os
from call_api import client
from datetime import datetime

import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials


st.title("🎬 Movie Script Test5")
st.write(
    "Let's start building! For help and inspiration, head over to [docs.streamlit.io](https://docs.streamlit.io/)."
)


# 1. Streamlit secrets에서 JSON 저장
if "MOVIEANALYSIS_GSHEET" not in st.secrets:
    st.error("MOVIEANALYSIS_GSHEET secret not found in Streamlit secrets.")
else:
    with open("google-credentials.json", "w") as f:
        json.dump(json.loads(st.secrets["MOVIEANALYSIS_GSHEET"]), f)

# 2. 인증 및 시트 연결
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("google-credentials.json", scope)
gs_client = gspread.authorize(creds)
sheet = gs_client.open("Movie_Analysis").worksheet("Data")

# 3. 예시: 데이터 한 줄 쓰기
sheet.append_row(["2025-03-29", "영화제목", "항목", "분석결과"])

# 질문 리스트
QUESTIONS = {
    "summary": {
        "prompt": "이 대본의 줄거리를 1000자 이내로 기-승-전-결 구조로 주인공의 감정 흐름과 이야기 전개가 드러나도록 간결하게 서술해 주세요.",
        "output_format": "문장"
    },
    "conflict_structure": {
        "prompt": "이 대본의 기승전결 구조에서 핵심 갈등 요소를 [기:갈등요소, 승:갈등요소, 전:갈등요소, 결:갈등요소] 형태로 리스트만 출력하세요. 설명 없이 리스트로만 출력해 주세요.",
        "output_format": "리스트"
    },
    "character_ratio": {
        "prompt": "이 대본의 등장인물 비중을 [주인공이름-30%, 이름-25%, 이름-15%, ...] 형태로, 비중이 높은 순으로 리스트만 출력하세요. 설명 없이 리스트로만 출력해 주세요.",
        "output_format": "리스트"
    },
    "emotion_curve": {
        "prompt": "기승전결에서 주인공의 감정 변화를 [기:감정, 승:감정, 전:감정, 결:감정] 형태로 리스트만 출력해 주세요. 설명 없이 리스트로만 출력해 주세요.",
        "output_format": "리스트"
    },
    "casting": {
        "prompt": "이 대본의 주인공에 적합한 한국 배우 3명을 [배우1-이유, 배우2-이유, 배우3-이유] 형태로 추천해 주세요. 설명 없이 리스트로만 출력해 주세요.",
        "output_format": "리스트"
    },
    "location_scene_ratio": {
        "prompt": "이 대본의 주요 장소와 장면 비중을 [장소1:비중%, 장소2:비중%, 장소3:비중%] 형태로 리스트만 출력해 주세요. 설명 없이 괄호 포함 리스트로만 출력해 주세요.",
        "output_format": "리스트"
    },
    "genre_mix": {
        "prompt": "이 영화의 장르 구성 비율을 분석하여 [장르1 40%, 장르2 30%, 장르3 30%] 형식으로, 합이 100%가 되도록 괄호 포함 리스트만 출력해 주세요. 참조하는 영화장르는 드라마,첩보,옴니버스,뮤직,동성애, 드무비,아동,하이틴,전기,청춘,재난,신파,활극,반공,군사,계몽,사회,스포츠,종교,무협,미스터리,SF,코메디,느와르,액션,범죄,어드벤처,가족,에로,멜로,로맨스,공포,뮤지컬,시대극,실험,스릴러,서부,전쟁,갱스터,판타지,해양액션 등입니다. 설명 없이 결과만 출력해 주세요.",
        "output_format": "리스트"
    },
    "similar_movies": {
        "prompt": "주제와 장르에서 유사한 한국 영화 5편을 [(제목,감독,주제), (제목,감독,주제), ...] 형태로 리스트만 출력해 주세요. 각 주제는 한문장으로. 설명 없이 리스트로만 출력해 주세요.",
        "output_format": "리스트"
    },
    "hit_pos": {
        "prompt": "이 영화가 손익분기점을 넘길 수 있는 긍정적인 요소 3개를 [요소1, 요소2, 요소3] 형식으로 리스트로만 출력해 주세요.",
        "output_format": "리스트"
    },
    "hit_neg": {
        "prompt": "이 영화가 손익분기점을 넘길 수 없는 부정적인 요소 3개를 [요소1, 요소2, 요소3] 형식으로 리스트로만 출력해 주세요.",
        "output_format": "리스트"
    },
    "hit_ganre": {
        "prompt": "이 영화가 흥행할수 있는지 장르 결합 측면에서 평가해서 한문장으로 간결하게 설명해줘.",
        "output_format": "문장"
    },
    "hit_charactor": {
        "prompt": "이 영화가 흥행할수 있는지 주인공의 감정선과 매력도 측면에서 한문장으로 간결하게 평가해줘.",
        "output_format": "문장"
    },
    "hit_story": {
        "prompt": "이 영화가 흥행할수 있는지 영화의 주제 측면에서 한문장으로 간결하게 평가해줘.",
        "output_format": "문장"
    }
}

# GPT API 호출 함수
def ask_gpt(question, script_text):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "당신은 영화 시나리오 분석 전문가입니다.외부 데이터 참조하지 않고 대본 자료만 분석합니다."},
            {"role": "user", "content": f"대본 내용: {script_text[:2000]}...\n\n{question}"}
        ]
    )
    return response.choices[0].message.content

# PDF에서 텍스트 추출 함수
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = "".join([page.get_text("text") for page in doc])
    return text

# Streamlit UI
st.title("영화 대본 분석 MVP (Google Sheets 연동)")
uploaded_file = st.file_uploader("PDF 대본을 업로드하세요", type=["pdf"])

if uploaded_file is not None:
    filename = uploaded_file.name
    movie_title = os.path.splitext(filename)[0]
    today = datetime.today().strftime("%Y-%m-%d")

    with st.spinner("PDF에서 텍스트 추출 중..."):
        script_text = extract_text_from_pdf(uploaded_file)
    st.success("텍스트 추출 완료!")

    if "analysis_results" not in st.session_state:
        results = {}
        for key, info in QUESTIONS.items():
            question = info["prompt"]
            output_format = info["output_format"]
            answer = ask_gpt(question, script_text)
            if output_format == "리스트":
                answer = answer.strip("[]")  # 필요 시 후처리
            results[key] = answer
        st.session_state.analysis_results = results

    st.success("GPT 분석 완료!")

    # 결과 Google Sheets에 누적 저장
    for key, val in st.session_state.analysis_results.items():
        sheet.append_row([today, movie_title, key, val])

    # 화면에 출력
    results_df = pd.DataFrame([
        {"항목": key, "응답": val} for key, val in st.session_state.analysis_results.items()
    ])
    st.write("### 분석 결과")
    st.dataframe(results_df)
