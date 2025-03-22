import os
import re
import time
import json
import sqlite3
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from db_schema import get_db_connection

# 환경 변수 로드
load_dotenv()

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def clean_script_text(text):
    """스크립트 텍스트 정리"""
    # 불필요한 공백 제거
    text = re.sub(r'\s+', ' ', text)
    # 페이지 번호 제거
    text = re.sub(r'\b\d+\s*/\s*\d+\b', '', text)
    return text.strip()

def chunk_text(text, max_chunk_size=8000):
    """텍스트를 적절한 크기로 분할"""
    # PDF가 너무 길면 처음과 중간, 끝부분만 분석
    if len(text) > 16000:
        # 처음 5000자
        start_chunk = text[:5000]
        # 중간 3000자
        middle_start = len(text) // 2 - 1500
        middle_chunk = text[middle_start:middle_start + 3000]
        # 마지막 5000자
        end_chunk = text[-5000:]
        return [start_chunk, middle_chunk, end_chunk]
    
    # 16000자 이하인 경우 기존 방식대로 분할
    words = text.split()
    chunks = []
    current_chunk = []
    current_size = 0
    
    for word in words:
        if current_size + len(word) + 1 > max_chunk_size:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_size = len(word)
        else:
            current_chunk.append(word)
            current_size += len(word) + 1
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def extract_text_from_pdf(pdf_file):
    """PDF 파일에서 텍스트 추출"""
    try:
        from PyPDF2 import PdfReader
        
        if isinstance(pdf_file, str):  # 파일 경로
            reader = PdfReader(pdf_file)
        else:  # 업로드된 파일 객체
            reader = PdfReader(pdf_file)
            
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"PDF 파일 처리 중 오류 발생: {str(e)}"

def summarize_script(text, debug=False):
    """스크립트 요약"""
    if not text or len(text) < 100:
        return "텍스트가 너무 짧거나 없습니다."
    
    try:
        # 텍스트 청소
        cleaned_text = clean_script_text(text)
        
        # 처리 시간 단축을 위해 더 효율적인 방법 사용
        # 텍스트가 매우 길면 처음, 중간, 끝 부분만 사용
        if len(cleaned_text) > 12000:
            # 직접 API로 전체 내용 요약 시도
            if debug: print("🔄 텍스트가 매우 길어 처음/중간/끝 부분만 분석합니다.")
            response = client.chat.completions.create(
                model="gpt-3.5-turbo", # 더 빠른 모델 사용
                messages=[
                    {"role": "system", "content": "당신은 효율적인 스크립트 분석 전문가입니다. 긴 스크립트의 핵심 내용을 빠르게 분석해야 합니다."},
                    {"role": "user", "content": f"다음 스크립트의 처음, 중간, 끝 부분을 보고 전체 내용을 추론하여 분석해주세요. 주요 인물, 관계, 사건, 줄거리, 주제를 파악하세요:\n\n[스크립트 시작 부분]\n{cleaned_text[:4000]}\n\n[스크립트 중간 부분]\n{cleaned_text[len(cleaned_text)//2-2000:len(cleaned_text)//2+2000]}\n\n[스크립트 끝 부분]\n{cleaned_text[-4000:]}"}
                ],
                temperature=0.5,
                max_tokens=1500
            )
            return response.choices[0].message.content
        
        # 중간 길이 스크립트는 두 부분만 분석
        elif len(cleaned_text) > 6000:
            if debug: print("🔄 텍스트가 중간 길이로 시작/끝 부분만 분석합니다.")
            # 시작과 끝 부분 분석
            start_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 스크립트 분석 전문가입니다. 주어진 스크립트를 분석하여 핵심 정보를 추출해 주세요."},
                    {"role": "user", "content": f"다음 스크립트의 시작 부분을 분석해 주세요. 주요 인물과 관계, 배경 설정에 집중하세요:\n\n{cleaned_text[:5000]}"}
                ],
                temperature=0.5,
                max_tokens=1000
            )
            
            end_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 스크립트 분석 전문가입니다. 주어진 스크립트를 분석하여 핵심 정보를 추출해 주세요."},
                    {"role": "user", "content": f"다음 스크립트의 마지막 부분을 분석해 주세요. 결말, 주제, 메시지에 집중하세요:\n\n{cleaned_text[-5000:]}"}
                ],
                temperature=0.5,
                max_tokens=1000
            )
            
            # 결과 통합
            combined_analysis = [start_response.choices[0].message.content, end_response.choices[0].message.content]
            
            final_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 스크립트 분석 전문가입니다. 부분 분석을 통합하여 전체적인 요약을 제공해 주세요."},
                    {"role": "user", "content": f"스크립트의 시작과 끝 부분 분석을 통합하여 종합적인 요약을 만들어주세요:\n\n[시작 부분 분석]\n{combined_analysis[0]}\n\n[끝 부분 분석]\n{combined_analysis[1]}"}
                ],
                temperature=0.5,
                max_tokens=1500
            )
            
            return final_response.choices[0].message.content
        
        # 짧은 스크립트는 한 번에 분석
        else:
            if debug: print("🔄 텍스트가 짧아 전체를 한 번에 분석합니다.")
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 영화/드라마 스크립트 분석 전문가입니다. 주어진 스크립트를 분석하여 다음 정보를 추출해 주세요: 1) 주요 인물과 관계, 2) 주요 사건과 줄거리, 3) 주제와 메시지."},
                    {"role": "user", "content": f"다음 스크립트를 분석해 주세요:\n\n{cleaned_text}"}
                ],
                temperature=0.5,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
        
    except Exception as e:
        # AI API 오류 시 기본 정보 제공
        return f"""
## 텍스트 기본 분석 결과
- **텍스트 길이**: {len(text):,}자

## 참고사항
OpenAI API 호출 중 오류가 발생했습니다: {str(e)}
상세한 분석을 위해서는 OpenAI API 키를 확인하세요.
        """

