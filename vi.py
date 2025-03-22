import streamlit as st
import os
import time
import json
import pandas as pd
import sqlite3
from datetime import datetime
from db_schema import get_db_connection, init_database
from character_extraction import process_character_data
from scene_extraction import process_scene_data
from data_uploader import process_single_file, list_movies, delete_movie_data
from ai_analyzer import extract_text_from_pdf, process_ai_analysis

# 페이지 설정
st.set_page_config(
    page_title="스크립트 분석기",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 사용자 정의 CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .subheader {
        font-size: 1.5rem;
        color: #424242;
        margin-bottom: 1rem;
    }
    .info-text {
        background-color: #E3F2FD;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .result-container {
        background-color: #FAFAFA;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-top: 1rem;
        border: 1px solid #E0E0E0;
    }
    .processing-status {
        text-align: center;
        margin: 2rem 0;
        font-size: 1.2rem;
        color: #1E88E5;
    }
    .character-box {
        background-color: #F5F5F5;
        border-left: 4px solid #1976D2;
        padding: 1rem;
        margin-bottom: 0.5rem;
        border-radius: 0 0.3rem 0.3rem 0;
    }
    .relationship-box {
        background-color: #FFF8E1;
        border-left: 4px solid #FFC107;
        padding: 1rem;
        margin-bottom: 0.5rem;
        border-radius: 0 0.3rem 0.3rem 0;
    }
    .tree-container {
        border: 1px solid #E0E0E0;
        border-radius: 0.5rem;
        padding: 1rem;
        background-color: white;
    }
    .delete-button {
        background-color: #F44336;
        color: white;
    }
    .stat-box {
        background-color: #F5F5F5;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stat-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1976D2;
    }
    .stat-label {
        font-size: 0.9rem;
        color: #616161;
    }
    </style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'summary' not in st.session_state:
    st.session_state.summary = None
if 'structured_data' not in st.session_state:
    st.session_state.structured_data = None
if 'dataframe' not in st.session_state:
    st.session_state.dataframe = None
if 'filename' not in st.session_state:
    st.session_state.filename = None
if 'extracted_text' not in st.session_state:
    st.session_state.extracted_text = None
if 'character_analysis' not in st.session_state:
    st.session_state.character_analysis = None
if 'character_tree' not in st.session_state:
    st.session_state.character_tree = None
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'current_movie_id' not in st.session_state:
    st.session_state.current_movie_id = None
if 'sentiment_analysis' not in st.session_state:
    st.session_state.sentiment_analysis = None

# 데이터베이스 초기화 확인
def check_and_init_database():
    """데이터베이스 존재 여부 확인 및 초기화"""
    db_exists = os.path.exists("scripts.db")
    if not db_exists:
        init_database()
        st.success("✅ 데이터베이스가 초기화되었습니다.")
    return db_exists

# 영화 정보 가져오기
def get_movie_data(movie_id):
    """영화 ID로 영화 데이터 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 영화 정보 조회
    cursor.execute("""
        SELECT movie_id, title, filename, genre, theme, summary
        FROM movies
        WHERE movie_id = ?
    """, (movie_id,))
    
    movie_data = cursor.fetchone()
    
    if not movie_data:
        conn.close()
        return None
    
    movie_dict = {
        "movie_id": movie_data[0],
        "title": movie_data[1],
        "filename": movie_data[2],
        "genre": movie_data[3],
        "theme": movie_data[4],
        "summary": movie_data[5]
    }
    
    # 등장인물 조회
    cursor.execute("""
        SELECT character_id, name, count, description
        FROM characters
        WHERE movie_id = ?
        ORDER BY count DESC
    """, (movie_id,))
    
    characters = []
    for row in cursor.fetchall():
        characters.append({
            "character_id": row[0],
            "name": row[1],
            "count": row[2],
            "description": row[3] or ""
        })
    
    # 씬 조회
    cursor.execute("""
        SELECT scene_id, scene_number, heading, location, setting, time_of_day
        FROM scenes
        WHERE movie_id = ?
        ORDER BY scene_number
    """, (movie_id,))
    
    scenes = []
    for row in cursor.fetchall():
        scenes.append({
            "scene_id": row[0],
            "scene_number": row[1],
            "heading": row[2],
            "location": row[3],
            "setting": row[4],
            "time_of_day": row[5]
        })
    
    # 감정 분석 조회
    cursor.execute("""
        SELECT sentiment_id, sentiment_score, sentiment_label, sentiment_text
        FROM sentiment_analysis
        WHERE movie_id = ?
        ORDER BY sentiment_id DESC
        LIMIT 1
    """, (movie_id,))
    
    sentiment_row = cursor.fetchone()
    sentiment = None
    if sentiment_row:
        sentiment = {
            "sentiment_id": sentiment_row[0],
            "sentiment_score": sentiment_row[1],
            "sentiment_label": sentiment_row[2],
            "details": json.loads(sentiment_row[3]) if sentiment_row[3] else {}
        }
    
    # 줄거리 분석 조회
    cursor.execute("""
        SELECT plot_id, plot_element, plot_description, plot_order
        FROM plot_analysis
        WHERE movie_id = ?
        ORDER BY plot_order
    """, (movie_id,))
    
    plot_points = []
    themes = []
    
    for row in cursor.fetchall():
        if row[1].startswith("plot_point"):
            plot_points.append({
                "plot_id": row[0],
                "description": row[2],
                "order": row[3]
            })
        elif row[1].startswith("theme"):
            themes.append({
                "plot_id": row[0],
                "description": row[2],
                "order": row[3]
            })
    
    # 관계 조회
    cursor.execute("""
        SELECT r.relationship_id, c1.name, c2.name, r.relationship_type
        FROM relationships r
        JOIN characters c1 ON r.character1_id = c1.character_id
        JOIN characters c2 ON r.character2_id = c2.character_id
        WHERE r.movie_id = ?
    """, (movie_id,))
    
    relationships = []
    for row in cursor.fetchall():
        relationships.append({
            "relationship_id": row[0],
            "character1": row[1],
            "character2": row[2],
            "relationship_type": row[3]
        })
    
    conn.close()
    
    # 결과 데이터 구성
    result = {
        "movie": movie_dict,
        "characters": characters,
        "scenes": scenes,
        "sentiment": sentiment,
        "plot_points": plot_points,
        "themes": themes,
        "relationships": relationships
    }
    
    return result

# 데이터베이스 내 영화 목록 가져오기
def get_movie_list():
    """데이터베이스의 영화 목록 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT movie_id, title, filename, 
               datetime(last_modified, 'unixepoch', 'localtime') as modified_date
        FROM movies
        ORDER BY title
    """)
    
    movies = []
    for row in cursor.fetchall():
        movies.append({
            "movie_id": row[0],
            "title": row[1],
            "filename": row[2],
            "modified_date": row[3]
        })
    
    conn.close()
    return movies

# 데이터베이스 통계 가져오기
def get_db_stats():
    """데이터베이스 통계 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 영화 수
    cursor.execute("SELECT COUNT(*) FROM movies")
    movie_count = cursor.fetchone()[0]
    
    # 등장인물 수
    cursor.execute("SELECT COUNT(*) FROM characters")
    character_count = cursor.fetchone()[0]
    
    # 씬 수
    cursor.execute("SELECT COUNT(*) FROM scenes")
    scene_count = cursor.fetchone()[0]
    
    # 최다 등장인물 영화
    cursor.execute("""
        SELECT m.title, COUNT(c.character_id) as char_count
        FROM movies m
        JOIN characters c ON m.movie_id = c.movie_id
        GROUP BY m.movie_id
        ORDER BY char_count DESC
        LIMIT 1
    """)
    most_characters = cursor.fetchone()
    
    # 최다 씬 영화
    cursor.execute("""
        SELECT m.title, COUNT(s.scene_id) as scene_count
        FROM movies m
        JOIN scenes s ON m.movie_id = s.movie_id
        GROUP BY m.movie_id
        ORDER BY scene_count DESC
        LIMIT 1
    """)
    most_scenes = cursor.fetchone()
    
    conn.close()
    
    return {
        "movie_count": movie_count,
        "character_count": character_count,
        "scene_count": scene_count,
        "most_characters": most_characters,
        "most_scenes": most_scenes
    }

# 영화 데이터 삭제
def delete_movie(movie_id):
    """영화 데이터를 데이터베이스에서 삭제"""
    return delete_movie_data(get_db_connection(), movie_id=movie_id)

# Mermaid 다이어그램 생성
def generate_relationship_diagram(relationships, characters):
    """등장인물 관계를 Mermaid 다이어그램으로 생성"""
    if not relationships or not characters:
        return "graph TD\n  A[관계 데이터 없음]"
    
    # 캐릭터 ID 매핑
    char_ids = {}
    for i, char in enumerate(characters):
        char_name = char["name"]
        char_ids[char_name] = f"C{i}"
    
    # 노드 정의
    mermaid = "graph TD\n"
    for char in characters[:10]:  # 최대 10명만 표시
        char_id = char_ids[char["name"]]
        count = char["count"]
        mermaid += f"  {char_id}[{char['name']} ({count}회)]\n"
    
    # 관계 정의
    for rel in relationships:
        char1 = rel["character1"]
        char2 = rel["character2"]
        rel_type = rel["relationship_type"]
        
        if char1 in char_ids and char2 in char_ids:
            mermaid += f"  {char_ids[char1]} -->|{rel_type}| {char_ids[char2]}\n"
    
    return mermaid

# 애플리케이션 헤더
st.markdown("<h1 class='main-header'>📝 스크립트 분석기</h1>", unsafe_allow_html=True)
st.markdown("<p class='subheader'>PDF 스크립트를 업로드하면 등장인물, 씬 정보, AI 분석 결과를 확인할 수 있습니다.</p>", unsafe_allow_html=True)

# 데이터베이스 초기화 확인
check_and_init_database()

# 사이드바
with st.sidebar:
    st.header("ℹ️ 메뉴")
    
    menu_options = [
        "대시보드",
        "스크립트 업로드 및 분석",
        "영화 목록 및 분석 결과",
        "데이터베이스 관리"
    ]
    
    selected_menu = st.selectbox("메뉴 선택", menu_options)
    
    st.markdown("---")
    
    # 데이터베이스 통계 표시
    stats = get_db_stats()
    st.header("📊 통계")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='stat-box'><div class='stat-value'>{stats['movie_count']}</div><div class='stat-label'>영화</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='stat-box'><div class='stat-value'>{stats['character_count']}</div><div class='stat-label'>등장인물</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='stat-box'><div class='stat-value'>{stats['scene_count']}</div><div class='stat-label'>장면</div></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 📊 분석 항목")
    st.markdown("""
    - 제목 (추정)
    - 주요 인물과 관계
    - 주요 사건 및 줄거리
    - 주제와 메시지
    - 장르 (추정)
    - 등장인물 구조 분석
    - 관계도 (트리 구조)
    - 감정 분석
    """)

# 대시보드
if selected_menu == "대시보드":
    st.header("📊 스크립트 분석 대시보드")
    
    # 영화 목록
    movies = get_movie_list()
    
    # 통계 카드
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='stat-box'><div class='stat-value'>{stats['movie_count']}</div><div class='stat-label'>분석된 스크립트</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='stat-box'><div class='stat-value'>{stats['character_count']}</div><div class='stat-label'>등장인물</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='stat-box'><div class='stat-value'>{stats['scene_count']}</div><div class='stat-label'>장면</div></div>", unsafe_allow_html=True)
    
    st.markdown("### 🎬 최근 분석된 스크립트")
    
    if movies:
        # 정렬: 최근 수정일 기준
        recent_movies = sorted(movies, key=lambda x: x["modified_date"], reverse=True)[:5]
        
        for movie in recent_movies:
            with st.expander(f"{movie['title']} ({movie['filename']})"):
                movie_data = get_movie_data(movie['movie_id'])
                
                if movie_data:
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**장르:** {movie_data['movie']['genre'] or '정보 없음'}")
                        st.markdown(f"**주제:** {movie_data['movie']['theme'] or '정보 없음'}")
                        
                        if movie_data['movie']['summary']:
                            st.markdown("**요약:**")
                            st.markdown(movie_data['movie']['summary'][:300] + "..." if len(movie_data['movie']['summary']) > 300 else movie_data['movie']['summary'])
                        
                        # 등장인물 수, 씬 수 표시
                        st.markdown(f"**등장인물:** {len(movie_data['characters'])}명, **씬:** {len(movie_data['scenes'])}개")
                    
                    with col2:
                        if movie_data['sentiment']:
                            sentiment = movie_data['sentiment']
                            st.markdown("**감정 분석:**")
                            st.markdown(f"- 전체 감정: {sentiment['sentiment_label']}")
                            st.markdown(f"- 감정 점수: {sentiment['sentiment_score']:.2f}")
                            
                            if 'dominant_emotions' in sentiment['details']:
                                emotions = ', '.join(sentiment['details']['dominant_emotions'][:3])
                                st.markdown(f"- 주요 감정: {emotions}")
                    
                    # 영화 상세 정보 보기 버튼
                    if st.button(f"상세 정보 보기 ({movie['title']})", key=f"view_{movie['movie_id']}"):
                        st.session_state.current_movie_id = movie['movie_id']
                        st.rerun()
    else:
        st.info("분석된 스크립트가 없습니다. '스크립트 업로드 및 분석' 메뉴에서 PDF 파일을 업로드하세요.")
    
    # 최다 등장인물/씬 영화 표시
    st.markdown("### 🏆 통계")
    
    col1, col2 = st.columns(2)
    with col1:
        if stats['most_characters']:
            st.markdown(f"**최다 등장인물 스크립트:** {stats['most_characters'][0]} ({stats['most_characters'][1]}명)")
        else:
            st.markdown("**최다 등장인물 스크립트:** 정보 없음")
    
    with col2:
        if stats['most_scenes']:
            st.markdown(f"**최다 장면 스크립트:** {stats['most_scenes'][0]} ({stats['most_scenes'][1]}개)")
        else:
            st.markdown("**최다 장면 스크립트:** 정보 없음")

# 스크립트 업로드 및 분석
elif selected_menu == "스크립트 업로드 및 분석":
    st.header("📤 스크립트 업로드 및 분석")
    
    # 업로드 탭: 개별 파일 업로드 vs 폴더 일괄 처리
    upload_tab1, upload_tab2 = st.tabs(["개별 파일 업로드", "폴더 일괄 처리"])
    
    with upload_tab1:
        # 개별 파일 업로드
        uploaded_file = st.file_uploader("PDF 스크립트 파일을 업로드하세요", type=['pdf'])
        
        if uploaded_file is not None:
            st.markdown("<div class='info-text'>파일이 업로드되었습니다. 분석을 시작하려면 아래 버튼을 클릭하세요.</div>", unsafe_allow_html=True)
            
            # 현재 파일이 이전과 다른 경우 상태 초기화
            if st.session_state.filename != uploaded_file.name:
                st.session_state.filename = uploaded_file.name
                st.session_state.extracted_text = None
                st.session_state.summary = None
                st.session_state.structured_data = None
                st.session_state.dataframe = None
                st.session_state.character_analysis = None
                st.session_state.character_tree = None
                st.session_state.analysis_complete = False
                st.session_state.current_movie_id = None
                st.session_state.sentiment_analysis = None
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # 기본 분석 (등장인물, 씬 추출)
                if st.button("기본 분석 시작 (등장인물, 씬)", key="basic_analyze_button", use_container_width=True):
                    # 진행 상태 표시 및 진행 상태바
                    progress_placeholder = st.empty()
                    status_text = st.empty()
                    progress_bar = st.progress(0)
                    
                    # 임시 파일 저장
                    with open("temp_script.pdf", "wb") as f:
                        f.write(uploaded_file.getvalue())
                    
                    # SQLite 업로드 실행
                    status_text.markdown("<p class='processing-status'>PDF 분석 및 데이터베이스 저장 중...</p>", unsafe_allow_html=True)
                    
                    conn = get_db_connection()
                    result = process_single_file(conn, "temp_script.pdf")
                    
                    # 생성된 영화 ID 가져오기
                    cursor = conn.cursor()
                    cursor.execute("SELECT movie_id FROM movies WHERE filename = ?", ("temp_script.pdf",))
                    movie = cursor.fetchone()
                    movie_id = movie[0] if movie else None
                    conn.close()
                    
                    if movie_id:
                        st.session_state.current_movie_id = movie_id
                    
                    progress_bar.progress(100)
                    
                    # 완료 메시지
                    if result:
                        status_text.markdown("<p class='processing-status'>✅ 기본 분석 완료!</p>", unsafe_allow_html=True)
                        time.sleep(1)
                        
                        # UI 정리
                        status_text.empty()
                        progress_bar.empty()
                        progress_placeholder.empty()
                        
                        # 페이지 새로고침
                        st.rerun()
                    else:
                        status_text.markdown("<p class='processing-status'>❌ 분석 실패!</p>", unsafe_allow_html=True)
            
            with col2:
                # AI 분석 (요약, 관계, 감정 분석)
                if st.session_state.current_movie_id:
                    if st.button("AI 분석 시작 (요약, 관계, 감정)", key="ai_analyze_button", use_container_width=True):
                        # 진행 상태 표시 및 진행 상태바
                        progress_placeholder = st.empty()
                        status_text = st.empty()
                        progress_bar = st.progress(0)
                        
                        # PDF 텍스트 추출
                        status_text.markdown("<p class='processing-status'>PDF에서 텍스트 추출 중...</p>", unsafe_allow_html=True)
                        
                        # 임시 파일이 없으면 다시 저장
                        if not os.path.exists("temp_script.pdf"):
                            with open("temp_script.pdf", "wb") as f:
                                f.write(uploaded_file.getvalue())
                        
                        # AI 분석 실행
                        status_text.markdown("<p class='processing-status'>AI 분석 중... (몇 분 소요될 수 있습니다)</p>", unsafe_allow_html=True)
                        progress_bar.progress(30)
                        
                        # AI 분석 실행
                        result = process_ai_analysis(st.session_state.current_movie_id, pdf_path="temp_script.pdf")
                        
                        progress_bar.progress(100)
                        
                        # 완료 메시지
                        if result["success"]:
                            status_text.markdown("<p class='processing-status'>✅ AI 분석 완료!</p>", unsafe_allow_html=True)
                            time.sleep(1)
                            
                            # 분석 결과 저장
                            st.session_state.summary = result["summary"]
                            st.session_state.character_analysis = result["character_analysis"]
                            st.session_state.character_tree = result["character_tree"]
                            st.session_state.structured_data = result["structured_data"]
                            st.session_state.sentiment_analysis = result["sentiment"]
                            st.session_state.analysis_complete = True
                            
                            # UI 정리
                            status_text.empty()
                            progress_bar.empty()
                            progress_placeholder.empty()
                            
                            # 페이지 새로고침
                            st.rerun()
                        else:
                            status_text.markdown(f"<p class='processing-status'>❌ 분석 실패! {result['message']}</p>", unsafe_allow_html=True)
                else:
                    st.warning("먼저 기본 분석을 완료해야 AI 분석을 시작할 수 있습니다.")
    
    with upload_tab2:
        # 폴더 일괄 처리
        st.markdown("### 📁 폴더 일괄 처리")
        
        # 폴더 경로 입력
        folder_path = st.text_input("PDF 파일이 있는 폴더 경로 입력", "data")
        
        # 폴더 존재 확인 및 스캔
        if os.path.exists(folder_path):
            pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
            
            if pdf_files:
                st.success(f"폴더에서 {len(pdf_files)}개의 PDF 파일을 찾았습니다.")
                
                # 파일 목록 표시
                with st.expander("PDF 파일 목록"):
                    for i, file in enumerate(pdf_files, 1):
                        st.write(f"{i}. {file}")
                
                # 처리 옵션
                col1, col2 = st.columns(2)
                
                with col1:
                    # 선택된 파일만 처리
                    selected_files = st.multiselect("처리할 파일 선택 (미선택 시 전체 처리)", pdf_files)
                    
                    if not selected_files:
                        selected_files = pdf_files  # 미선택 시 전체 선택
                
                with col2:
                    # 분석 옵션
                    analysis_options = st.multiselect(
                        "분석 옵션 선택",
                        ["기본 분석 (등장인물, 씬)", "AI 분석 (요약, 관계, 감정)"],
                        default=["기본 분석 (등장인물, 씬)"]
                    )
                
                # 처리 버튼
                if st.button("선택한 파일 일괄 처리 시작", type="primary", use_container_width=True):
                    run_basic = "기본 분석 (등장인물, 씬)" in analysis_options
                    run_ai = "AI 분석 (요약, 관계, 감정)" in analysis_options
                    
                    if not run_basic and not run_ai:
                        st.error("최소한 하나의 분석 옵션을 선택해야 합니다.")
                    else:
                        # 진행 상태 표시
                        progress_placeholder = st.empty()
                        status_text = st.empty()
                        progress_bar = st.progress(0)
                        
                        total_files = len(selected_files)
                        processed_count = 0
                        success_count = 0
                        
                        # 결과 저장용 리스트
                        results = []
                        
                        # 데이터베이스 연결
                        conn = get_db_connection()
                        
                        for i, file in enumerate(selected_files):
                            # 진행 상태 업데이트
                            file_path = os.path.join(folder_path, file)
                            status_text.markdown(f"<p class='processing-status'>처리 중: {file} ({i+1}/{total_files})</p>", unsafe_allow_html=True)
                            progress_bar.progress((i) / total_files)
                            
                            try:
                                # 기본 분석 실행
                                if run_basic:
                                    result = process_single_file(conn, file_path)
                                    if not result:
                                        results.append({
                                            "file": file,
                                            "basic_analysis": "실패",
                                            "ai_analysis": "건너뜀"
                                        })
                                        continue
                                
                                # 영화 ID 가져오기
                                cursor = conn.cursor()
                                cursor.execute("SELECT movie_id FROM movies WHERE filename = ?", (file,))
                                movie = cursor.fetchone()
                                
                                if not movie:
                                    results.append({
                                        "file": file,
                                        "basic_analysis": "성공" if run_basic else "건너뜀",
                                        "ai_analysis": "실패 (영화 ID 찾을 수 없음)"
                                    })
                                    continue
                                
                                movie_id = movie[0]
                                
                                # AI 분석 실행
                                ai_result = "건너뜀"
                                if run_ai:
                                    ai_result_data = process_ai_analysis(movie_id, pdf_path=file_path)
                                    ai_result = "성공" if ai_result_data["success"] else f"실패 ({ai_result_data['message']})"
                                
                                # 결과 저장
                                results.append({
                                    "file": file,
                                    "basic_analysis": "성공" if run_basic else "건너뜀",
                                    "ai_analysis": ai_result
                                })
                                
                                success_count += 1
                                
                            except Exception as e:
                                # 오류 발생 시
                                results.append({
                                    "file": file,
                                    "basic_analysis": "오류",
                                    "ai_analysis": "오류",
                                    "error": str(e)
                                })
                            
                            processed_count += 1
                        
                        # 연결 닫기
                        conn.close()
                        
                        # 완료 표시
                        progress_bar.progress(1.0)
                        status_text.markdown(f"<p class='processing-status'>✅ 처리 완료! {success_count}/{total_files} 파일 성공</p>", unsafe_allow_html=True)
                        
                        # 결과 표시
                        st.markdown("### 처리 결과")
                        result_df = pd.DataFrame(results)
                        st.dataframe(result_df, use_container_width=True)
                        
                        # CSV 내보내기
                        csv = result_df.to_csv(index=False).encode('utf-8-sig')
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        st.download_button(
                            label="CSV로 처리 결과 내보내기",
                            data=csv,
                            file_name=f"batch_process_results_{timestamp}.csv",
                            mime='text/csv',
                            use_container_width=True
                        )
            else:
                st.warning(f"'{folder_path}' 폴더에 PDF 파일이 없습니다.")
        else:
            st.error(f"'{folder_path}' 폴더가 존재하지 않습니다. 유효한 폴더 경로를 입력하세요.")
            
            # 폴더 생성 옵션
            if st.button(f"'{folder_path}' 폴더 생성"):
                try:
                    os.makedirs(folder_path)
                    st.success(f"'{folder_path}' 폴더가 생성되었습니다.")
                except Exception as e:
                    st.error(f"폴더 생성 중 오류 발생: {str(e)}")
    
    # 기본 분석 결과 표시
    if st.session_state.current_movie_id:
        st.markdown("---")
        st.subheader("기본 분석 결과")
        
        movie_data = get_movie_data(st.session_state.current_movie_id)
        
        if movie_data:
            # 영화 정보
            st.markdown(f"**제목:** {movie_data['movie']['title']}")
            st.markdown(f"**파일명:** {movie_data['movie']['filename']}")
            
            # 탭 구성
            tab1, tab2 = st.tabs(["등장인물", "장면(씬)"])
            
            with tab1:
                if movie_data['characters']:
                    # 등장인물 표시
                    char_df = pd.DataFrame(movie_data['characters'])
                    if len(char_df) > 0:
                        char_df = char_df[['name', 'count', 'description']]
                        char_df.columns = ['이름', '등장 횟수', '설명']
                        st.dataframe(char_df, use_container_width=True)
                    else:
                        st.info("등장인물 데이터가 없습니다.")
                else:
                    st.info("등장인물 데이터가 없습니다.")
            
            with tab2:
                if movie_data['scenes']:
                    # 씬 표시
                    scene_df = pd.DataFrame(movie_data['scenes'])
                    if len(scene_df) > 0:
                        scene_df = scene_df[['scene_number', 'heading', 'setting', 'time_of_day']]
                        scene_df.columns = ['씬번호', '헤딩', '설정(내/외부)', '시간대']
                        st.dataframe(scene_df, use_container_width=True)
                    else:
                        st.info("씬 데이터가 없습니다.")
                else:
                    st.info("씬 데이터가 없습니다.")
    
    # AI 분석 결과 표시
    if st.session_state.analysis_complete and st.session_state.summary:
        st.markdown("---")
        st.subheader("AI 분석 결과")
        
        tab1, tab2, tab3, tab4 = st.tabs(["요약", "등장인물 분석", "관계도", "감정 분석"])
        
        with tab1:
            # 요약 정보
            st.markdown(st.session_state.summary)
            
            # 구조화된 데이터
            if isinstance(st.session_state.structured_data, dict):
                st.markdown("### 추출된 정보")
                
                # 장르 및 제목
                if 'genre' in st.session_state.structured_data:
                    st.markdown(f"**장르:** {st.session_state.structured_data['genre']}")
                if 'title' in st.session_state.structured_data:
                    st.markdown(f"**제목 (추정):** {st.session_state.structured_data['title']}")
                
                # 주제
                if 'themes' in st.session_state.structured_data and st.session_state.structured_data['themes']:
                    st.markdown("**주제:**")
                    for theme in st.session_state.structured_data['themes']:
                        st.markdown(f"- {theme}")
                
                # 등장인물
                if 'main_characters' in st.session_state.structured_data and st.session_state.structured_data['main_characters']:
                    st.markdown("**주요 등장인물:**")
                    for char in st.session_state.structured_data['main_characters']:
                        if isinstance(char, dict):
                            st.markdown(f"- **{char.get('name', '')}**: {char.get('description', '')}")
                
                # 줄거리 요소
                if 'plot_points' in st.session_state.structured_data and st.session_state.structured_data['plot_points']:
                    st.markdown("**줄거리 요소:**")
                    for i, point in enumerate(st.session_state.structured_data['plot_points'], 1):
                        st.markdown(f"{i}. {point}")
        
        with tab2:
            # 등장인물 분석
            if st.session_state.character_analysis:
                st.markdown(st.session_state.character_analysis)
            else:
                st.info("등장인물 분석 정보가 없습니다.")
        
        with tab3:
            # 관계도
            if st.session_state.character_tree:
                st.markdown("### 등장인물 관계도")
                st.code(st.session_state.character_tree, language="mermaid")
                st.info("위의 Mermaid 코드를 복사하여 [Mermaid Live Editor](https://mermaid.live/)에 붙여넣으면 시각적 관계도를 볼 수 있습니다.")
            else:
                st.info("관계도 정보가 없습니다.")
        
        with tab4:
            # 감정 분석
            if st.session_state.sentiment_analysis and isinstance(st.session_state.sentiment_analysis, dict):
                sentiment = st.session_state.sentiment_analysis
                
                # 기본 감정 정보
                st.markdown("### 감정 분석 결과")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**전체 감정:** {sentiment.get('overall_sentiment', 'N/A')}")
                    st.markdown(f"**감정 점수:** {sentiment.get('sentiment_score', 0):.2f}")
                
                with col2:
                    if 'dominant_emotions' in sentiment:
                        st.markdown("**주요 감정:**")
                        for emotion in sentiment['dominant_emotions']:
                            st.markdown(f"- {emotion}")
                
                # 분위기 설명
                if 'mood_description' in sentiment:
                    st.markdown("### 분위기 설명")
                    st.markdown(sentiment['mood_description'])
                
                # 감정 변화 곡선
                if 'emotional_arcs' in sentiment:
                    st.markdown("### 감정 변화 곡선")
                    for i, arc in enumerate(sentiment['emotional_arcs'], 1):
                        st.markdown(f"{i}. {arc}")
            else:
                st.info("감정 분석 정보가 없습니다.")

# 영화 목록 및 분석 결과
elif selected_menu == "영화 목록 및 분석 결과":
    st.header("🎬 영화 목록 및 분석 결과")
    
    # 디버그 정보 추가
    st.write("Debug: 영화 목록 메뉴가 선택되었습니다.")
    st.write(f"DB 파일 존재: {os.path.exists('scripts.db')}")
    
    # 영화 목록 가져오기
    movies = get_movie_list()
    
    if not movies:
        st.info("분석된 영화 데이터가 없습니다. '스크립트 업로드 및 분석' 메뉴에서 새로운 스크립트를 업로드하세요.")
    else:
        # 영화 선택 드롭다운
        movie_options = {f"{movie['title']} ({movie['filename']})": movie['movie_id'] for movie in movies}
        selected_movie_label = st.selectbox("영화 선택", list(movie_options.keys()))
        selected_movie_id = movie_options[selected_movie_label]
        
        st.session_state.current_movie_id = selected_movie_id
        
        # 선택된 영화 정보 표시
        movie_data = get_movie_data(selected_movie_id)
        
        if movie_data:
            st.markdown("---")
            
            # 영화 기본 정보
            st.subheader(f"📽️ {movie_data['movie']['title']}")
            st.markdown(f"**파일명:** {movie_data['movie']['filename']}")
            
            if movie_data['movie']['genre']:
                st.markdown(f"**장르:** {movie_data['movie']['genre']}")
            
            if movie_data['movie']['theme']:
                st.markdown(f"**주제:** {movie_data['movie']['theme']}")
            
            # 탭으로 구분된 정보
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["요약", "등장인물", "장면(씬)", "관계도", "감정 분석"])
            
            with tab1:
                # 요약 정보
                if movie_data['movie']['summary']:
                    st.markdown("### 스크립트 요약")
                    st.markdown(movie_data['movie']['summary'])
                    
                    # 줄거리 요소
                    if movie_data['plot_points']:
                        st.markdown("### 줄거리 요소")
                        for i, point in enumerate(movie_data['plot_points'], 1):
                            st.markdown(f"{i}. {point['description']}")
                    
                    # 주제
                    if movie_data['themes']:
                        st.markdown("### 주제")
                        for theme in movie_data['themes']:
                            st.markdown(f"- {theme['description']}")
                else:
                    st.info("요약 정보가 없습니다. AI 분석을 실행하면 요약 정보가 생성됩니다.")
            
            with tab2:
                # 등장인물 정보
                if movie_data['characters']:
                    st.markdown("### 등장인물 목록")
                    
                    # 테이블로 표시
                    char_df = pd.DataFrame([
                        {
                            "이름": char['name'],
                            "등장 횟수": char['count'],
                            "설명": char['description'] or ""
                        }
                        for char in movie_data['characters']
                    ])
                    
                    st.dataframe(char_df, use_container_width=True)
                    
                    # 주요 인물 시각화 (막대 그래프)
                    if len(movie_data['characters']) > 0:
                        st.markdown("### 주요 등장인물 빈도")
                        
                        # 상위 10명만 표시
                        top_chars = sorted(movie_data['characters'], key=lambda x: x['count'], reverse=True)[:10]
                        
                        # 차트 데이터
                        chart_data = pd.DataFrame({
                            "인물": [char['name'] for char in top_chars],
                            "등장 횟수": [char['count'] for char in top_chars]
                        })
                        
                        st.bar_chart(chart_data, x="인물", y="등장 횟수")
                else:
                    st.info("등장인물 정보가 없습니다.")
            
            with tab3:
                # 씬 정보
                if movie_data['scenes']:
                    st.markdown("### 장면(씬) 목록")
                    
                    # 테이블로 표시
                    scene_df = pd.DataFrame([
                        {
                            "씬번호": scene['scene_number'],
                            "헤딩": scene['heading'],
                            "설정": scene['setting'],
                            "시간대": scene['time_of_day']
                        }
                        for scene in movie_data['scenes']
                    ])
                    
                    st.dataframe(scene_df, use_container_width=True)
                    
                    # 내부/외부 씬 비율 (파이 차트)
                    if len(movie_data['scenes']) > 0:
                        st.markdown("### 내부/외부 씬 비율")
                        
                        # 내부/외부 설정 집계
                        settings = {}
                        for scene in movie_data['scenes']:
                            setting = scene['setting']
                            settings[setting] = settings.get(setting, 0) + 1
                        
                        # 차트 데이터
                        setting_data = pd.DataFrame({
                            "설정": list(settings.keys()),
                            "개수": list(settings.values())
                        })
                        
                        # 시간대별 집계
                        times = {}
                        for scene in movie_data['scenes']:
                            time = scene['time_of_day']
                            if time and time != "N/A":
                                times[time] = times.get(time, 0) + 1
                        
                        # 시간대 차트 데이터
                        if times:
                            time_data = pd.DataFrame({
                                "시간대": list(times.keys()),
                                "개수": list(times.values())
                            })
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write("**내부/외부 비율**")
                                st.bar_chart(setting_data, x="설정", y="개수")
                            
                            with col2:
                                st.write("**시간대 비율**")
                                st.bar_chart(time_data, x="시간대", y="개수")
                else:
                    st.info("씬 정보가 없습니다.")
            
            with tab4:
                # 관계도
                if movie_data['relationships']:
                    st.markdown("### 등장인물 관계도")
                    
                    # Mermaid 다이어그램 생성
                    mermaid_code = generate_relationship_diagram(
                        movie_data['relationships'], 
                        movie_data['characters']
                    )
                    
                    st.code(mermaid_code, language="mermaid")
                    st.info("위의 Mermaid 코드를 복사하여 [Mermaid Live Editor](https://mermaid.live/)에 붙여넣으면 시각적 관계도를 볼 수 있습니다.")
                    
                    # 관계 테이블
                    st.markdown("### 등장인물 관계 정보")
                    
                    relation_df = pd.DataFrame([
                        {
                            "인물1": rel['character1'],
                            "인물2": rel['character2'],
                            "관계": rel['relationship_type']
                        }
                        for rel in movie_data['relationships']
                    ])
                    
                    st.dataframe(relation_df, use_container_width=True)
                else:
                    st.info("관계도 정보가 없습니다. AI 분석을 실행하면 관계도가 생성됩니다.")
            
            with tab5:
                # 감정 분석
                if movie_data['sentiment']:
                    sentiment = movie_data['sentiment']
                    
                    st.markdown("### 감정 분석 결과")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**전체 감정:** {sentiment['sentiment_label']}")
                        st.markdown(f"**감정 점수:** {sentiment['sentiment_score']:.2f}")
                    
                    with col2:
                        if 'dominant_emotions' in sentiment['details']:
                            st.markdown("**주요 감정:**")
                            for emotion in sentiment['details']['dominant_emotions']:
                                st.markdown(f"- {emotion}")
                    
                    # 분위기 설명
                    if 'mood_description' in sentiment['details']:
                        st.markdown("### 분위기 설명")
                        st.markdown(sentiment['details']['mood_description'])
                    
                    # 감정 변화 곡선
                    if 'emotional_arcs' in sentiment['details']:
                        st.markdown("### 감정 변화 곡선")
                        for i, arc in enumerate(sentiment['details']['emotional_arcs'], 1):
                            st.markdown(f"{i}. {arc}")
                else:
                    st.info("감정 분석 정보가 없습니다. AI 분석을 실행하면 감정 분석 결과가 생성됩니다.")
            
            # 영화 삭제 버튼
            st.markdown("---")
            if st.button("🗑️ 이 영화 데이터 삭제", type="primary", use_container_width=True):
                if delete_movie(selected_movie_id):
                    st.success(f"영화 '{movie_data['movie']['title']}'의 데이터가 삭제되었습니다.")
                    st.session_state.current_movie_id = None
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("영화 데이터 삭제 중 오류가 발생했습니다.")

