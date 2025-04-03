import streamlit as st
import gspread
import json
import pandas as pd
from openai import OpenAI
from PyPDF2 import PdfReader
from oauth2client.service_account import ServiceAccountCredentials

# ✅ GPT API 키 (Streamlit secrets에서 불러오기)
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ✅ Google Sheets 인증
if "MOVIEANALYSIS_GSHEET" not in st.secrets:
    st.error("❌ Streamlit secrets에 'MOVIEANALYSIS_GSHEET' 키가 없습니다.")
    st.stop()

with open("google-credentials.json", "w") as f:
    json.dump(json.loads(st.secrets["MOVIEANALYSIS_GSHEET"]), f)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("google-credentials.json", scope)
gs_client = gspread.authorize(creds)
sheet = gs_client.open_by_url("https://docs.google.com/spreadsheets/d/1PdE87G6sENx4sQk1swCNPnmrZrEHpHBBRQwNKWLFdEQ").worksheet("Plot")

# ✅ 텍스트 추출 함수
def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

# ✅ GPT로 플롯 자동 분할
def split_script_with_gpt(full_text):
    prompt = f"""다음은 영화 시나리오 전체입니다. 이 시나리오를 n개의 주요 플롯(Plot)으로 나누고, 각 플롯의 내용을 300자 이내로 요약해줘. 
JSON 형식으로, 다음 키로 구성해줘: 플롯번호, 요약문.

시나리오:
{full_text}
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response["choices"][0]["message"]["content"]

# ✅ GPT로 각 플롯 분석
def analyze_single_plot(scene):
    def ask(subprompt):
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": subprompt}],
            temperature=0
        )
        return res["choices"][0]["message"]["content"].strip()
    
    emotion = ask(f"다음 플롯의 주인공 감정을 0~100 숫자 하나로만 답해줘:\n{scene}")
    sub_emotion = ask(f"다음 플롯의 인물2 감정을 0~100 숫자 하나로만 답해줘:\n{scene}")
    tension = ask(f"다음 플롯의 긴박도를 0~100 숫자 하나로만 답해줘:\n{scene}")
    genre = ask(f"다음 플롯의 장르를 아래 중 하나만 단어로 답해줘:\n[드라마, 로맨스, 코미디, 스릴러, SF/판타지, 공포, 액션, 시대극, 뮤지컬]\n{scene}")
    
    return emotion, sub_emotion, tension, genre

# ✅ Streamlit UI
st.title("🎬 GPT 기반 영화 플롯 분석기")

uploaded = st.file_uploader("PDF 시나리오 파일 업로드", type="pdf")

if uploaded:
    movie_title = uploaded.name.replace(".pdf", "")
    full_text = extract_text_from_pdf(uploaded)
    st.success("✅ 텍스트 추출 완료. GPT로 플롯 분석 중...")

    # GPT로 플롯 분할 및 요약
    plot_json = split_script_with_gpt(full_text)
    try:
        import ast
        plots = ast.literal_eval(plot_json)
    except:
        st.error("GPT 응답을 JSON으로 변환하는 데 실패했습니다.")
        st.stop()

    rows = []
    for p in plots:
        plot_num = p.get("플롯번호") or p.get("번호") or p.get("plot") or plots.index(p) + 1
        summary = p.get("요약문") or p.get("내용") or p.get("summary")

        emotion, sub, tension, genre = analyze_single_plot(summary)

        rows.append([
            movie_title,
            plot_num,
            f"플롯 {plot_num}",
            summary[:60],
            int((int(plot_num)-1)/max(len(plots)-1, 1)*100),
            emotion,
            sub,
            tension,
            genre
        ])

    df = pd.DataFrame(rows, columns=["영화제목", "플롯번호", "플롯", "주요사건", "진행도(%)", "주인공감정", "인물2감정", "긴박도", "장르"])

    st.subheader("📊 분석 결과")
    st.dataframe(df)

    if st.button("📤 Google Sheets에 저장"):
        for _, row in df.iterrows():
            sheet.append_row(row.values.tolist(), value_input_option="USER_ENTERED")
        st.success("✅ 저장 완료!")