def extract_structured_data(summary):
    """요약에서 구조화된 데이터 추출"""
    try:
        # API 오류 메시지가 포함되어 있는지 확인
        if "API 호출 중 오류가 발생했습니다" in summary:
            # 기본 분석 결과만 반환
            return "OpenAI API 호출 중 오류가 발생했습니다. 상세 분석을 위해 API 설정을 확인하세요."
        
        # 정상적인 요약이 있는 경우 API 사용
        prompt = f"""
        다음 스크립트 요약에서 구조화된 데이터를 효율적으로 추출해 주세요:

        {summary}

        다음 형식으로 결과를 JSON 형식으로 반환해 주세요:
        {{
            "title": "작품 제목 (추정)",
            "genre": "추정 장르",
            "main_characters": [
                {{"name": "캐릭터1", "description": "설명"}},
                {{"name": "캐릭터2", "description": "설명"}}
            ],
            "plot_points": [
                "핵심 줄거리 요소1",
                "핵심 줄거리 요소2"
            ],
            "themes": [
                "주제1", 
                "주제2"
            ]
        }}
        """

        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # 더 빠른 모델 사용
            messages=[
                {"role": "system", "content": "당신은 효율적인 스크립트 분석가로, 요약 내용에서 핵심 정보를 JSON 형식으로 추출합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=800
        )
        
        result = response.choices[0].message.content
        
        # JSON 형식 추출 (텍스트에서 JSON 부분만 추출)
        json_pattern = r'```json\n(.*?)\n```'
        json_match = re.search(json_pattern, result, re.DOTALL)
        
        if json_match:
            # JSON 코드 블록 내용 추출
            json_str = json_match.group(1)
        else:
            # 전체 응답을 JSON으로 간주
            json_str = result
        
        # JSON 파싱 시도
        try:
            data = json.loads(json_str)
            return data
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 원본 텍스트 반환
            return result
    
    except Exception as e:
        # 오류 발생 시 기본 정보만 반환
        return f"구조화된 데이터 추출 중 오류 발생: {str(e)}"

def analyze_characters_and_relationships(text):
    """스크립트에서 등장인물과 관계를 분석"""
    try:
        # 텍스트 청소
        cleaned_text = clean_script_text(text)
        
        # 텍스트 길이에 따라 처리 (너무 길면 일부만)
        if len(cleaned_text) > 10000:
            analysis_text = f"{cleaned_text[:5000]}\n\n...\n\n{cleaned_text[-5000:]}"
        else:
            analysis_text = cleaned_text
            
        # 등장인물 분석 요청
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # 비용 효율적 모델
            messages=[
                {"role": "system", "content": "당신은 스크립트에서 등장인물과 그들의 관계를 분석하는 전문가입니다."},
                {"role": "user", "content": f"""다음 스크립트를 분석하여 등장인물과 그들의 관계를 상세히 추출해 주세요:

{analysis_text}

다음 형식으로 결과를 반환해 주세요:
1. 등장인물 목록: 각 인물의 이름과 간략한 설명
2. 주요 관계: 중요한 인물 관계를 설명
3. 계층 구조: 인물 간의 관계를 계층 구조로 표현 (예: 가족 관계, 직장 관계 등)
                """}
            ],
            temperature=0.5,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        # API 오류 시 기본 메시지 반환
        return f"등장인물 분석 중 오류 발생: {str(e)}"

def generate_character_tree(text):
    """등장인물 관계를 트리 구조 형태의 Mermaid 다이어그램으로 생성"""
    try:
        # 텍스트 청소
        cleaned_text = clean_script_text(text)
        
        # 너무 길면 처음과 끝 부분만 분석
        if len(cleaned_text) > 8000:
            analysis_text = f"{cleaned_text[:4000]}\n\n...\n\n{cleaned_text[-4000:]}"
        else:
            analysis_text = cleaned_text
        
        # 관계도 생성 요청
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 스크립트 분석가이며, 등장인물 관계도를 Mermaid 다이어그램 형식으로 생성하는 전문가입니다."},
                {"role": "user", "content": f"""다음 스크립트를 분석하여 주요 등장인물과 그들의 관계를 트리 구조로 표현하는 Mermaid 다이어그램 코드를 생성해 주세요.

{analysis_text}

1. 가장 중요한 인물이나 관계의 중심이 되는 인물을 루트 노드로 설정하세요.
2. 등장인물들의 관계(가족, 친구, 동료 등)를 나타내는 링크를 추가하세요.
3. 최대 8-10명의 주요 인물만 포함하세요.
4. 인물 옆에 역할이나 특징을 간략히 표시하세요.

다음과 같은 형식의 Mermaid 코드를 생성해 주세요:

```mermaid
graph TD
  A[주인공] --> B[친구]
  A --> C[가족]
  B --> D[친구의 동료]
  ...
```
                """}
            ],
            temperature=0.5,
            max_tokens=800
        )
        
        # Mermaid 코드 추출
        mermaid_response = response.choices[0].message.content
        
        # Mermaid 코드 블록 추출
        mermaid_pattern = re.compile(r'```mermaid\n(.*?)```', re.DOTALL)
        match = mermaid_pattern.search(mermaid_response)
        
        if match:
            mermaid_code = match.group(1).strip()
            return mermaid_code
        else:
            # 코드 블록으로 감싸지 않은 경우
            if "graph" in mermaid_response or "flowchart" in mermaid_response:
                return mermaid_response  
            else:
                return "graph TD\n  A[분석 오류] --> B[관계도를 생성할 수 없습니다]"
            
    except Exception as e:
        # API 오류 시 기본 트리 구조 생성
        return f"graph TD\n  A[오류] --> B[등장인물 관계도 생성 실패: {str(e)}]"

