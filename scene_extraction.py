import os
import re
from PyPDF2 import PdfReader

# PDF에서 텍스트 추출 
def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        return text if text.strip() else ""
    except Exception as e:
        print(f"PDF 텍스트 추출 중 오류: {str(e)}")
        return ""

# 장면(Scene) 추출 함수
def extract_scenes(text):
    """스크립트에서 장면들을 추출"""
    # 장면 패턴: 숫자. [장면 헤딩]
    scene_pattern = r'\n(\d+)\.\s*([^\n]+)'
    
    # 대체 패턴: #숫자 [장면 헤딩] 또는 S#숫자 [장면 헤딩]
    alt_scene_pattern1 = r'\n[#S]+\s*(\d+)\s*[\.]*\s*([^\n]+)'
    
    # INT/EXT 패턴
    int_ext_pattern = r'\n(?:INT|EXT|내부|외부)[\.]*\s*([^\n]+)'
    
    # 주요 패턴 우선 적용
    scene_starts = [(m.start(), m.group(1), m.group(2).strip()) for m in re.finditer(scene_pattern, text)]
    
    # 결과가 적으면 대체 패턴 시도
    if len(scene_starts) < 10:
        scene_starts = [(m.start(), m.group(1), m.group(2).strip()) for m in re.finditer(alt_scene_pattern1, text)]
    
    # 여전히 적으면 INT/EXT 패턴 시도 (이 경우 장면 번호 대신 순서 번호 사용)
    if len(scene_starts) < 10:
        scene_starts = [(m.start(), str(i+1), m.group(1).strip()) 
                         for i, m in enumerate(re.finditer(int_ext_pattern, text))]
    
    scenes = []
    
    for i in range(len(scene_starts)):
        start_pos, scene_number, location = scene_starts[i]
        end_pos = scene_starts[i+1][0] if i < len(scene_starts) - 1 else len(text)
        scene_text = text[start_pos:end_pos].strip()
        
        if not scene_text:
            continue
        
        # 시간대 추출 (낮/밤/새벽 등)
        time_match = re.search(r'\b(밤|낮|새벽|저녁|아침|DAY|NIGHT|MORNING|EVENING|아침|오전|오후|저녁|밤)\b', 
                               location, re.IGNORECASE)
        time_of_day = time_match.group(1) if time_match else "N/A"
        
        # 내부/외부 설정 추출
        setting = "INT"  # 기본값
        if any(ext in location.upper() for ext in ["외부", "EXT", "EXTERNAL", "야외"]):
            setting = "EXT"
        
        scene = {
            "scene_number": scene_number,
            "heading": f"{scene_number}. {location}",
            "location": location,
            "setting": setting,
            "time_of_day": time_of_day
        }
        
        scenes.append(scene)
    
    return scenes

# 씬 데이터 처리 함수
def process_scene_data(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    if not text:
        print(f"❌ PDF에서 텍스트를 추출할 수 없습니다: {pdf_path}")
        return []
    
    scenes = extract_scenes(text)
    return [{"scene_number": s["scene_number"], 
             "heading": s["heading"],
             "location": s["location"], 
             "setting": s["setting"], 
             "time_of_day": s["time_of_day"]} 
            for s in scenes]

if __name__ == "__main__":
    # 테스트용 코드
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        scenes = process_scene_data(pdf_path)
        print(f"추출된 장면: {len(scenes)}개")
        for i, scene in enumerate(scenes[:10]):  # 처음 10개만 출력
            print(f"{i+1}. {scene['heading']} - {scene['setting']} / {scene['time_of_day']}")
        if len(scenes) > 10:
            print(f"... 외 {len(scenes) - 10}개")
    else:
        print("사용법: python scene_extraction.py [PDF 파일 경로]")