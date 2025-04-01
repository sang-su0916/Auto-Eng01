# AI 영어 첨삭 앱

이 앱은 OpenAI API를 활용한 영어 작문 첨삭 서비스입니다. 주어진 문제에 대한 답변을 작성하면 AI가 문법, 어휘, 표현 등을 첨삭해줍니다.

## 기능

- 미리 준비된 예제 문제 선택 또는 직접 문제 입력
- AI로 새로운 문제 생성 기능
- 난이도 선택 (초급, 중급, 상급) 및 세부 난이도 선택 (초, 중, 상)
- 영어 작문 답변 입력
- AI를 통한 문법, 어휘, 표현 첨삭
- 첨삭 결과 저장 기능

## 설치 방법

1. 프로젝트 클론 또는 다운로드
   ```
   git clone https://github.com/sang-su0916/Auto-Eng01.git
   cd Auto-Eng01
   ```
2. 필요한 패키지 설치
   ```
   pip install -r requirements.txt
   ```
   
   > **참고**: 이 앱은 OpenAI Python 패키지 v1.12.0 이상을 사용합니다. 이 버전에서는 `openai.OpenAI()` 대신 `openai.Client()`를 사용합니다.

3. API 키 설정
   - `.env.example` 파일을 복사하여 `.env` 파일 생성
   - `.env` 파일에 API 키 입력:
     ```
     OPENAI_API_KEY=your_api_key_here
     GEMINI_API_KEY=your_api_key_here
     ```

## 실행 방법

앱을 실행하려면 다음 명령어를 사용하세요:

```
streamlit run app.py
```

## 사용 방법

1. 왼쪽 선택 메뉴에서 "예제 문제 선택", "직접 문제 입력" 또는 "AI가 생성한 문제" 선택
2. 문제를 선택하거나 직접 입력하거나 AI에게 생성 요청
3. AI 생성 문제의 경우 난이도 선택 (초급, 중급,, 상급 및 세부 난이도 초, 중, 상)
4. 답변을 영어로 작성
5. "첨삭 요청하기" 버튼 클릭
6. AI 첨삭 결과 확인
7. 필요시 "결과 저장하기" 버튼으로 결과 저장

## 배포 방법

### Streamlit Cloud 배포

이 앱은 Streamlit Cloud에 배포할 수 있습니다:

1. GitHub에 저장소 푸시
2. [Streamlit Cloud](https://streamlit.io/cloud)에 로그인
3. "New app" 버튼 클릭
4. 저장소, 브랜치, 메인 파일(app.py) 선택
5. 고급 설정에서 필요한 API 키를 환경 변수로 추가:
   - `OPENAI_API_KEY`
   - `GEMINI_API_KEY` (선택사항)
6. 배포 버튼 클릭

### Heroku 배포

Heroku에 배포하기:

1. [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) 설치
2. 다음 명령어 실행:
   ```
   heroku login
   heroku create your-app-name
   git push heroku main
   ```
3. 환경 변수 설정:
   ```
   heroku config:set OPENAI_API_KEY=your_api_key_here
   heroku config:set GEMINI_API_KEY=your_api_key_here
   ```

## 참고 사항

- 앱 사용을 위해서는 OpenAI API 키가 필요합니다. Gemini API는 선택사항입니다.
- 최신 OpenAI Python 패키지(v1.12.0 이상)를 사용합니다. 이전 버전의 경우 호환성 문제가 발생할 수 있습니다.
- 첨삭 결과는 텍스트 파일로 저장할 수 있습니다. 
- 로컬에서 실행할 경우 파일 시스템에 접근할 수 있지만, 클라우드 서비스에 배포할 경우 로컬 파일 시스템에 저장하는 기능은 제한될 수 있습니다. 