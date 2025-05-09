#  Discord AI 회의록 정리봇

AI와 LangChain, ChromaDB 기반으로 **Discord 서버 내 회의록을 관리하고 검색**할 수 있는 스마트 회의비서 봇입니다. 

회의록을 매일 자동으로 크롤링하고, **DB에 임베딩**하여 자연어로 회의 내용을 검색할 수 있어요.

---
## 💬 Discord 챗봇 링크

![image](https://github.com/user-attachments/assets/d8d1350b-0d5d-4ba7-8e7f-b3d9d8f04353)



[회의정리 봇 링크](https://discord.com/oauth2/authorize?client_id=1359414076299804673&permissions=8&integration_type=0&scope=bot).


해당 링크를 통해 봇을 서버에 참가시킬 수 있습니다.
관리자 권한을 부여해주세요! (권한 미부여 시, 오류 발생 가능성 있음.)

---

## 📌 주요 기능

- :dependabot: 회의록을 기억하는 챗봇을 통해, 개발에 대한 리마인드 및 도움을 받을 수 있음.
- 📝 텍스트 파일(.txt) 형태의 회의록을 자동으로 저장 및 로드. DB에 회의록을 저장.
- 🗂️ guild_id와 날짜를 메타데이터로 저장하여 서버별, 날짜별 회의 내용 관리
- 📦 LangChain Agent를 통해 자연어 기반 회의록 검색
- 📅 APScheduler로 **매일 특정 시간에 회의록 로드 → DB 업데이트 → Retriever 최신화**
- 💬 Google Gemini API를 활용해 회의록 기반 AI 질의응답 지원 (gemini-2.0-flash)
- ⚙️ SQLTool과 함께 SQL DB에 저장된 회의록도 쿼리 가능

---

## 📐 프로젝트 구조

```
Discord_chatbot_agent/ 
├── main.py # 핵심 챗봇 + Retriever + DB 관리 + 스케줄러
├── gemini_summarization.py # Discord 봇 핸들러 (챗봇 호출만 담당)
├── chroma_db/ # ChromaDB 데이터 저장 (db_build.py 실행후 생성)
├── minutes/ # 회의록 txt 파일 폴더 (파일명: {guild_id}_{날짜}.txt)
├── db_build.py # SQLite3로 챗봇 설정 관련 DB 생성 (회의록 및 채팅 히스토리 저장)
├── CHAT_DB.db # SQL DB (db_build.py 실행후 생성)
├── requirements.txt
└── README.md
```


---

## ⚙️ 설치 및 실행 방법 

아래 내용은 위 링크에 만들어진 봇이 아닌,
해당 코드를 기반으로 로컬에서 봇을 생성하는 가이드입니다.

따라서, 로컬환경에서의 봇 구축이 아닌
단순히 봇을 이용하기를 원하시면 상단의 링크를 통해 봇을 초대하시길 바랍니다.


0. 들어가기 앞서

Python 3.11.11 버전
requirements.txt는 window 운영환경에 맞춰져 있음

1. 패키지 설치  
```
pip install -r requirements.txt
```

환경변수 세팅 (Google Gemini API Key, Discord Token 등) 

2. db_build.py 실행
```
python db_build.py
```
3. Discord 봇 실행

```
python main.py
python gemini_summarization.py
```

🛠️ 사용 기술 / 라이브러리
---
Python 3.11.11

LangChain

Chroma

sentence-transformers

APScheduler

Google Gemini API

Discord API

💬 Discord 명령어 예시
![image](https://github.com/user-attachments/assets/ddcdabe8-61ca-4cdf-802e-759aa16481dc)
![image](https://github.com/user-attachments/assets/d58ce7b9-db82-419a-bcc8-a99d1b93d96e)


🖥️ 실행 화면
---

📌 챗봇
![image](https://github.com/user-attachments/assets/ebee1bc6-9fd7-4b22-8ff3-b32e93ba2db8)


📌 회의록 및 리마인드 출력
![image](https://github.com/user-attachments/assets/146bbabd-a126-47f9-ae8a-08639272af49)



📅 스케줄링 동작 시간
---
작업 실행 시간 (매일)

회의록 매일 디스코드에 송출 10:10

회의록 기반 리마인더 멘션 10:20

ChromaDB로 임베딩 저장	10:20

Retriever 최신화	10:30


🧰 추후 개발 방향
---
1. 음성 회의시 녹음 및 회의록 정리 기능  -> 현재 음성 서버에 참가시키고 퇴장시키는 기능만 구현해놓은 상태
2. RAG 정교화 -> 좀 더 세부적이고 상세한 회의록이 조회가능하도록 RAG 시스템을 수정함으로써 사용자 경험을 개선할 예정
3. 다양한 플랫폼에 이식 예정 (현재 디스코드로 구현되어있으나, 협업에 많이사용하는 슬랙이나 카카오톡 봇으로도 이용이 가능하도록 확장 예정)



📃 라이센스
---
본 프로젝트는 아래 라이브러리를 사용하며, 각 라이브러리의 라이센스를 따릅니다.

sentence-transformers: Apache 2.0

Chroma: MIT

LangChain: MIT

기타 사용 라이브러리 및 API: 각 서비스 이용약관 및 라이센스 준수

📬 문의
---
개발자: Shaerrr

📧 : kimjinsyll@gmail.com

이슈나 문의는 이메일로 보내주세요. 언제든 환영합니다. 🙌 
