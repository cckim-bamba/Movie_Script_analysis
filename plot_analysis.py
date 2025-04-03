# Ensure required packages are installed: PyPDF2, pandas
import os
import json
import re
import pandas as pd
from PyPDF2 import PdfReader
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ✅ Google Sheets 인증 함수
def authorize_gsheet(credential_file="google-credentials.json"):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credential_file, scope)
    client = gspread.authorize(creds)
    return client

# ✅ PDF 텍스트 추출
def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# ✅ 간단한 플롯 분석
def analyze_script_to_plots(text, movie_title):
    scenes = re.split(r'\n{2,}', text)[:8]
    results = []
    for i, scene in enumerate(scenes):
        plot_num = i + 1
        progress = int((plot_num - 1) / max(len(scenes) - 1, 1) * 100)
        main_emotion = max(0, min(100, 60 - i * 5))
        sub_emotion = max(0, min(100, 50 + i * 3))
        tension = max(0, min(100, i * 15))
        genre = "드라마"
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

# ✅ 결과를 Google Sheets에 저장
def upload_to_gsheet(df, sheet_url, sheet_name, credential_file):
    client = authorize_gsheet(credential_file)
    sheet = client.open_by_url(sheet_url).worksheet(sheet_name)
    for _, row in df.iterrows():
        sheet.append_row(row.values.tolist(), value_input_option="USER_ENTERED")

# ✅ 메인 실행 함수
def main():
    # PDF 경로 및 인증 키 경로 입력
    pdf_path = input("PDF 파일 경로를 입력하세요: ").strip()
    credential_file = input("Google 인증 JSON 경로를 입력하세요: ").strip()

    # Google Sheet 정보
    sheet_url = "https://docs.google.com/spreadsheets/d/1PdE87G6sENx4sQk1swCNPnmrZrEHpHBBRQwNKWLFdEQ/edit#gid=1348359652"
    sheet_name = "plot"

    # 영화제목은 파일명에서 추출
    movie_title = os.path.basename(pdf_path).replace(".pdf", "")

    # 분석 및 업로드
    print("⏳ 텍스트 추출 중...")
    text = extract_text_from_pdf(pdf_path)

    print("🧠 분석 중...")
    df = analyze_script_to_plots(text, movie_title)
    print(df)

    print("📤 Google Sheets에 저장 중...")
    upload_to_gsheet(df, sheet_url, sheet_name, credential_file)
    print("✅ 저장 완료!")

if __name__ == "__main__":
    main()
