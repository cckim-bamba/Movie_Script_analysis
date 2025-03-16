import openai
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# API 키 가져오기
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("API Key가 설정되지 않았습니다. .env 파일을 확인하세요.")

# OpenAI 클라이언트 생성 (버전 1.0 이상 방식)
client = openai.OpenAI()

# GPT API 호출
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "당신은 영화 대본 분석 전문가입니다."},
        {"role": "user", "content": "이 대본을 분석해서 질문에 답을 해, 질문에 [Narrative]라고 표시되어 있으면 서술형으로, 없다면 단답형으로 답변해줘"}
    ]
)

# 응답 출력
print(response.choices[0].message.content)