# 베이스 이미지 설정
FROM python:3.11-slim

# 시스템 패키지 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app   

# 현재 디렉토리의 모든 파일을 컨테이너의 /app 디렉토리로 복사
COPY . /app

# requirements.txt 파일을 사용하여 필요한 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 컨테이너 실행 명령어
CMD ["python", "main.py"] 
# CMD ["python", "gemini_summarization.py"] 현재 에러로 인해 주석처리