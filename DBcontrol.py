import sqlite3
import json
import os
from datetime import datetime
import sqlite3
import json
import os
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import TextLoader
from langchain.embeddings import SentenceTransformerEmbeddings
from langchain.schema import Document
from langchain.document_loaders import TextLoader
from glob import glob


#-------------------------- DB 연결 설정 -----------------------------------------
# conn = sqlite3.connect('CHAT_DB.db',)
# c = conn.cursor()

#-------------------------- 유틸리티 함수 -----------------------------------------

def fetch_bot_config(guild_id):
    """
    BOT_CONFIG 테이블에서 특정 guild_id에 해당하는 데이터를 가져옵니다.
    """
    with sqlite3.connect('CHAT_DB.db') as conn:
        c = conn.cursor()
        query = c.execute('''
            SELECT *
            FROM BOT_CONFIG
            WHERE guild_id = ?
        ''', (guild_id,))
        result = query.fetchone()
    if result:
        # JSON 문자열을 Python 리스트로 변환
        all_channel_ids = json.loads(result[1]) if result[1] else []
        return {
            "guild_id": result[0],
            "all_channel_ids": all_channel_ids,
            "receive_channel": result[2],
            "filtered_channels": json.loads(result[3]) if result[3] else []
            }
    return None

def save_guild_all_channel_ids(guild_id, all_channel_ids):
    """
    BOT_CONFIG 테이블에서 특정 guild_id의 All_channel_ids를 저장하거나 업데이트합니다.
    """
    with sqlite3.connect('CHAT_DB.db') as conn:
        c = conn.cursor()
        try:
            all_channel_ids_json = json.dumps(all_channel_ids)
            c.execute('''
                INSERT INTO BOT_CONFIG (guild_id, All_channel_ids)
                VALUES (?, ?)
            ''', (guild_id, all_channel_ids_json))
        except sqlite3.IntegrityError:
            c.execute('''
                UPDATE BOT_CONFIG
                SET All_channel_ids = ?
                WHERE guild_id = ?
            ''', (all_channel_ids_json, guild_id))
        conn.commit()

def save_guild_receive_channel(guild_id, receive_channel):
    """
    BOT_CONFIG 테이블에서 특정 guild_id의 receive_channel을 저장하거나 업데이트합니다.
    """
    with sqlite3.connect('CHAT_DB.db') as conn:
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO BOT_CONFIG (guild_id, receive_channel)
                VALUES (?, ?)
            ''', (guild_id, receive_channel))
        except sqlite3.IntegrityError:
            c.execute('''
                UPDATE BOT_CONFIG
                SET receive_channel = ?
                WHERE guild_id = ?
            ''', (receive_channel, guild_id))
        conn.commit()

def save_guild_filtered_channels(guild_id, filtered_channels):
    """
    BOT_CONFIG 테이블에서 특정 guild_id의 filtered_channels를 저장하거나 업데이트합니다.
    """
    with sqlite3.connect('CHAT_DB.db') as conn:
        c = conn.cursor()
        try:
            filtered_channels_json = json.dumps(filtered_channels)
            c.execute('''
                INSERT INTO BOT_CONFIG (guild_id, filtered_channels)
                VALUES (?, ?)
            ''', (guild_id, filtered_channels_json))
        except sqlite3.IntegrityError:
            c.execute('''
                UPDATE BOT_CONFIG
                SET filtered_channels = ?
                WHERE guild_id = ?
            ''', (filtered_channels_json, guild_id))
        conn.commit()

def save_minutes(guild_id, content):
    """
    MINUTES 테이블에 특정 guild_id의 회의록을을 저장하거나 업데이트합니다.
    """
    now_time=datetime.now().strftime('%Y-%m-%d')
    with sqlite3.connect('CHAT_DB.db') as conn:
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO MINUTES (guild_id, content, date)
                VALUES (?, ?, ?)
            ''', (guild_id, content, now_time))
            conn.commit()
            return "회의록이 성공적으로 저장됐습니다."
        except sqlite3.IntegrityError:
            return "이미 존재하는 회의록입니다."
        

def fetch_minutes(guild_id, date):
    """
    MINUTES 테이블에 특정 guild_id의 지정된 날짜의 회의록을 가져옵니다.
    """
    with sqlite3.connect('CHAT_DB.db') as conn:
        c = conn.cursor()
        query = c.execute('''
            SELECT content
            FROM MINUTES
            WHERE guild_id = ? and date = ?
            ''', (int(guild_id), date))
        result = query.fetchall()
    return result[-1][0]



#-------------------------- 벡터 DB 설정 및 호출 -----------------------------------------

embedding = SentenceTransformerEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
persist_db = Chroma(persist_directory="chroma_db", embedding_function=embedding, collection_name="minutes_from_discord")



#-------------------------- 크로마 유틸리티 함수 -----------------------------------------

# glob.glob를 통해 디렉토리 내의 모든 파일을 가져옵니다. 그후, 그 list를 아래 함수의 인자로 넣어줍니다.
def load_txt_minutes():
    """
    주어진 파일 리스트에서 모든 회의록을 로드하고 벡터 DB에 추가합니다.
    파일 이름에서 메타데이터를 추출합니다. (예: guild_id, date)
    """
    file_list = glob("minutes/*.txt")
    documents = []
    for file_name in file_list:
        guild_id, date = file_name.split("_")
        loader = TextLoader(file_name, encoding="utf-8")
        file_documents = loader.load_and_split(text_splitter=RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50))
        
        # 각 문서에 개별적으로 메타데이터 추가
        for doc in file_documents:
            doc.metadata["guild_id"] = guild_id
            doc.metadata["date"] = date
        
        # 처리된 문서를 전체 리스트에 추가
        documents.extend(file_documents)
    
    return documents

def save_to_persist_db(documents: list[Document]) -> None:
    """
    주어진 문서 리스트를 벡터 DB에 추가합니다.
    """
    persist_db.add_documents(documents)
    persist_db.persist()

def load_from_persist_db(guild_id: str) -> list[Document]:
    """
    주어진 guild_id에 해당하는 문서를 벡터 DB에서 로드합니다.
    """
    return persist_db.similarity_search_by_vector(guild_id, k=5)    

def load_from_persist_db_by_date(guild_id: str, date: str) -> list[Document]:  
    """
    주어진 guild_id와 date에 해당하는 문서를 벡터 DB에서 로드합니다.
    """
    return persist_db.similarity_search_by_vector(guild_id, k=5, filter={"date": date})

def load_from_persist_db_by_date_all(guild_id: str) -> list[Document]:
    """
    주어진 guild_id에 해당하는 모든 문서를 벡터 DB에서 로드합니다.
    """
    return persist_db.similarity_search_by_vector(guild_id, k=5, filter={"guild_id": guild_id}) 