# 데이터베이스 관리
elif selected_menu == "데이터베이스 관리":
    st.header("🗄️ 데이터베이스 관리")
    
    # 디버그 정보 추가
    st.write("Debug: 데이터베이스 관리 메뉴가 선택되었습니다.")
    st.write(f"DB 파일 존재: {os.path.exists('scripts.db')}")
    
    # 테스트 데이터 삽입 버튼
    if st.button("테스트 데이터 삽입"):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 영화 테스트 데이터
            cursor.execute("""
                INSERT INTO movies (title, filename, last_modified, genre, theme, summary)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                "테스트 영화",
                "test_movie.pdf",
                time.time(),
                "드라마",
                "인간 관계",
                "이것은 테스트 영화의 요약입니다. 실제 분석 데이터가 아닙니다."
            ))
            
            movie_id = cursor.lastrowid
            
            # 등장인물 테스트 데이터
            for i, name in enumerate(["주인공", "친구", "악당", "조연"]):
                cursor.execute("""
                    INSERT INTO characters (movie_id, name, count, description)
                    VALUES (?, ?, ?, ?)
                """, (
                    movie_id,
                    name,
                    100 - i * 20,
                    f"{name}에 대한 설명"
                ))
            
            # 씬 테스트 데이터
            for i in range(1, 6):
                cursor.execute("""
                    INSERT INTO scenes (movie_id, scene_number, heading, location, setting, time_of_day)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    movie_id,
                    str(i),
                    f"{i}. 테스트 장면",
                    "테스트 장소",
                    "INT" if i % 2 == 0 else "EXT",
                    "낮" if i % 3 == 0 else "밤"
                ))
            
            conn.commit()
            conn.close()
            
            st.success("테스트 데이터가 성공적으로 삽입되었습니다.")
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"테스트 데이터 삽입 중 오류 발생: {str(e)}")
    
    # 탭으로 구분된 기능
    tab1, tab2 = st.tabs(["영화 데이터 관리", "데이터베이스 백업/복원"])
    
    with tab1:
        st.subheader("영화 데이터 목록")
        
        # 영화 목록 가져오기
        movies = get_movie_list()
        
        if not movies:
            st.info("데이터베이스에 영화 데이터가 없습니다.")
        else:
            # 영화 목록 표시
            movie_df = pd.DataFrame([
                {
                    "ID": movie['movie_id'],
                    "제목": movie['title'],
                    "파일명": movie['filename'],
                    "수정일": movie['modified_date']
                }
                for movie in movies
            ])
            
            st.dataframe(movie_df, use_container_width=True)
            
            # 영화 삭제 기능
            st.subheader("영화 데이터 삭제")
            
            movie_options = {f"{movie['title']} ({movie['filename']})": movie['movie_id'] for movie in movies}
            selected_movie_label = st.selectbox("삭제할 영화 선택", list(movie_options.keys()))
            selected_movie_id = movie_options[selected_movie_label]
            
            if st.button("🗑️ 선택한 영화 데이터 삭제", type="primary"):
                if delete_movie(selected_movie_id):
                    st.success(f"영화 '{selected_movie_label}'의 데이터가 삭제되었습니다.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("영화 데이터 삭제 중 오류가 발생했습니다.")
    
    with tab2:
        st.subheader("데이터베이스 백업/복원")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 데이터베이스 백업")
            
            if st.button("📦 백업 파일 생성", use_container_width=True):
                # 현재 시간 기반 파일명
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"scripts_backup_{timestamp}.db"
                
                try:
                    # 데이터베이스 파일 복사
                    import shutil
                    shutil.copy2("scripts.db", backup_filename)
                    
                    # 다운로드 버튼 제공
                    with open(backup_filename, "rb") as f:
                        st.download_button(
                            label="📥 백업 파일 다운로드",
                            data=f.read(),
                            file_name=backup_filename,
                            mime="application/octet-stream",
                            key="download_backup",
                            use_container_width=True
                        )
                    
                    st.success(f"데이터베이스 백업이 생성되었습니다: {backup_filename}")
                except Exception as e:
                    st.error(f"백업 생성 중 오류 발생: {str(e)}")
        
        with col2:
            st.markdown("### 데이터베이스 복원")
            
            uploaded_db = st.file_uploader("백업 파일 업로드 (.db)", type=['db'])
            
            if uploaded_db is not None:
                if st.button("🔄 데이터베이스 복원", use_container_width=True):
                    try:
                        # 현재 DB 백업
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        current_backup = f"scripts_before_restore_{timestamp}.db"
                        
                        import shutil
                        if os.path.exists("scripts.db"):
                            shutil.copy2("scripts.db", current_backup)
                        
                        # 업로드된 파일로 교체
                        with open("scripts.db", "wb") as f:
                            f.write(uploaded_db.getvalue())
                        
                        st.success("데이터베이스가 성공적으로 복원되었습니다.")
                        st.info("변경사항을 확인하려면 페이지를 새로고침하세요.")
                    except Exception as e:
                        st.error(f"데이터베이스 복원 중 오류 발생: {str(e)}")
        
        # 데이터베이스 초기화
        st.markdown("---")
        st.markdown("### ⚠️ 데이터베이스 초기화")
        st.warning("이 작업은 모든 데이터를 삭제하고 데이터베이스를 새로 생성합니다.")
        
        confirm_text = st.text_input("초기화하려면 'INITIALIZE'를 입력하세요")
        
        if confirm_text == "INITIALIZE":
            if st.button("🗑️ 데이터베이스 초기화", type="primary", use_container_width=True):
                try:
                    # 기존 파일 백업
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    if os.path.exists("scripts.db"):
                        import shutil
                        shutil.copy2("scripts.db", f"scripts_backup_before_init_{timestamp}.db")
                        os.remove("scripts.db")
                    
                    # 새 데이터베이스 초기화
                    init_database()
                    
                    st.success("데이터베이스가 성공적으로 초기화되었습니다.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"데이터베이스 초기화 중 오류 발생: {str(e)}")

# 푸터
st.markdown("---")
st.markdown("© 2025 스크립트 분석기 | SQLite + OpenAI 기반")