def analyze_sentiment(text, movie_id):
    """스크립트의 전반적인 감정을 분석"""
    try:
        # 텍스트 청소
        cleaned_text = clean_script_text(text)
        
        # 텍스트가 너무 길면 부분만 사용
        if len(cleaned_text) > 8000:
            analysis_text = f"{cleaned_text[:4000]}\n\n...\n\n{cleaned_text[-4000:]}"
        else:
            analysis_text = cleaned_text
        
        # 감정 분석 요청
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 스크립트의 감정 분석을 수행하는 전문가입니다."},
                {"role": "user", "content": f"""다음 스크립트의 전반적인 감정과 분위기를 분석해 주세요.

{analysis_text}

다음 형식으로 JSON 결과를 반환해 주세요:
{{
    "overall_sentiment": "전체적인 감정 (긍정적/부정적/중립적)",
    "sentiment_score": 감정 점수 (-1.0 ~ 1.0, 부정적일수록 -1에 가깝고 긍정적일수록 1에 가까움),
    "dominant_emotions": ["주요 감정1", "주요 감정2", "주요 감정3"],
    "mood_description": "전반적인 분위기에 대한 설명",
    "emotional_arcs": ["감정 변화 곡선에 대한 설명"]
}}
                """}
            ],
            temperature=0.5,
            max_tokens=800
        )
        
        # JSON 결과 추출
        result = response.choices[0].message.content
        
        # JSON 형식 추출 (텍스트에서 JSON 부분만 추출)
        json_pattern = r'```json\n(.*?)\n```'
        json_match = re.search(json_pattern, result, re.DOTALL)
        
        if json_match:
            # JSON 코드 블록 내용 추출
            json_str = json_match.group(1)
        else:
            # 전체 응답을 JSON으로 간주
            json_str = result
        
        # JSON 파싱 시도
        try:
            data = json.loads(json_str)
            
            # 데이터베이스에 감정 분석 저장
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 전체 감정 분석 저장
            cursor.execute("""
                INSERT INTO sentiment_analysis 
                (movie_id, sentiment_score, sentiment_label, sentiment_text)
                VALUES (?, ?, ?, ?)
            """, (
                movie_id, 
                data.get('sentiment_score', 0), 
                data.get('overall_sentiment', 'N/A'),
                json.dumps(data)
            ))
            
            conn.commit()
            conn.close()
            
            return data
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 원본 텍스트 반환
            return result
    
    except Exception as e:
        # 오류 발생 시 기본 정보만 반환
        return f"감정 분석 중 오류 발생: {str(e)}"

