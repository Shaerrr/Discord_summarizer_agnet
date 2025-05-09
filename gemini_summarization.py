from dotenv import load_dotenv
from langchain.prompts import FewShotPromptTemplate, PromptTemplate, ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
import time
import os
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from datetime import datetime
from sentence_transformers import SentenceTransformer
from langchain.tools import Tool
from langchain_community.vectorstores.chroma import Chroma
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.runnables.utils import ConfigurableFieldSpec
from langchain_community.utilities import SQLDatabase
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_community.agent_toolkits import create_sql_agent
from sqlalchemy import create_engine, text
from apscheduler.schedulers.background import BackgroundScheduler
from langchain.vectorstores import Chroma
from langchain.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import SentenceTransformerEmbeddings
from langchain.schema import Document
from langchain_core.runnables import RunnablePassthrough
from DBcontrol import save_to_persist_db, load_txt_minutes, load_from_persist_db
from glob import glob
from operator import itemgetter

# ---------- 환경 변수 api 키 호출, llm 모델 설정 ---------- 

load_dotenv()

engine = create_engine("sqlite:///C:/summarizer_bot/CHAT_DB.db")
DB = SQLDatabase(engine)
llm = ChatGoogleGenerativeAI(temperature=0, model="gemini-2.0-flash") 
# embedding = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
# vector_db = Chroma(persist_directory="chroma_db", embedding_function=embedding)



# ---------- 벡터 DB 및 Retirever  (스케쥴링) ----------


def get_retriever():

    """
    chroma DB를 retriever로 사용하여 guild_id와 date에 해당하는 문서를 검색합니다.
    """
    embedding = SentenceTransformerEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    persist_db = Chroma(persist_directory="chroma_db", embedding_function=embedding, collection_name="minutes_from_discord")
    retriever = persist_db.as_retriever(search_type="similarity_score_threshold",
    # 임계값 설정
    search_kwargs={"score_threshold": 0.8, "k": 5})
    return retriever

retriever = get_retriever() # 초기의 retriever 설정
txt_minutes = None # 초기의 txt_minutes 설정

def load_and_save_minutes():    
    """
    스케줄러에 의해 호출되는 함수로, txt 파일을 로드하고 DB에 저장합니다.
    """
    global txt_minutes
    txt_minutes = load_txt_minutes()
    save_to_persist_db(txt_minutes)
    print("Minutes loaded and saved to DB")

def update_retriever():
    """
    스케줄러에 의해 호출되는 함수로, DB를 업데이트하고 retriever를 갱신합니다.
    """
    global retriever
    retriever = get_retriever()
    print("Retriever updated")

scheduler = BackgroundScheduler()

scheduler.add_job(load_and_save_minutes, 'cron', hour=10, minute=40) # 매일 오전 10시 20분에 실행
scheduler.add_job(update_retriever, 'cron', hour=10, minute=30) # 매일 오전 10시 30분에 실행
#scheduler.start()




