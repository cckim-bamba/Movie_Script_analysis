import os
import re
import sqlite3
from datetime import datetime
from db_schema import get_db_connection, init_database
from character_extraction import process_character_data
from scene_extraction import process_scene_data

def extract_movie_title(file_name):
    """파일명에서 영화 제목 추출"""
    # 확장자 제거
    name_without_ext = os.path.splitext(file_name)[0]
    # 괄호, 특수문자 등 제거하고 제목으로 추정되는 부분만 추출
    clean_name = re.sub(r'[\(\)\[\]\{\}].*', '', name_without_ext)
    clean_name = re.sub(r'[_\-\.]', ' ', clean_name).strip()
    return clean_name

def get_movie_id(conn, file_path):
    """파일 경로로 영화 ID 조회, 없으면 새로 생성"""
    cursor = conn.cursor()
    file_name = os.path.basename(file_path)
    
    # 파일명으로 영화 레코드 조회
    cursor.execute("SELECT movie_id FROM movies WHERE filename = ?", (file_name,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    
    # 영화 레코드가 없으면 새로 생성
    title = extract_movie_title(file_name)
    last_modified = os.path.getmtime(file_path)
    
    cursor.execute("""
        INSERT INTO movies (title, filename, last_modified, file_path)
        VALUES (?, ?, ?, ?)
    """, (title, file_name, last_modified, file_path))
    
    conn.commit()
    return cursor.lastrowid

def is_file_modified(conn, file_path):
    """파일이 마지막 처리 이후 수정되었는지 확인"""
    cursor = conn.cursor()
    file_name = os.path.basename(file_path)
    last_modified = os.path.getmtime(file_path)
    
    cursor.execute("SELECT last_modified FROM movies WHERE filename = ?", (file_name,))
    result = cursor.fetchone()
    
    if not result:
        return True  # 파일이 DB에 없으면 수정됨으로 간주
    
    return last_modified > result[0]

def update_movie_modified_time(conn, movie_id, file_path):
    """영화 파일의 마지막 수정 시간 업데이트"""
    cursor = conn.cursor()
    last_modified = os.path.getmtime(file_path)
    
    cursor.execute("""
        UPDATE movies 
        SET last_modified = ? 
        WHERE movie_id = ?
    """, (last_modified, movie_id))
    
    conn.commit()

def upload_character_data(conn, movie_id, character_data):
    """등장인물 데이터 업로드/업데이트"""
    cursor = conn.cursor()
    
    for character in character_data:
        # 이미 존재하는 캐릭터인지 확인
        cursor.execute("""
            SELECT character_id, count FROM characters 
            WHERE movie_id = ? AND name = ?
        """, (movie_id, character['name']))
        
        existing = cursor.fetchone()
        
        if existing:
            # 존재하면 업데이트
            character_id, existing_count = existing
            # 카운트가 다르면 업데이트
            if existing_count != character['count']:
                cursor.execute("""
                    UPDATE characters 
                    SET count = ? 
                    WHERE character_id = ?
                """, (character['count'], character_id))
        else:
            # 없으면 새로 추가
            cursor.execute("""
                INSERT INTO characters (movie_id, name, count) 
                VALUES (?, ?, ?)
            """, (movie_id, character['name'], character['count']))
    
    conn.commit()

def upload_scene_data(conn, movie_id, scene_data):
    """장면 데이터 업로드/업데이트"""
    cursor = conn.cursor()
    
    for scene in scene_data:
        # 이미 존재하는 씬인지 확인
        cursor.execute("""
            SELECT scene_id FROM scenes 
            WHERE movie_id = ? AND scene_number = ?
        """, (movie_id, scene['scene_number']))
        
        existing = cursor.fetchone()
        
        if existing:
            # 존재하면 업데이트
            scene_id = existing[0]
            cursor.execute("""
                UPDATE scenes 
                SET heading = ?, location = ?, setting = ?, time_of_day = ? 
                WHERE scene_id = ?
            """, (scene['heading'], scene['location'], scene['setting'], 
                 scene['time_of_day'], scene_id))
        else:
            # 없으면 새로 추가
            cursor.execute("""
                INSERT INTO scenes (movie_id, scene_number, heading, location, setting, time_of_day) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (movie_id, scene['scene_number'], scene['heading'], 
                 scene['location'], scene['setting'], scene['time_of_day']))
    
    conn.commit()

def process_single_file(conn, pdf_path):
    """단일 PDF 파일 처리"""
    if not os.path.exists(pdf_path):
        print(f"❌ 파일이 존재하지 않습니다: {pdf_path}")
        return False
    
    # 파일이 수정되었는지 확인
    if not is_file_modified(conn, pdf_path):
        print(f"🔄 '{os.path.basename(pdf_path)}' 변경 없음. 업데이트 건너뜁니다.")
        return True
    
    # 영화 ID 가져오기
    movie_id = get_movie_id(conn, pdf_path)
    
    print(f"\n🎬 '{os.path.basename(pdf_path)}' 분석 시작!")
    
    # 등장인물 데이터 처리 및 업데이트
    character_data = process_character_data(pdf_path)
    if character_data:
        upload_character_data(conn, movie_id, character_data)
        print(f"✅ 등장인물 {len(character_data)}명 처리 완료")
    else:
        print("⚠️ 등장인물 데이터가 없습니다.")
    
    # 씬 데이터 처리 및 업데이트
    scene_data = process_scene_data(pdf_path)
    if scene_data:
        upload_scene_data(conn, movie_id, scene_data)
        print(f"✅ 장면 {len(scene_data)}개 처리 완료")
    else:
        print("⚠️ 장면 데이터가 없습니다.")
    
    # 영화 수정 시간 업데이트
    update_movie_modified_time(conn, movie_id, pdf_path)
    
    print(f"✅ '{os.path.basename(pdf_path)}' 데이터베이스 업데이트 완료!\n")
    return True

def process_directory(conn, directory="data"):
    """디렉토리 내 모든 PDF 파일 처리"""
    if not os.path.exists(directory):
        print(f"❌ '{directory}' 디렉토리가 존재하지 않습니다.")
        return False
    
    pdf_files = [f for f in os.listdir(directory) if f.lower().endswith(".pdf")]
    
    if not pdf_files:
        print(f"❌ '{directory}' 디렉토리에 PDF 파일이 없습니다.")
        return False
    
    print(f"🔍 총 {len(pdf_files)}개의 PDF 파일을 처리합니다.")
    
    success_count = 0
    for pdf_file in pdf_files:
        pdf_path = os.path.join(directory, pdf_file)
        if process_single_file(conn, pdf_path):
            success_count += 1
    
    print(f"\n📊 처리 결과: {success_count}/{len(pdf_files)} 파일 성공")
    return True

def delete_movie_data(conn, movie_id=None, filename=None):
    """영화 데이터 삭제 (영화 ID 또는 파일명으로)"""
    cursor = conn.cursor()
    
    if movie_id is None and filename is None:
        print("❌ 삭제할 영화의 ID나 파일명을 지정해야 합니다.")
        return False
    
    # 파일명으로 영화 ID 조회
    if movie_id is None and filename is not None:
        cursor.execute("SELECT movie_id FROM movies WHERE filename = ?", (filename,))
        result = cursor.fetchone()
        if not result:
            print(f"❌ '{filename}' 파일에 대한 영화 데이터가 없습니다.")
            return False
        movie_id = result[0]
    
    # 연결된 데이터 삭제
    tables = ["sentiment_analysis", "plot_analysis", "relationships", "characters", "scenes"]
    for table in tables:
        cursor.execute(f"DELETE FROM {table} WHERE movie_id = ?", (movie_id,))
    
    # 영화 데이터 삭제
    cursor.execute("DELETE FROM movies WHERE movie_id = ?", (movie_id,))
    
    rows_deleted = cursor.rowcount
    conn.commit()
    
    if rows_deleted > 0:
        print(f"✅ 영화 ID {movie_id}의 모든 데이터가 삭제되었습니다.")
        return True
    else:
        print(f"⚠️ 영화 ID {movie_id}의 데이터가 없습니다.")
        return False

def list_movies(conn):
    """데이터베이스의 모든 영화 목록 조회"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT movie_id, title, filename, datetime(last_modified, 'unixepoch', 'localtime') as modified_date
        FROM movies
        ORDER BY last_modified DESC
    """)
    
    movies = cursor.fetchall()
    
    if not movies:
        print("⚠️ 데이터베이스에 영화 데이터가 없습니다.")
        return []
    
    print("\n📋 데이터베이스 영화 목록:")
    for i, movie in enumerate(movies, 1):
        movie_id, title, filename, modified_date = movie
        print(f"{i}. [{movie_id}] {title} ({filename}) - 수정일: {modified_date}")
    
    return movies

if __name__ == "__main__":
    # 데이터베이스 연결
    conn = get_db_connection()
    
    import sys
    if len(sys.argv) > 1:
        # 명령행 인수에 따라 다른 동작 수행
        if sys.argv[1] == "--list":
            # 영화 목록 출력
            list_movies(conn)
        elif sys.argv[1] == "--delete" and len(sys.argv) > 2:
            # 영화 데이터 삭제
            try:
                movie_id = int(sys.argv[2])
                delete_movie_data(conn, movie_id=movie_id)
            except ValueError:
                # 숫자가 아니면 파일명으로 간주
                delete_movie_data(conn, filename=sys.argv[2])
        elif sys.argv[1] == "--all":
            # 모든 PDF 파일 처리
            process_directory(conn)
        else:
            # 단일 파일 처리
            process_single_file(conn, sys.argv[1])
    else:
        # 인수가 없으면 디렉토리 처리
        process_directory(conn)
    
    conn.close()