def save_plot_analysis(movie_id, structured_data):
    """줄거리 분석 결과를 데이터베이스에 저장"""
    try:
        if isinstance(structured_data, str):
            # 문자열인 경우 JSON 파싱 시도
            try:
                data = json.loads(structured_data)
            except json.JSONDecodeError:
                return False
        else:
            data = structured_data
            
        # 줄거리 요소 추출
        plot_points = data.get('plot_points', [])
        if not plot_points:
            return False
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 기존 데이터 삭제
        cursor.execute("DELETE FROM plot_analysis WHERE movie_id = ?", (movie_id,))
        
        # 새 데이터 삽입
        for i, plot in enumerate(plot_points):
            cursor.execute("""
                INSERT INTO plot_analysis 
                (movie_id, plot_element, plot_description, plot_order)
                VALUES (?, ?, ?, ?)
            """, (movie_id, f"plot_point_{i+1}", plot, i+1))
        
        # 주제 데이터 추가
        themes = data.get('themes', [])
        for i, theme in enumerate(themes):
            cursor.execute("""
                INSERT INTO plot_analysis 
                (movie_id, plot_element, plot_description, plot_order)
                VALUES (?, ?, ?, ?)
            """, (movie_id, f"theme_{i+1}", theme, 100+i))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"줄거리 분석 저장 중 오류: {str(e)}")
        return False