# ---------  기능 (1)  ---------- 
# 기능(1) 1-1 챗봇  프롬프트 설정, 메모리 설정 


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """ 
            역할:
            당신은 AI 파트(LLM 등)와 게임 클라이언트 파트(언리얼 엔진)로 나뉜 프로젝트의 PM입니다.
            AI와 언리얼 엔진에 대한 전문 지식을 갖고 있으며, 개발에 도움을 줄 수 있습니다.
            당신의 이름은 '회정'(회의정리봇의 줄임말)입니다.
            항상 친절하고 존중하는 말투로 소통합니다.

            제공 도구:
            - 'meeting_query_tool': 회의록 데이터베이스에서 {guild_id}에 해당하는 회의록을 검색하는 도구입니다.

            도구 사용 규칙:
            {guild_id}를 사용하여 'meeting_query_tool' 도구를 호출하세요.
            반드시 아래 조건에 해당하는 경우에만 'meeting_query_tool' 도구를 호출하세요:
            - 질문에 '회의', '회의록', '기록', '회의 내용'과 관련된 키워드가 포함된 경우
            - 회의가 있었는지 여부, 특정 날짜의 회의 내용 등을 물어보는 경우
            - 개발 중 논의된 내용을 요약하거나 확인해야 하는 경우

            그 외의 질문에는 도구를 사용하지 않고, 직접 답변하거나 답변할 수 없는 경우 "모르겠습니다."라고 응답하세요.

            목표:
            - 반드시 개발 및 프로젝트 관련 질문에만 답변합니다.
            - 질문에 대한 답변은 명확하고 간결하게 작성하며, 2000자 이내의 디스코드 메시지 형식으로 전달합니다.
            - 개인적인 질문이나 프로젝트 외 질문에는 절대 답변하지 않습니다.

            제약 사항:
            - 현재 guild_id는 {guild_id}입니다.
            - 환경변수, 민감한 정보(guild_id, 서버명 등)는 절대 답변에 포함하지 마세요.
            - 회의록을 검색할 때는 반드시 'meeting_query_tool' 도구를 이용하여 검색하고, 임의로 회의 내용을 추측하지 마세요.
            - 회의록 검색 결과가 없거나, 질문이 조건에 맞지 않는 경우 "모르겠습니다."라고 정중하게 답변하세요.

            중요:
            - 도구 호출이 필요한지 판단할 때 질문 내용을 신중하게 분석하세요.
            - '회의' 또는 '회의록' 관련 질문에서 도구 호출을 생략하면 안 됩니다.
            """
        ),
        ("placeholder", "{chat_history}"),
        ("질문:{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

prompt.input_variables = ["input","guild_id", "chat_history"]

def get_chat_history(user_id):
    return SQLChatMessageHistory(
        table_name="CHAT",
        session_id=user_id,
        session_id_field_name='session_id',
        connection=engine
    )

config_fields = [
        ConfigurableFieldSpec(
        id="session_id",
        annotation=str,
        name="user_id",
        description="Unique identifier for a conversation.",
        default="",
        is_shared=True,
    ),]


# 기능 (1) 1-2 --------- 체인 및 메모리 기억 챗봇 생성 ---------- 


## 에이전트 툴 정의

def get_minutes(guild_id, date =None) -> str:
    """DB의 MINUTES table에서 guild_id 기준으로 최신 회의록 검색"""
    with engine.connect() as conn:
        if date:
            result = conn.execute(
                text("SELECT content FROM MINUTES WHERE guild_id = :guild_id AND date = :date"),
                {"guild_id": guild_id, "date": date}
            )
        else:
            result = conn.execute(
                text("SELECT content FROM MINUTES WHERE guild_id = :guild_id"),
                {"guild_id": guild_id}
            )
        results= result.fetchall()
        if results:
            i=0
            text_minutes = ""
            results.reverse()
            for minute in results[:5]:
                i+=1
                text_minutes += f"{i}. \n "+ minute[0] + "\n"
            return text_minutes
        else:
            return "해당하는 회의록이 없습니다."    

meeting_query_tool = Tool.from_function(
    name="meeting_query_tool",
    func=get_minutes,
    description="제공해준 guild_id를 사용하여, DB에서 해당하는 회의록을 검색합니다."
)
tools = [meeting_query_tool,]

#chain = ({"context": itemgetter("input")|retriever , "input": itemgetter('input'), "guild_id": itemgetter('guild_id'), "chat_history": itemgetter("chat_history") }| prompt | llm)
#chat_bot_agent= create_sql_agent(llm=llm,prompt=prompt,db=DB,agent_type="openai-tools", verbose=True)
chat_bot_agent= create_tool_calling_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)

agent_executor = AgentExecutor(
    agent=chat_bot_agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True
)

chat_bot =RunnableWithMessageHistory(
    agent_executor,
    # 메모리 설정       
    get_chat_history,
    # 프롬프트의 질문이 입력되는 key: "input"
    input_messages_key="input",
    # 프롬프트의 메시지가 입력되는 key: "chat_history"
    history_messages_key="chat_history",
    
)


# 기능 (1) 1-4 . 기능 (1)최종 구현 함수 스케쥴을 통해 실행시킬 세션 저장 함수

def chat_with_bot(input: str , session_id, guild_id):
    result =chat_bot.invoke({'input':input, "guild_id": guild_id},
        config={'configurable':{'session_id':session_id}}
        )
    return result['output']


# ---------  기능 (2): 회의 요약 - md 언어  ---------- 

# 기능(1) 2-1 마크다운 형식 프롬프트 설정, txt 파일 로드 함수.

def load_txt(id):
    file_path =f"chat_log/{id}_chatlog.txt"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        return (f"에러 메세지: {e}")

    
