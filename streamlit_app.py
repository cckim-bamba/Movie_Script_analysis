import streamlit as st

st.title("🎬 Movie Script Test4")
st.write(
    "Let's start building! For help and inspiration, head over to [docs.streamlit.io](https://docs.streamlit.io/)."
)

import streamlit as st
import fitz  # PyMuPDF
import openai
import pandas as pd
import json
import os
from call_api import client 

# 질문 리스트
QUESTIONS = {
    "summary": "이 대본의 줄거리 요약 500자 이내로",
    "conflict_structure": "기승전결 핵심 갈등 요소 [기:갈등요소, 승:갈등요소, 전:갈등요소, 결:갈등요소] 형태로, 괄호 포함하고 리스트만 출력해.",
    "character_ratio": "이 대본의 등장인물 [주인공-%, 인물1-%, 인물2-%,, ] 등장 비중 순으로 리스트만 출력",
    "emotion_curve": "기승전결에서 주인공의 감정변화 [기:감정, 승:감정, 전:감정, 결:감정] 형태로, 괄호 포함하고 리스트만 출력해.",
    "casting": "이 대본의 주인공에 적합한 배우 3명 추천해 [배우1,배우2,배우3] 형태로, 괄호 포함하고 리스트만 출력해.",
    "location_scene_ratio": "이 대본의 주요 장소와 장면 비중을 [장소:비중%,장소:비중%,장소:비중%,,] 괄호 포함하고 리스트만 출력해..",
    "location_scene_count": "이 영화에 나오는 장소와 장소별 Scean 노출회수를 세어서 노출비중이 높은 순으로 [장소1:%,장소2:%,장소3] 형태로, 괄호 포함하고 리스트만 출력해.",
    "genre_mix": "이 영화의 장르 구성 요소를 %, 합이 100%가 되도록 분석해. (예: [액션 40%, 드라마 30%, 스릴러 30%] 괄호포함하고 리스트만 출력해.) ",
    "similar_movies": "유사한 주제를 가진 한국 영화 5개 [영화1-주제,영화2-주제, 영화3-주제,,] 형태로, 주제는 3개이내 단어로 리스트만 출력 ",
    "hit_pos_neg": "이 영화의 흥행 가능성 긍정요소 3개, 부정적 요소 3개씩 리스트로 출력."
}



# GPT API 호출 함수
def ask_gpt(question, script_text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 영화 시나리오 분석 전문가입니다."},
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
st.title("영화 대본 분석 MVP")
uploaded_file = st.file_uploader("PDF 대본을 업로드하세요", type=["pdf"])

if uploaded_file is not None:
    # 영화제목 추출 (여기서만 접근해야 안전해!)
    filename = uploaded_file.name
    movie_title = os.path.splitext(filename)[0]
    csv_filename = f"{movie_title} 분석결과.csv"

    with st.spinner("PDF에서 텍스트 추출 중..."):
        script_text = extract_text_from_pdf(uploaded_file)

    st.success("텍스트 추출 완료!")

    if "analysis_results" not in st.session_state:
        results = {}
        for question in QUESTIONS.values():
            with st.spinner(f"질문: {question} 처리 중..."):
                answer = ask_gpt(question, script_text)
                results[question] = answer
        st.session_state.analysis_results = results

    st.success("GPT 분석 완료!")

    results_df = pd.DataFrame.from_dict(st.session_state.analysis_results, orient='index', columns=["응답"])
    csv = results_df.to_csv(index=True, encoding='utf-16', sep='\t')
    st.download_button("CSV 파일 다운로드", csv, csv_filename, "text/csv")
    st.write("### 분석 결과")
    st.dataframe(results_df)