def save_character_relationships(movie_id, character_analysis, conn=None):
    """등장인물 관계 분석 결과를 데이터베이스에 저장"""
    try:
        close_conn = False
        if conn is None:
            conn = get_db_connection()
            close_conn = True
            
        cursor = conn.cursor()
        
        # 등장인물 ID 가져오기
        cursor.execute("SELECT character_id, name FROM characters WHERE movie_id = ?", (movie_id,))
        characters = {name.lower(): char_id for char_id, name in cursor.fetchall()}
        
        # 관계 패턴 찾기
        relation_patterns = [
            r'(\w+)와\(과\)\s*(\w+)의\s*관계[:：]?\s*([^,\.]+)',
            r'(\w+)와\(과\)\s*(\w+)[:：]?\s*([^,\.]+)',
            r'(\w+)와\(과\)\s*(\w+)\s*사이[:：]?\s*([^,\.]+)',
            r'(\w+)와\(과\)\s*(\w+)\s*-\s*([^,\.]+)',
            r'(\w+)[:：]\s*(\w+)의\s*([^,\.]+)'
        ]
        
        relations_found = []
        
        for pattern in relation_patterns:
            matches = re.finditer(pattern, character_analysis, re.MULTILINE)
            for match in matches:
                char1, char2, rel_type = match.groups()
                char1 = char1.strip().lower()
                char2 = char2.strip().lower()
                rel_type = rel_type.strip()
                
                if char1 in characters and char2 in characters:
                    relations_found.append((
                        characters[char1],
                        characters[char2],
                        rel_type
                    ))
        
        # 관계 저장
        for char1_id, char2_id, rel_type in relations_found:
            # 이미 있는 관계인지 확인
            cursor.execute("""
                SELECT relationship_id FROM relationships
                WHERE movie_id = ? AND 
                      ((character1_id = ? AND character2_id = ?) OR
                       (character1_id = ? AND character2_id = ?))
            """, (movie_id, char1_id, char2_id, char2_id, char1_id))
            
            existing = cursor.fetchone()
            
            if existing:
                # 업데이트
                cursor.execute("""
                    UPDATE relationships
                    SET relationship_type = ?
                    WHERE relationship_id = ?
                """, (rel_type, existing[0]))
            else:
                # 새로 추가
                cursor.execute("""
                    INSERT INTO relationships
                    (movie_id, character1_id, character2_id, relationship_type)
                    VALUES (?, ?, ?, ?)
                """, (movie_id, char1_id, char2_id, rel_type))
        
        if close_conn:
            conn.commit()
            conn.close()
            
        return len(relations_found)
        
    except Exception as e:
        print(f"등장인물 관계 저장 중 오류: {str(e)}")
        if close_conn and conn:
            conn.close()
        return 0