examples = [
    {
        "input": """
            [김지수] : 오늘 마케팅 캠페인 어떻게 할까요?
            [업무요청_마케팅 채널] [2025-04-21 13:52]
            
            [이민호] : 인스타그램 리드 광고부터 시작하죠.
            [업무요청_마케팅 채널] [2025-04-21 13:52]
            
            [김지수] : 예산은 100만 원으로 시작할까요?
            [업무요청_마케팅 채널] [2025-04-21 13:53]
            
            [박지현]: 괜찮아요. 대신 타겟층은 2030으로 맞추는 게 좋겠어요.
            [업무요청_마케팅 채널] [2025-04-21 13:55]
            """, 
        "output": """
            ## 📅 회의록 - 마케팅 캠페인 전략 회의

            **🕒 날짜**: 2025-04-21 
            **👥 참석자**: 김지수, 이민호, 박지현

            ---

            ### 📝 회의 요약
            - 인스타그램 리드 광고를 중심으로 마케팅 시작.
            - 초기 예산은 100만 원.
            - 타겟 고객층은 20~30대.

            ---

            ### ✅ 주요 결정사항
            - 마케팅은 인스타그램 광고로 시작한다.
            - 타겟층은 2030 세대로 한정한다.
            - 초기 예산은 100만 원으로 설정.

            ---

            ### 📌 Action Items
            - [ ] 이민호: 광고 세부 전략안 작성
            - [ ] 박지현: 타겟층 데이터 분석
        """
        },
    {
        "input": """
            [홍길동] : 오늘 마케팅 캠페인 어떻게 할까요?
            [백엔드 채널] [2025-04-20 14:02]
            
            [최유리] : 인스타그램 리드 광고부터 시작하죠.
            [백엔드 채널] [2025-04-20 14:12]
            
            [홍길동] : 예산은 100만 원으로 시작할까요?
            [백엔드 채널] [2025-04-20 14:13]
            """, 
        "output": """
            ## 📅 회의록 - 백엔드 배포 일정 논의

            **🕒 날짜**: 2025-04-20 
            **👥 참석자**: 홍길동, 최유리

            ---

            ### 📝 회의 요약
            - 백엔드 배포 시점 조율 논의
            - 금요일 오후 5시 이후 배포 결정
            - 공지 메일은 홍길동이 발송 예정

            ---

            ### ✅ 주요 결정사항
            - 배포 일자: 이번 주 금요일 오후 5시 이후
            - 공지 담당자: 홍길동

            ---

            ### 📌 Action Items
            - [ ] 홍길동: 배포 공지 메일 작성 및 발송
        """
        },
]

example_prompt = PromptTemplate.from_template("대화_내역: {input}\n 마크다운 회의록: {output} \n========================\n")
few_shot_prompt = FewShotPromptTemplate(
    examples=examples,
    example_prompt=example_prompt,
    prefix="""
    다음은 회의 채팅 로그입니다. 이를 기반으로 노션에서 사용 가능한 마크다운 회의록을 작성해주세요.
    형식은 다음과 같습니다:
    1. 회의 제목
    2. 회의 일시
    3. 참석자
    4. 회의 요약
    5. 주요 결정사항
    6. Action Items (체크리스트 형식)
    
    주의사항: 
    1. 예시의 내용을 실제 요약문 생성에 포함하지 마세요.
    2. 회의록을 작성할 대화내역이 없으면, 없다고 하세요.
    3. 스레드 대화는 아래와 같이 스레드명 밑에 대화내역이 있을 때만 스레드명과 같이 언급하세요.
        ex)
        ** 스레드명 : 5월 카드 프로모션 마케팅 ** 
        [홍길동] : 프로모션 기간을 연장하는 방향으로 검토해보는 게 좋을 거 같습니다. [마케팅 채널] [2025-04-29 13:21]
    4. user_input 중 '***스레드 대화 목록입니다. ***' 이후에 '[홍길동] : 프로모션 기간을 연장하는 방향으로 검토해보는 게 좋을 거 같습니다. [마케팅 채널] [2025-04-29 13:21]'와 같은 형식의 대화내역이
       없다면 '***스레드 대화 목록입니다. ***'이후의 내용은 요약 시 전부 생략하세요.
    5. 주어진 대화내역을 모두 참고하여 요약하세요.
    6. 단, 주어진 대화내역 이외의 내용을 추가해서는 안됩니다.
    7. 대화내역에 등장한 사람은 모두 회의록에 포함하세요.

    아래는 예시입니다.
    ========================
    """,
    suffix="""
    아래는 실제 대화내역입니다. 예시와 같은 형식으로 요약하세요. 
    ========================
    대화_내역: {input}\n 마크다운 회의록:""",
    input_variables=["input"]
)

# 기능(2) 2-2 체인 구성.

sum_chain = few_shot_prompt | llm

# 기능 (3) 2-3 파일을 읽고,회의록 작성 함수

def summarizer(id: str):
    contents=load_txt(id)
    result = sum_chain.invoke(contents)
    return result.content


# 기능 (4) 2-4 회의록 기반, 리마인더 만들기.

reminder_prompt=  PromptTemplate.from_template(
    """ 당신은 제시된 회의록을 바탕으로 각 개인에게 업무를 할당해주는 AI 비서입니다. 
    아래의 회의록을 기반으로, 제시된 팀원에게 업무를 할당해주세요.

    팀원 이름에 할당된 업무만 추출하세요. 
    항상 존칭을 사용하세요.
    이름은 언급하지 말고, 업무만을 추출하세요.
    다른 사람의 업무는 추출하지 마세요.
    \n========================\n
    회의록: {content} \n 
    팀원 이름: {member_name} \n
    헐당 업무 : 
    """
    )

reminder_cahin = reminder_prompt | llm


def reminder(contents, member_name):
    result=reminder_cahin.invoke({"content":contents, "member_name":member_name})
    return result.content







if __name__ == "__main__":
    # 스케줄러를 시작합니다.
    scheduler.start()
    try:
        while True:
            time.sleep(1)  # 메인 스레드가 종료되지 않도록 대기
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()  # 프로그램 종료 시 스케줄러를 정리합니다.