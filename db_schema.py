import sqlite3
import os

def init_database(db_path="scripts.db"):
    """데이터베이스 초기화 및 테이블 생성"""
    # 디렉토리가 없으면 생성
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    # 데이터베이스 연결
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 영화 테이블 생성
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS movies (
        movie_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        filename TEXT NOT NULL UNIQUE,
        last_modified REAL,
        file_path TEXT,
        genre TEXT,
        theme TEXT,
        summary TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 등장인물 테이블 생성
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS characters (
        character_id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        count INTEGER DEFAULT 0,
        description TEXT,
        FOREIGN KEY (movie_id) REFERENCES movies (movie_id),
        UNIQUE (movie_id, name)
    )
    ''')
    
    # 씬 테이블 생성
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scenes (
        scene_id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        scene_number TEXT NOT NULL,
        heading TEXT,
        location TEXT,
        setting TEXT,
        time_of_day TEXT,
        FOREIGN KEY (movie_id) REFERENCES movies (movie_id),
        UNIQUE (movie_id, scene_number)
    )
    ''')
    
    # 관계 테이블 생성
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS relationships (
        relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        character1_id INTEGER NOT NULL,
        character2_id INTEGER NOT NULL,
        relationship_type TEXT,
        description TEXT,
        FOREIGN KEY (movie_id) REFERENCES movies (movie_id),
        FOREIGN KEY (character1_id) REFERENCES characters (character_id),
        FOREIGN KEY (character2_id) REFERENCES characters (character_id),
        UNIQUE (movie_id, character1_id, character2_id)
    )
    ''')
    
    # 감정 분석 테이블 생성
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sentiment_analysis (
        sentiment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        scene_id INTEGER,
        character_id INTEGER,
        sentiment_score REAL,
        sentiment_label TEXT,
        sentiment_text TEXT,
        FOREIGN KEY (movie_id) REFERENCES movies (movie_id),
        FOREIGN KEY (scene_id) REFERENCES scenes (scene_id),
        FOREIGN KEY (character_id) REFERENCES characters (character_id)
    )
    ''')
    
    # 줄거리 분석 테이블 생성
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS plot_analysis (
        plot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        plot_element TEXT,
        plot_description TEXT,
        plot_order INTEGER,
        FOREIGN KEY (movie_id) REFERENCES movies (movie_id)
    )
    ''')
    
    # 설정 테이블 생성 (시스템 설정 저장용)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
        setting_key TEXT UNIQUE,
        setting_value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()
    
    print("✅ 데이터베이스 초기화 완료")

def check_db_exists(db_path="scripts.db"):
    """데이터베이스 파일이 존재하는지 확인"""
    return os.path.exists(db_path)

def get_db_connection(db_path="scripts.db"):
    """데이터베이스 연결을 반환"""
    if not check_db_exists(db_path):
        init_database(db_path)
    return sqlite3.connect(db_path)

if __name__ == "__main__":
    # 데이터베이스 초기화
    init_database()