def update_movie_summary(movie_id, summary, structured_data):
    """영화 요약 정보 업데이트"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # JSON 형식인지 확인
        if isinstance(structured_data, str):
            try:
                data = json.loads(structured_data)
            except json.JSONDecodeError:
                data = {"error": "JSON 파싱 오류"}
        else:
            data = structured_data
            
        # 영화 정보 업데이트
        cursor.execute("""
            UPDATE movies
            SET summary = ?,
                genre = ?,
                theme = ?
            WHERE movie_id = ?
        """, (
            summary,
            data.get('genre', ''),
            ', '.join(data.get('themes', [])) if isinstance(data.get('themes', []), list) else '',
            movie_id
        ))
        
        # 영화 제목이 있으면 업데이트
        if 'title' in data and data['title']:
            cursor.execute("""
                UPDATE movies
                SET title = ?
                WHERE movie_id = ?
            """, (data['title'], movie_id))
        
        conn.commit()
        
        # 줄거리 분석 저장
        save_plot_analysis(movie_id, data)
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"영화 요약 업데이트 중 오류: {str(e)}")
        return False

def process_ai_analysis(movie_id, text=None, pdf_path=None):
    """영화 스크립트의 AI 분석을 수행하고 데이터베이스에 저장"""
    try:
        # 텍스트 준비
        if text is None and pdf_path:
            text = extract_text_from_pdf(pdf_path)
        
        if not text or len(text) < 100:
            return {
                "success": False,
                "message": "텍스트가 너무 짧거나 없습니다."
            }
            
        # 요약 생성
        summary = summarize_script(text)
        
        # 구조화된 데이터 추출
        structured_data = extract_structured_data(summary)
        
        # 등장인물 및 관계 분석
        character_analysis = analyze_characters_and_relationships(text)
        
        # 관계도 생성
        character_tree = generate_character_tree(text)
        
        # 감정 분석
        sentiment = analyze_sentiment(text, movie_id)
        
        # 데이터베이스에 정보 저장
        conn = get_db_connection()
        
        # 영화 요약 업데이트
        update_movie_summary(movie_id, summary, structured_data)
        
        # 등장인물 관계 저장
        save_character_relationships(movie_id, character_analysis, conn)
        
        conn.close()
        
        return {
            "success": True,
            "summary": summary,
            "structured_data": structured_data,
            "character_analysis": character_analysis,
            "character_tree": character_tree,
            "sentiment": sentiment
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"AI 분석 중 오류 발생: {str(e)}"
        }

if __name__ == "__main__":
    # 테스트용 코드
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        text = extract_text_from_pdf(pdf_path)
        print(f"텍스트 길이: {len(text):,}자")
        
        # 영화 정보 가져오기
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("\n===== 영화 스크립트 분석 =====")
        
        # 파일명으로 영화 찾기
        movie_file = os.path.basename(pdf_path)
        cursor.execute("SELECT movie_id FROM movies WHERE filename = ?", (movie_file,))
        movie = cursor.fetchone()
        
        if movie:
            movie_id = movie[0]
            print(f"기존 영화 ID: {movie_id}를 분석합니다.")
        else:
            # 새 영화 추가
            from data_uploader import process_single_file
            process_single_file(conn, pdf_path)
            
            # 새로 생성된 영화 ID 가져오기
            cursor.execute("SELECT movie_id FROM movies WHERE filename = ?", (movie_file,))
            movie = cursor.fetchone()
            movie_id = movie[0] if movie else None
            
            if not movie_id:
                print("영화 등록에 실패했습니다.")
                conn.close()
                sys.exit(1)
                
            print(f"새 영화 ID: {movie_id}를 등록하고 분석합니다.")
        
        conn.close()
        
        # AI 분석 수행
        print("\n===== AI 분석 시작 =====")
        result = process_ai_analysis(movie_id, text=text)
        
        if result["success"]:
            print("\n✅ 분석 완료!")
            print(f"- 요약: {len(result['summary'])}자")
            print(f"- 등장인물 분석: {len(result['character_analysis'])}자")
            print(f"- 관계도 생성: {'성공' if result['character_tree'] else '실패'}")
            
            # 감정 분석 결과 출력
            if isinstance(result['sentiment'], dict):
                print("\n===== 감정 분석 =====")
                print(f"- 전체 감정: {result['sentiment'].get('overall_sentiment', 'N/A')}")
                print(f"- 감정 점수: {result['sentiment'].get('sentiment_score', 'N/A')}")
                emotions = ', '.join(result['sentiment'].get('dominant_emotions', ['N/A']))
                print(f"- 주요 감정: {emotions}")
            
            print("\n분석이 데이터베이스에 저장되었습니다.")
        else:
            print(f"\n❌ 분석 실패: {result['message']}")
    else:
        print("사용법: python ai_analyzer.py [PDF 파일 경로]")