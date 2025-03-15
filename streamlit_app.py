import streamlit as st

st.title("🎈 My new app")
st.write(
    "Let's start building! For help and inspiration, head over to [docs.streamlit.io](https://docs.streamlit.io/)."
)

import streamlit as st
import fitz  # PyMuPDF
import openai
import pandas as pd
import json
import os

# OpenAI API Key (환경 변수에서 가져오기)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# 질문 리스트
QUESTIONS = [
    "줄거리 1천자 이내로 요약해줘.",
    "기, 승, 전, 결 각각 핵심 내용을 3줄씩 bullet point로 정리해줘.",
    "이 영화의 등장인물 수는 몇 명인가?",
    "주인공의 감정 변화를 기, 승, 전, 결 4단계로 요약해줘.",
    "이 영화의 장르 구성 요소를 %, 합이 100%가 되도록 분석해줘. (예: 액션 40%, 드라마 30%, 스릴러 30%)",
    "유사한 주제를 가진 영화 최대 5개를 추천해줘.",
    "이 영화의 흥행 요소를 500자 이내로 분석해줘."
]

# GPT API 호출 함수
def ask_gpt(question, script_text):
    response = openai.ChatCompletion.create(
        model="gpt-4",  # 필요하면 다른 모델로 변경
        messages=[
            {"role": "system", "content": "당신은 영화 시나리오 분석 전문가입니다."},
            {"role": "user", "content": f"대본 내용: {script_text[:2000]}...\n\n{question}"}
        ]
    )
    return response['choices'][0]['message']['content']

# PDF에서 텍스트 추출 함수
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = "".join([page.get_text("text") for page in doc])
    return text

# Streamlit UI
st.title("영화 대본 분석 MVP")
uploaded_file = st.file_uploader("PDF 대본을 업로드하세요", type=["pdf"])

if uploaded_file is not None:
    with st.spinner("PDF에서 텍스트 추출 중..."):
        script_text = extract_text_from_pdf(uploaded_file)
    
    st.success("텍스트 추출 완료!")
    
    # GPT API 호출 및 응답 저장
    results = {}
    for question in QUESTIONS:
        with st.spinner(f"질문: {question} 처리 중..."):
            answer = ask_gpt(question, script_text)
            results[question] = answer
    
    st.success("GPT 분석 완료!")
    
    # 결과를 데이터프레임으로 변환
    df = pd.DataFrame.from_dict(results, orient='index', columns=["응답"])
    
    # CSV 저장 버튼
    csv = df.to_csv(index=True, encoding='utf-8-sig')
    st.download_button("CSV 파일 다운로드", csv, "script_analysis.csv", "text/csv")
    
    # 결과 출력
    st.write("### 분석 결과")
    st.dataframe(df)
