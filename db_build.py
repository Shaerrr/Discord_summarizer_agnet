import sqlite3
from langchain_community.vectorstores import Chroma
from langchain.schema import Document
from langchain.embeddings import SentenceTransformerEmbeddings

# Embedding 설정
embedding = SentenceTransformerEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
persist_db = None  # Chroma DB는 나중에 초기화할 예정
# SQLite 데이터베이스 생성 및 테이블 초기화
def initialize_sqlite_db():
    conn = sqlite3.connect("CHAT_DB.db")
    cursor = conn.cursor()

    # CHAT 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS CHAT (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT DEFAULT (DATETIME('now', 'localtime')),
        )
    ''')

    # BOT_CONFIG 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS BOT_CONFIG (
            guild_id INTEGER PRIMARY KEY AUTOINCREMENT,
            All_channel_ids TEXT NOT NULL,
            receive_channel TEXT,
            filtered_channels TEXT
        )
    ''')

    # MINUTES 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS MINUTES (
            minute_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            content TEXT,
            date TEXT
        )
    ''')

    conn.commit()
    cursor.close()
    conn.close()
    print("SQLite 데이터베이스 및 테이블이 생성되었습니다.")


# Chroma 벡터 데이터베이스 생성 및 초기화
def initialize_chroma_db():
    # Chroma DB 생성
    persist_db = Chroma(
        embedding_function=embedding,
        persist_directory="chroma_db",
        collection_name="chat_collection"
    )
    print("Chroma 벡터 데이터베이스가 생성되었습니다.")


# 실행
if __name__ == "__main__":
    initialize_sqlite_db()
    initialize_chroma_db()