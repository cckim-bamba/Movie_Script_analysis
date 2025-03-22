import os
import re
import json
from collections import Counter
from PyPDF2 import PdfReader
from konlpy.tag import Okt

# 블랙리스트 JSON 파일 로드
def load_blacklist(json_path="blacklist.json"):
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

EXCLUSION_TERMS = load_blacklist()

# PDF에서 텍스트 추출 (PyPDF2 사용)
def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        return text if text.strip() else ""
    except Exception as e:
        print(f"PDF 텍스트 추출 중 오류: {str(e)}")
        return ""

# KONLPY 형태소 분석 기반 등장인물 추출
def extract_names_with_nlp(text):
    try:
        okt = Okt()
        nouns = okt.nouns(text)
        noun_counts = Counter(nouns)
        return {n: c for n, c in noun_counts.items() if c >= 100 and len(n) >= 2 and n not in EXCLUSION_TERMS}
    except Exception as e:
        print(f"형태소 분석 중 오류: {str(e)}")
        return {}

# "이름 + 직책" 패턴 찾기 (예: "고 반장", "최 형사")
def extract_character_titles(text):
    pattern = re.compile(r"\b([가-힣]{1,2})\s(반장|형사|선생|부장|과장|대리|사장|회장|팀장|사원|대표|실장|소장|상무|이사|부사장|사무관|교수|차장|본부장|원장|청장|주임|총리|장관|총장|국장|계장|팀원|부원장|서기관|검사|변호사|의사|간호사|조교|경위|순경|경사|경감|경정|총경|경무관|교장|강사|교감|교사)\b")
    matches = pattern.findall(text)
    character_mentions = [f"{match[0]} {match[1]}".strip() for match in matches if match]
    return Counter({char: count for char, count in Counter(character_mentions).items() if count >= 100})

# 대화 패턴에서 등장인물 추출
def extract_dialogue_speakers(text):
    # 이름 + ':' 형태의 패턴 찾기
    dialogue_pattern = re.compile(r'([가-힣a-zA-Z\s]{1,10})[\s]*:')
    matches = dialogue_pattern.findall(text)
    
    # 이름 클린업 및 카운팅
    speakers = [name.strip() for name in matches if len(name.strip()) >= 2]
    return Counter({speaker: count for speaker, count in Counter(speakers).items() if count >= 20})

# 최종 등장인물 정리
def analyze_script(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    if not text:
        print(f"PDF에서 텍스트를 추출할 수 없습니다: {pdf_path}")
        return []
    
    character_counts = extract_character_titles(text)
    nlp_characters = extract_names_with_nlp(text)
    dialogue_speakers = extract_dialogue_speakers(text)
    
    # 모든 소스에서 추출한 등장인물 통합
    final_characters = Counter()
    final_characters.update(character_counts)
    final_characters.update(nlp_characters)
    final_characters.update(dialogue_speakers)
    
    return [{"name": name, "count": count} for name, count in final_characters.most_common(30)]

# SQLite에 저장할 데이터 처리
def process_character_data(pdf_path):
    character_data = analyze_script(pdf_path)
    
    if not character_data:
        print(f"❌ '{pdf_path}'에서 등장인물 데이터 없음")
    
    return character_data

if __name__ == "__main__":
    # 테스트용 코드
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        characters = process_character_data(pdf_path)
        print(f"추출된 등장인물: {len(characters)}명")
        for char in characters:
            print(f"{char['name']}: {char['count']}회 등장")
    else:
        print("사용법: python character_extraction.py [PDF 파일 경로]")