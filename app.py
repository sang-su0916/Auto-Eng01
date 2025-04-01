import streamlit as st
import os
import openai
import pandas as pd
import numpy as np
import json
import hashlib
import csv
import io
import datetime
import altair as alt
import zipfile
from dotenv import load_dotenv
from problems import SAMPLE_PROBLEMS
from prompts import get_correction_prompt

# Load environment variables first
load_dotenv()

# Initialize API configurations
try:
    import google.generativeai as genai
    if os.getenv("GOOGLE_API_KEY"):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
except ImportError:
    st.error("google-generativeai 패키지가 설치되지 않았습니다. 'pip install google-generativeai'를 실행해주세요.")
except Exception as e:
    st.error(f"Gemini API 초기화 중 오류가 발생했습니다: {str(e)}")

# Initialize session state
if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
if 'gemini_api_key' not in st.session_state:
    st.session_state.gemini_api_key = os.getenv("GEMINI_API_KEY", "")

# Page configuration
st.set_page_config(
    page_title="학원자동시스템관리",
    page_icon="🏫",
    layout="wide"
)

# Function to initialize session states
def initialize_session_states():
    """세션 상태 초기화"""
    if 'current_problem' not in st.session_state:
        st.session_state.current_problem = None
    if 'user_answer' not in st.session_state:
        st.session_state.user_answer = ""
    if 'feedback' not in st.session_state:
        st.session_state.feedback = None
    if 'input_method' not in st.session_state:
        st.session_state.input_method = "text"
    if 'custom_problems' not in st.session_state:
        st.session_state.custom_problems = {}
    if 'save_dir' not in st.session_state:
        st.session_state.save_dir = os.getcwd()
    if 'last_problem_key' not in st.session_state:
        st.session_state.last_problem_key = None
    if 'selected_level' not in st.session_state:
        st.session_state.selected_level = "초급"
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'users' not in st.session_state:
        st.session_state.users = {}
    if 'teacher_problems' not in st.session_state:
        st.session_state.teacher_problems = {}
    if 'student_records' not in st.session_state:
        st.session_state.student_records = {}
    
    # API 키 초기화 - .env 파일에서 로드
    load_dotenv()
    if 'openai_api_key' not in st.session_state:
        st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
    if 'gemini_api_key' not in st.session_state:
        st.session_state.gemini_api_key = os.getenv("GEMINI_API_KEY", "")

# Initialize session state
initialize_session_states()

# User management functions
def save_users_data():
    """사용자 데이터를 JSON 파일로 저장"""
    try:
        data = {
            'teacher_problems': st.session_state.teacher_problems,
            'student_records': st.session_state.student_records,
            'users': st.session_state.users if 'users' in st.session_state else {}
        }
        with open('users_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"데이터 저장 중 오류 발생: {str(e)}")
        return False

def load_users_data():
    """JSON 파일에서 사용자 데이터 로드"""
    try:
        if os.path.exists('users_data.json'):
            with open('users_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                st.session_state.teacher_problems = data.get('teacher_problems', {})
                st.session_state.student_records = data.get('student_records', {})
                st.session_state.users = data.get('users', {})
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {str(e)}")

# Load user data at app start
load_users_data()

def hash_password(password):
    """비밀번호 해싱 함수"""
    return hashlib.sha256(password.encode()).hexdigest()

def login_user(username, password):
    """사용자 로그인 처리"""
    try:
        if username in st.session_state.users:
            hashed_password = hash_password(password)
            if st.session_state.users[username]["password"] == hashed_password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.user_role = st.session_state.users[username]["role"]
                
                # API 키 다시 로드
                load_dotenv()
                st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
                st.session_state.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
                
                return True
            else:
                st.error("비밀번호가 일치하지 않습니다.")
        else:
            st.error("존재하지 않는 사용자입니다.")
        return False
    except Exception as e:
        st.error(f"로그인 처리 중 오류가 발생했습니다: {e}")
        return False

def logout_user():
    """사용자 로그아웃 처리"""
    # API 키는 유지하지 않음
    st.session_state.clear()
    
    # 기본 상태 설정
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.user_role = None
    
    # API 키 재로드
    load_dotenv()
    st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
    st.session_state.gemini_api_key = os.getenv("GEMINI_API_KEY", "")

def register_user(username, password, role, name, email, created_by=None):
    """새 사용자 등록"""
    if username in st.session_state.users:
        return False, "이미 존재하는 사용자 이름입니다."
    
    hashed_password = hash_password(password)
    st.session_state.users[username] = {
        "password": hashed_password,
        "role": role,
        "name": name,
        "email": email,
        "created_by": created_by,
        "created_at": datetime.datetime.now().isoformat()
    }
    
    # 학생인 경우 학생 기록 초기화
    if role == "student":
        st.session_state.student_records[username] = {
            "solved_problems": [],
            "total_problems": 0,
            "feedback_history": []
        }
    
    save_users_data()
    return True, "사용자가 성공적으로 등록되었습니다."

# Login page
def login_page():
    st.title("학원자동시스템관리 - 로그인")
    
    # 로그인 폼
    username = st.text_input("아이디", key="login_username")
    password = st.text_input("비밀번호", type="password", key="login_password")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        login_button = st.button("로그인")
    
    if login_button:
        if login_user(username, password):
            st.success("로그인 성공!")
            st.rerun()
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    
    # 역할별 안내 정보
    with st.expander("역할별 안내", expanded=False):
        st.info("""
        ### 학생
        - 문제 풀기 및 학습 기록 확인
        - AI 첨삭 받기
        
        ### 교사
        - 문제 출제 및 관리
        - 학생 등록 및 관리
        - 학생 답변 채점 및 첨삭
        
        ### 관리자
        - 시스템 전체 관리
        - API 키 설정
        - 데이터 백업 및 복원
        """)

# Student Dashboard
def student_dashboard():
    st.title(f"학생 대시보드 - {st.session_state.users[st.session_state.username]['name']}님")
    
    # 사이드바 - 학생 메뉴
    st.sidebar.title("학생 메뉴")
    
    menu = st.sidebar.radio(
        "메뉴 선택:",
        ["문제 풀기", "내 학습 기록", "프로필"]
    )
    
    if menu == "문제 풀기":
        student_solve_problems()
    elif menu == "내 학습 기록":
        student_learning_history()
    elif menu == "프로필":
        student_profile()
    
    # 로그아웃 버튼
    logout_button = st.sidebar.button("로그아웃")
    if logout_button:
        logout_user()
        st.rerun()

def student_solve_problems():
    st.header("문제 풀기")
    
    # 카테고리 선택
    categories = list(set(p.get("category", "기타") for p in st.session_state.teacher_problems.values()))
    if categories:
        selected_category = st.selectbox("카테고리 선택:", categories)
        
        # 선택된 카테고리의 문제 목록
        category_problems = {k: v for k, v in st.session_state.teacher_problems.items() 
                           if v.get("category") == selected_category}
        
        if category_problems:
            problem_key = st.selectbox(
                "문제 선택:",
                list(category_problems.keys()),
                format_func=lambda x: f"{x} ({category_problems[x].get('level', '난이도 미지정')})"
            )
            
            if problem_key:
                display_and_solve_problem(problem_key, category_problems[problem_key])
        else:
            st.info("선택한 카테고리에 문제가 없습니다.")
    else:
        st.info("아직 등록된 문제가 없습니다. 선생님께 문의해주세요.")

def student_learning_history():
    st.header("내 학습 기록")
    
    # 로그인한 학생의 기록 가져오기
    username = st.session_state.username
    if username not in st.session_state.student_records:
        st.info("아직 학습 기록이 없습니다. 문제를 풀어보세요!")
        return
    
    student_data = st.session_state.student_records[username]
    
    # 학습 통계 표시
    st.subheader("학습 통계")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("총 학습 문제 수", student_data["total_problems"])
    
    with col2:
        # 이번 주에 푼 문제 수
        week_problems = 0
        today = datetime.datetime.now()
        week_start = today - datetime.timedelta(days=today.weekday())
        
        for problem in student_data["solved_problems"]:
            try:
                problem_time = datetime.datetime.fromisoformat(problem["timestamp"])
                if problem_time >= week_start:
                    week_problems += 1
            except:
                pass
        
        st.metric("이번 주 학습 수", week_problems)
    
    with col3:
        # 오늘 푼 문제 수
        today_problems = 0
        today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for problem in student_data["solved_problems"]:
            try:
                problem_time = datetime.datetime.fromisoformat(problem["timestamp"])
                if problem_time >= today_start:
                    today_problems += 1
            except:
                pass
        
        st.metric("오늘 학습 수", today_problems)
    
    # 카테고리별 문제 분포
    if student_data["solved_problems"]:
        st.subheader("카테고리별 학습 분포")
        
        # 카테고리별 문제 수 계산
        categories = {}
        for problem in student_data["solved_problems"]:
            category = problem["problem"].get("category", "기타")
            if category in categories:
                categories[category] += 1
            else:
                categories[category] = 1
        
        # 데이터프레임 생성
        df = pd.DataFrame({
            "카테고리": list(categories.keys()),
            "문제 수": list(categories.values())
        })
        
        # 차트 생성
        chart = alt.Chart(df).mark_bar().encode(
            x="문제 수:Q",
            y=alt.Y("카테고리:N", sort="-x"),
            color=alt.Color("카테고리:N", legend=None),
            tooltip=["카테고리", "문제 수"]
        ).properties(
            title="카테고리별 학습 분포"
        )
        
        st.altair_chart(chart, use_container_width=True)
    
    # 최근 학습 기록
    st.subheader("최근 학습 기록")
    
    if not student_data["solved_problems"]:
        st.info("아직 학습 기록이 없습니다.")
    else:
        # 최근 5개 기록 표시
        recent_problems = sorted(
            student_data["solved_problems"], 
            key=lambda x: x["timestamp"] if "timestamp" in x else "", 
            reverse=True
        )[:5]
        
        for i, problem in enumerate(recent_problems):
            try:
                with st.expander(f"{i+1}. {problem['problem']['question'][:50]}... ({datetime.datetime.fromisoformat(problem['timestamp']).strftime('%Y-%m-%d %H:%M')})"):
                    st.subheader("문제")
                    st.write(problem["problem"]["question"])
                    
                    st.subheader("나의 답변")
                    st.write(problem["answer"])
                    
                    st.subheader("AI 첨삭")
                    st.markdown(problem["feedback"])
            except:
                st.error(f"기록 {i+1}을 표시하는 데 문제가 발생했습니다.")

def student_profile():
    st.header("내 프로필")
    
    username = st.session_state.username
    user_data = st.session_state.users[username]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("기본 정보")
        st.write(f"**이름:** {user_data['name']}")
        st.write(f"**이메일:** {user_data['email']}")
        st.write(f"**사용자 유형:** 학생")
        
        if "created_at" in user_data:
            try:
                created_at = datetime.datetime.fromisoformat(user_data["created_at"])
                st.write(f"**가입일:** {created_at.strftime('%Y-%m-%d')}")
            except:
                st.write(f"**가입일:** {user_data['created_at']}")
        
        if "created_by" in user_data and user_data["created_by"]:
            st.write(f"**등록한 교사:** {user_data['created_by']}")
    
    with col2:
        st.subheader("비밀번호 변경")
        
        current_password = st.text_input("현재 비밀번호", type="password")
        new_password = st.text_input("새 비밀번호", type="password")
        confirm_password = st.text_input("새 비밀번호 확인", type="password")
        
        if st.button("비밀번호 변경"):
            if not current_password or not new_password or not confirm_password:
                st.error("모든 필드를 입력해주세요.")
            elif hash_password(current_password) != user_data["password"]:
                st.error("현재 비밀번호가 올바르지 않습니다.")
            elif new_password != confirm_password:
                st.error("새 비밀번호와 확인이 일치하지 않습니다.")
            elif len(new_password) < 6:
                st.error("비밀번호는 최소 6자 이상이어야 합니다.")
            else:
                st.session_state.users[username]["password"] = hash_password(new_password)
                save_users_data()
                st.success("비밀번호가 성공적으로 변경되었습니다.")

# Teacher Dashboard
def teacher_dashboard():
    st.title(f"교사 대시보드 - {st.session_state.users[st.session_state.username]['name']}님")
    
    # 사이드바 - 교사 메뉴
    st.sidebar.title("교사 메뉴")
    
    menu = st.sidebar.radio(
        "메뉴 선택:",
        ["문제 관리", "학생 관리", "채점 및 첨삭", "프로필"]
    )
    
    if menu == "문제 관리":
        teacher_problem_management()
    elif menu == "학생 관리":
        teacher_student_management()
    elif menu == "채점 및 첨삭":
        teacher_grading()
    elif menu == "프로필":
        teacher_profile()
    
    # 로그아웃 버튼
    logout_button = st.sidebar.button("로그아웃")
    if logout_button:
        logout_user()
        st.rerun()

def check_api_key():
    """API 키 유효성을 확인하는 함수"""
    has_openai = bool(st.session_state.openai_api_key.strip())
    has_gemini = bool(st.session_state.gemini_api_key.strip())
    return has_openai or has_gemini

def save_generated_problems(problems, school_type, grade, topic, difficulty):
    """생성된 문제를 저장하는 함수"""
    try:
        if 'teacher_problems' not in st.session_state:
            st.session_state.teacher_problems = {}
        
        # 문제 데이터 구조화
        problem_data = {
            "school_type": school_type,
            "grade": grade,
            "topic": topic,
            "difficulty": difficulty,
            "content": problems,
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_by": st.session_state.username,
            "status": "approved"
        }
        
        # 고유한 키 생성
        problem_key = f"{school_type}_{grade}_{topic}_{difficulty}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 문제 저장
        st.session_state.teacher_problems[problem_key] = problem_data
        
        # 데이터 저장
        if save_users_data():
            return True, "문제가 성공적으로 저장되었습니다."
        else:
            return False, "문제 저장 중 오류가 발생했습니다."
    except Exception as e:
        return False, f"문제 저장 중 오류 발생: {str(e)}"

def generate_ai_problems():
    """AI를 사용하여 문제 생성"""
    try:
        st.subheader("AI로 문제 생성하기")
        
        # API 키 설정 섹션
        st.info("API 키가 설정되지 않은 경우 여기서 직접 입력할 수 있습니다.")
        
        # API 키 입력 옵션
        api_key_option = st.radio(
            "API 키 설정 방식:",
            ["환경 변수 사용", "직접 입력"],
            help="API 키를 환경 변수에서 가져올지, 직접 입력할지 선택하세요."
        )
        
        if api_key_option == "직접 입력":
            col1, col2 = st.columns(2)
            with col1:
                temp_openai_key = st.text_input(
                    "OpenAI API 키 입력:",
                    type="password",
                    value=st.session_state.openai_api_key
                )
            with col2:
                temp_gemini_key = st.text_input(
                    "Gemini API 키 입력:",
                    type="password",
                    value=st.session_state.gemini_api_key
                )
            
            # 임시 API 키 저장
            if st.button("API 키 적용"):
                st.session_state.openai_api_key = temp_openai_key
                st.session_state.gemini_api_key = temp_gemini_key
                if temp_gemini_key:
                    genai.configure(api_key=temp_gemini_key)
                st.success("API 키가 적용되었습니다.")
        
        st.markdown("---")
        
        # 학교급 선택
        school_type = st.selectbox(
            "학교급:", 
            ["중학교", "고등학교"],
            help="학교 급별을 선택하세요."
        )
        
        # 학년 선택
        grade = st.selectbox(
            "학년:", 
            ["1학년", "2학년", "3학년"],
            help="학년을 선택하세요."
        )
        
        # 주제 선택
        topic = st.selectbox(
            "주제:", 
            [
                "일상생활/자기소개",
                "학교생활/교육",
                "취미/여가활동",
                "환경/사회문제",
                "과학/기술",
                "문화/예술",
                "진로/직업"
            ],
            help="문제의 주제를 선택하세요."
        )
        
        # 난이도 선택
        difficulty = st.selectbox(
            "난이도:", 
            ["하", "중", "상"],
            help="문제의 난이도를 선택하세요."
        )
        
        # 생성할 문제 수
        num_problems = st.slider(
            "생성할 문제 수:", 
            min_value=1, 
            max_tokens=10, 
            value=5,
            help="한 번에 생성할 문제의 수를 선택하세요."
        )
        
        # AI 모델 선택
        model_choice = st.radio(
            "사용할 AI 모델:", 
            ["OpenAI GPT", "Google Gemini"],
            help="문제 생성에 사용할 AI 모델을 선택하세요."
        )

        if st.button("AI 문제 생성하기"):
            if not check_api_key():
                st.error("API 키가 설정되지 않았습니다. 위에서 API 키를 입력하거나 관리자 설정에서 API 키를 확인해주세요.")
                return

            with st.spinner("문제를 생성하는 중입니다..."):
                try:
                    # 학교급별 난이도 조정을 위한 기준 설정
                    level_criteria = {
                        "중학교": {
                            "하": "기초 영어 문법과 어휘, 간단한 일상 표현",
                            "중": "기본 영어 문법과 어휘, 일반적인 상황에서의 의사소통",
                            "상": "심화 영어 문법과 어휘, 다양한 상황에서의 의사소통"
                        },
                        "고등학교": {
                            "하": "고교 기초 수준의 영어 문법과 어휘, 일반적인 주제의 의사소통",
                            "중": "고교 중급 수준의 영어 문법과 어휘, 다양한 주제의 의사소통",
                            "상": "고교 심화 수준의 영어 문법과 어휘, 학술적/전문적 주제의 의사소통"
                        }
                    }

                    # 프롬프트 생성
                    base_prompt = f"""
영어 문제를 생성해주세요:

[기본 정보]
- 학교급: {school_type}
- 학년: {grade}
- 주제: {topic}
- 난이도: {difficulty}
- 문제 수: {num_problems}개

[난이도 기준]
{level_criteria[school_type][difficulty]}

[문제 형식]
각 문제는 다음 형식을 정확히 따라주세요:

[문제 1]
유형: [객관식/주관식/서술형]
문제: (영어로 된 문제 내용)
맥락: (문제의 상황 설명)
보기: (객관식인 경우)
A. 
B. 
C. 
D. 
정답: 
해설: (영어 학습 포인트 설명)

[문제 2]
...

[주의사항]
1. {school_type} {grade} 수준에 맞는 어휘와 문법 사용
2. {difficulty}난이도에 맞는 복잡성과 사고력 요구
3. 실용적이고 실생활에서 활용 가능한 내용
4. 명확한 정답과 상세한 해설 제공
5. 각 문제는 독립적이며 서로 다른 학습 포인트 포함
"""

                    problems = None
                    
                    # OpenAI GPT 사용
                    if model_choice == "OpenAI GPT" and st.session_state.get('openai_api_key'):
                        client = openai.OpenAI(api_key=st.session_state.openai_api_key)
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": base_prompt}],
                            temperature=0.7,
                            max_tokens=3000
                        )
                        problems = response.choices[0].message.content
                    
                    # Google Gemini 사용
                    elif model_choice == "Google Gemini" and st.session_state.get('gemini_api_key'):
                        genai.configure(api_key=st.session_state.gemini_api_key)
                        model = genai.GenerativeModel('gemini-pro')
                        response = model.generate_content(base_prompt)
                        if response and hasattr(response, 'text'):
                            problems = response.text
                        else:
                            st.error("Gemini API가 유효한 응답을 반환하지 않았습니다.")
                            return
                    
                    if problems and len(problems.strip()) > 0:
                        # 생성된 문제 표시
                        st.success("문제가 생성되었습니다. 검토 후 저장해주세요.")
                        
                        # 교사 검토를 위한 편집 가능한 텍스트 영역
                        edited_problems = st.text_area(
                            "생성된 문제 검토 및 수정",
                            value=problems,
                            height=400,
                            key="problem_edit_area"
                        )
                        
                        # 저장 버튼
                        if st.button("검토 완료 및 저장", key="save_problems"):
                            if not edited_problems.strip():
                                st.error("저장할 문제 내용이 없습니다.")
                                return
                            
                            success, message = save_generated_problems(
                                edited_problems,
                                school_type,
                                grade,
                                topic,
                                difficulty
                            )
                            
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                    else:
                        st.error("문제 생성에 실패했습니다. 다시 시도해주세요.")
                
                except Exception as e:
                    st.error(f"문제 생성 중 오류가 발생했습니다: {str(e)}")
                    return
    
    except Exception as e:
        st.error(f"오류가 발생했습니다: {str(e)}")
        return

def teacher_problem_management():
    st.header("문제 관리")
    
    tab1, tab2, tab3, tab4 = st.tabs(["문제 목록", "직접 문제 출제", "CSV로 문제 업로드", "AI 문제 생성"])
    
    # 문제 목록 탭
    with tab1:
        st.subheader("출제한 문제 목록")
        
        teacher_problems = st.session_state.teacher_problems
        if not teacher_problems:
            st.info("아직 출제한 문제가 없습니다. 다른 탭에서 문제를 출제해보세요.")
        else:
            # 카테고리별로 정렬
            categories = {}
            for key, problem in teacher_problems.items():
                # 현재 교사가 출제한 문제만 표시
                if problem.get("created_by") == st.session_state.username:
                    category = problem.get("category", "기타")
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(key)
            
            if not categories:
                st.info("아직 출제한 문제가 없습니다. 다른 탭에서 문제를 출제해보세요.")
            else:
                # 카테고리 선택
                selected_category = st.selectbox(
                    "카테고리:",
                    list(categories.keys()),
                    key="view_category"
                )
                
                # 선택된 카테고리의 문제 목록
                if selected_category:
                    for key in categories[selected_category]:
                        problem = teacher_problems[key]
                        with st.expander(f"{key.split('/')[-1] if '/' in key else key}"):
                            st.write(f"**문제:** {problem['question']}")
                            st.write(f"**맥락:** {problem['context']}")
                            if 'example' in problem and problem['example']:
                                st.write(f"**예시 답안:** {problem['example']}")
                            
                            if st.button(f"삭제: {key}", key=f"delete_{key}"):
                                if key in st.session_state.teacher_problems:
                                    del st.session_state.teacher_problems[key]
                                    save_users_data()
                                    st.success(f"문제 '{key}'가 삭제되었습니다.")
                                    st.rerun()
    
    # 직접 문제 출제 탭
    with tab2:
        st.subheader("새 문제 출제하기")
        
        # 문제 유형 선택
        problem_type = st.radio("문제 유형:", ["객관식", "주관식"], horizontal=True)
        
        # 카테고리 선택
        custom_category = st.selectbox(
            "문제 카테고리:", 
            ["일상생활/자기소개", "학교생활/교육", "취미/여가활동", "여행/문화체험", 
             "환경/사회문제", "과학/기술", "직업/진로", "건강/운동", 
             "음식/요리", "예술/엔터테인먼트", "경제/비즈니스", "시사/뉴스",
             "가족/인간관계", "감정/심리", "자연/동물", "기타"],
            key="new_category"
        )
        
        # 문제 이름
        custom_name = st.text_input("문제 이름:", key="new_name")
        
        # 문제 내용
        custom_question = st.text_area("문제를 입력하세요:", height=100, key="new_question")
        custom_context = st.text_area("문제의 맥락을 입력하세요:", height=100, key="new_context")
        
        # 객관식인 경우 보기 입력
        if problem_type == "객관식":
            st.subheader("보기 입력")
            options = []
            for i in range(4):
                option = st.text_input(f"보기 {i+1}:", key=f"option_{i}")
                if option:
                    options.append(option)
            correct_answer = st.selectbox("정답 선택:", [f"보기 {i+1}" for i in range(len(options))] if options else [])
        
        # 주관식인 경우 예시 답안
        else:
            custom_example = st.text_area("예시 답안을 입력하세요:", height=100, key="new_example")
        
        # 난이도 선택
        level_options = ["초급(초)", "초급(중)", "초급(상)", "중급(초)", "중급(중)", "중급(상)", "상급(초)", "상급(중)", "상급(상)"]
        custom_level = st.selectbox("난이도:", level_options, key="new_level")
        
        if st.button("문제 저장하기"):
            if not custom_name or not custom_question or not custom_context:
                st.error("문제 이름, 문제 내용, 맥락은 필수 입력사항입니다.")
            elif problem_type == "객관식" and (len(options) < 4 or not correct_answer):
                st.error("객관식 문제는 4개의 보기와 정답을 모두 입력해야 합니다.")
            else:
                problem_key = f"{custom_category}/{custom_name}"
                
                # 중복 확인
                if problem_key in st.session_state.teacher_problems:
                    st.error(f"동일한 카테고리와 이름의 문제가 이미 존재합니다: {problem_key}")
                else:
                    # 문제 저장
                    problem_data = {
                        "category": custom_category,
                        "question": custom_question,
                        "context": custom_context,
                        "type": problem_type,
                        "level": custom_level,
                        "created_by": st.session_state.username,
                        "created_at": datetime.datetime.now().isoformat()
                    }
                    
                    if problem_type == "객관식":
                        problem_data["options"] = options
                        problem_data["correct_answer"] = correct_answer
                    else:
                        problem_data["example"] = custom_example
                    
                    st.session_state.teacher_problems[problem_key] = problem_data
                    save_users_data()
                    st.success(f"문제 '{custom_name}'이(가) 저장되었습니다.")
    
    # CSV로 문제 업로드 탭
    with tab3:
        st.subheader("CSV로 문제 업로드")
        
        st.info("""
        CSV 파일 형식:
        - 첫 번째 행: 헤더 (name,category,question,context,example,level)
        - 각 행: 하나의 문제
        - 필수 열: name, category, question, context
        - 선택 열: example, level
        """)
        
        # 예시 CSV 다운로드
        example_csv = """name,category,question,context,example,level
영어소개,개인/일상생활,Introduce yourself in English.,This is a self-introduction for a job interview.,"Hello, my name is...",초급(중)
취미설명,개인/일상생활,Describe your hobbies.,You are talking about your free time activities.,"I enjoy playing soccer...",초급(상)"""
        
        st.download_button(
            label="예시 CSV 다운로드",
            data=example_csv,
            file_name="example_problems.csv",
            mime="text/csv"
        )
        
        # CSV 파일 업로드
        uploaded_file = st.file_uploader("CSV 파일 업로드", type=["csv"])
        
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                
                # 필수 열 확인
                required_columns = ["name", "category", "question", "context"]
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    st.error(f"CSV 파일에 필수 열이 누락되었습니다: {', '.join(missing_columns)}")
                else:
                    # 업로드된 문제 미리보기
                    st.subheader("업로드된 문제 미리보기")
                    st.dataframe(df)
                    
                    if st.button("문제 저장하기", key="csv_save"):
                        imported_count = 0
                        skipped_count = 0
                        
                        for _, row in df.iterrows():
                            try:
                                name = str(row["name"]).strip()
                                category = str(row["category"]).strip()
                                question = str(row["question"]).strip()
                                context = str(row["context"]).strip()
                                example = str(row["example"]).strip() if "example" in row and not pd.isna(row["example"]) else ""
                                level = str(row["level"]).strip() if "level" in row and not pd.isna(row["level"]) else "초급(중)"
                                
                                # 필수 필드 확인
                                if not name or not category or not question or not context:
                                    skipped_count += 1
                                    continue
                                
                                problem_key = f"{category}/{name}"
                                
                                # 중복 확인
                                if problem_key in st.session_state.teacher_problems:
                                    skipped_count += 1
                                    continue
                                
                                # 문제 저장
                                st.session_state.teacher_problems[problem_key] = {
                                    "category": category,
                                    "question": question,
                                    "context": context,
                                    "example": example,
                                    "level": level,
                                    "created_by": st.session_state.username,
                                    "created_at": datetime.datetime.now().isoformat()
                                }
                                
                                imported_count += 1
                            
                            except Exception as e:
                                skipped_count += 1
                        
                        save_users_data()
                        st.success(f"{imported_count}개의 문제가 성공적으로 저장되었습니다. {skipped_count}개의 문제가 건너뛰어졌습니다.")
            
            except Exception as e:
                st.error(f"CSV 파일 처리 중 오류가 발생했습니다: {e}")
    
    # AI 문제 생성 탭
    with tab4:
        generate_ai_problems()

def teacher_student_management():
    st.header("학생 관리")
    
    tab1, tab2, tab3 = st.tabs(["학생 등록", "학생 목록", "학생 성적 및 진도"])
    
    # 학생 등록 탭
    with tab1:
        st.subheader("새 학생 등록")
        
        username = st.text_input("학생 아이디:", key="new_student_username")
        name = st.text_input("학생 이름:", key="new_student_name")
        email = st.text_input("학생 이메일 (선택):", key="new_student_email")
        password = st.text_input("비밀번호:", type="password", key="new_student_password")
        confirm_password = st.text_input("비밀번호 확인:", type="password", key="new_student_confirm")
        
        if st.button("학생 등록"):
            if not username or not name or not password:
                st.error("학생 아이디, 이름, 비밀번호는 필수 입력사항입니다.")
            elif password != confirm_password:
                st.error("비밀번호와 비밀번호 확인이 일치하지 않습니다.")
            elif username in st.session_state.users:
                st.error(f"이미 존재하는 아이디입니다: {username}")
            elif len(password) < 6:
                st.error("비밀번호는 최소 6자 이상이어야 합니다.")
            else:
                # 학생 등록
                success, message = register_user(
                    username, 
                    password, 
                    "student", 
                    name, 
                    email, 
                    created_by=st.session_state.username
                )
                
                if success:
                    st.success(f"학생 '{name}'이(가) 성공적으로 등록되었습니다.")
                else:
                    st.error(message)
    
    # 학생 목록 탭
    with tab2:
        st.subheader("등록된 학생 목록")
        
        # 현재 교사가 등록한 학생만 필터링
        teacher_students = {}
        for username, user_data in st.session_state.users.items():
            if user_data["role"] == "student" and user_data.get("created_by") == st.session_state.username:
                teacher_students[username] = user_data
        
        if not teacher_students:
            st.info("아직 등록한 학생이 없습니다. '학생 등록' 탭에서 학생을 추가하세요.")
        else:
            # 표로 보여주기
            student_data = []
            for username, user_data in teacher_students.items():
                try:
                    created_at = datetime.datetime.fromisoformat(user_data.get("created_at", "")).strftime("%Y-%m-%d")
                except:
                    created_at = user_data.get("created_at", "")
                
                # 학생 기록에서 총 문제 수 가져오기
                total_problems = 0
                if username in st.session_state.student_records:
                    total_problems = st.session_state.student_records[username].get("total_problems", 0)
                
                student_data.append({
                    "아이디": username,
                    "이름": user_data.get("name", ""),
                    "이메일": user_data.get("email", ""),
                    "등록일": created_at,
                    "푼 문제 수": total_problems
                })
            
            df = pd.DataFrame(student_data)
            st.dataframe(df, use_container_width=True)
            
            # 선택한 학생 삭제
            st.subheader("학생 계정 관리")
            selected_student = st.selectbox(
                "학생 선택:",
                list(teacher_students.keys()),
                format_func=lambda x: f"{x} ({teacher_students[x].get('name', '')})"
            )
            
            if selected_student:
                st.warning(f"주의: 학생 계정을 삭제하면 모든 학습 기록이 함께 삭제됩니다.")
                confirm_delete = st.checkbox("삭제를 확인합니다")
                
                if st.button("선택한 학생 삭제") and confirm_delete:
                    # 학생 삭제
                    if selected_student in st.session_state.users:
                        del st.session_state.users[selected_student]
                    
                    # 학생 기록 삭제
                    if selected_student in st.session_state.student_records:
                        del st.session_state.student_records[selected_student]
                    
                    save_users_data()
                    st.success(f"학생 '{selected_student}'이(가) 삭제되었습니다.")
                    st.rerun()
    
    # 학생 성적 및 진도 탭
    with tab3:
        st.subheader("학생 성적 및 진도")
        
        # 현재 교사가 등록한 학생만 필터링
        teacher_students = {}
        for username, user_data in st.session_state.users.items():
            if user_data["role"] == "student" and user_data.get("created_by") == st.session_state.username:
                teacher_students[username] = user_data
        
        if not teacher_students:
            st.info("아직 등록한 학생이 없습니다. '학생 등록' 탭에서 학생을 추가하세요.")
        else:
            # 학생 선택
            selected_student = st.selectbox(
                "학생 선택:",
                list(teacher_students.keys()),
                format_func=lambda x: f"{x} ({teacher_students[x].get('name', '')})",
                key="progress_student"
            )
            
            if selected_student:
                st.write(f"**학생 이름:** {teacher_students[selected_student].get('name', '')}")
                
                # 학생 기록 가져오기
                if selected_student in st.session_state.student_records:
                    student_data = st.session_state.student_records[selected_student]
                    
                    # 기본 통계
                    st.write(f"**총 푼 문제 수:** {student_data.get('total_problems', 0)}")
                    
                    solved_problems = student_data.get("solved_problems", [])
                    if solved_problems:
                        # 최근 활동 시간
                        try:
                            recent_problem = max(solved_problems, key=lambda x: x.get("timestamp", "") if "timestamp" in x else "")
                            recent_time = datetime.datetime.fromisoformat(recent_problem.get("timestamp", "")).strftime("%Y-%m-%d %H:%M")
                            st.write(f"**최근 활동:** {recent_time}")
                        except:
                            st.write("**최근 활동:** 정보 없음")
                        
                        # 카테고리별 문제 수 계산
                        categories = {}
                        for problem in solved_problems:
                            category = problem["problem"].get("category", "기타")
                            if category in categories:
                                categories[category] += 1
                            else:
                                categories[category] = 1
                        
                        # 차트 생성
                        st.subheader("카테고리별 학습 분포")
                        df = pd.DataFrame({
                            "카테고리": list(categories.keys()),
                            "문제 수": list(categories.values())
                        })
                        
                        chart = alt.Chart(df).mark_bar().encode(
                            x="문제 수:Q",
                            y=alt.Y("카테고리:N", sort="-x"),
                            color=alt.Color("카테고리:N", legend=None),
                            tooltip=["카테고리", "문제 수"]
                        ).properties(
                            title="카테고리별 학습 분포"
                        )
                        
                        st.altair_chart(chart, use_container_width=True)
                        
                        # 주간 학습 추세
                        st.subheader("주간 학습 추세")
                        
                        # 최근 4주 데이터 수집
                        today = datetime.datetime.now()
                        weeks_data = {}
                        
                        for i in range(4):
                            week_start = today - datetime.timedelta(days=today.weekday() + 7*i)
                            week_end = week_start + datetime.timedelta(days=6)
                            week_label = f"{week_start.strftime('%m/%d')}~{week_end.strftime('%m/%d')}"
                            weeks_data[week_label] = 0
                        
                        for problem in solved_problems:
                            try:
                                problem_time = datetime.datetime.fromisoformat(problem["timestamp"])
                                for i in range(4):
                                    week_start = today - datetime.timedelta(days=today.weekday() + 7*i)
                                    week_end = week_start + datetime.timedelta(days=6)
                                    week_label = f"{week_start.strftime('%m/%d')}~{week_end.strftime('%m/%d')}"
                                    
                                    if week_start <= problem_time <= week_end:
                                        weeks_data[week_label] += 1
                                        break
                            except:
                                pass
                        
                        # 데이터프레임 생성 (역순으로 정렬)
                        weekly_df = pd.DataFrame({
                            "주차": list(reversed(list(weeks_data.keys()))),
                            "문제 수": list(reversed(list(weeks_data.values())))
                        })
                        
                        # 차트 생성
                        st.line_chart(weekly_df.set_index("주차"))
                        
                        # 최근 학습 기록
                        st.subheader("최근 학습 기록")
                        recent_problems = sorted(
                            solved_problems, 
                            key=lambda x: x["timestamp"] if "timestamp" in x else "", 
                            reverse=True
                        )[:5]
                        
                        for i, problem in enumerate(recent_problems):
                            try:
                                with st.expander(f"{i+1}. {problem['problem']['question'][:50]}... ({datetime.datetime.fromisoformat(problem['timestamp']).strftime('%Y-%m-%d %H:%M')})"):
                                    st.write(f"**문제:** {problem['problem']['question']}")
                                    st.write(f"**답변:** {problem['answer']}")
                                    with st.expander("AI 첨삭 보기"):
                                        st.markdown(problem['feedback'])
                            except:
                                st.error(f"기록 {i+1}을 표시하는 데 문제가 발생했습니다.")
                    else:
                        st.info("이 학생은 아직 문제를 풀지 않았습니다.")
                else:
                    st.info("이 학생의 학습 기록이 없습니다.")

def teacher_grading():
    st.header("채점 및 첨삭")
    
    st.info("이 섹션에서는 학생들의 답변을 직접 채점하고 첨삭할 수 있습니다.")
    
    # 채점할 학생 선택
    teacher_students = {}
    for username, user_data in st.session_state.users.items():
        if user_data["role"] == "student" and user_data.get("created_by") == st.session_state.username:
            teacher_students[username] = user_data
    
    if not teacher_students:
        st.warning("아직 등록한 학생이 없습니다. '학생 관리' 메뉴에서 학생을 추가하세요.")
    else:
        selected_student = st.selectbox(
            "학생 선택:",
            list(teacher_students.keys()),
            format_func=lambda x: f"{x} ({teacher_students[x].get('name', '')})",
            key="grading_student"
        )
        
        if selected_student:
            st.write(f"**선택한 학생:** {teacher_students[selected_student].get('name', '')}")
            
            # 학생 기록 가져오기
            if selected_student in st.session_state.student_records:
                student_data = st.session_state.student_records[selected_student]
                solved_problems = student_data.get("solved_problems", [])
                
                if not solved_problems:
                    st.info("이 학생은 아직 문제를 풀지 않았습니다.")
                else:
                    # 답변 목록 표시
                    st.subheader("채점할 답변 선택")
                    
                    # 답변 데이터 준비
                    answer_data = []
                    for i, problem in enumerate(solved_problems):
                        try:
                            timestamp = datetime.datetime.fromisoformat(problem.get("timestamp", "")).strftime("%Y-%m-%d %H:%M")
                            
                            # 교사 채점 여부 확인
                            has_teacher_feedback = "teacher_feedback" in problem
                            
                            answer_data.append({
                                "index": i,
                                "문제": problem["problem"]["question"][:30] + "...",
                                "제출일시": timestamp,
                                "카테고리": problem["problem"].get("category", "기타"),
                                "교사 채점": "완료" if has_teacher_feedback else "미완료"
                            })
                        except:
                            pass
                    
                    if not answer_data:
                        st.info("표시할 수 있는 답변이 없습니다.")
                    else:
                        # 데이터프레임으로 표시
                        df = pd.DataFrame(answer_data)
                        st.dataframe(df.drop(columns=["index"]), use_container_width=True)
                        
                        # 채점할 답변 선택
                        selected_answer_index = st.selectbox(
                            "채점할 답변을 선택하세요:",
                            options=df["index"].tolist(),
                            format_func=lambda x: f"{df[df['index']==x]['문제'].iloc[0]} ({df[df['index']==x]['제출일시'].iloc[0]})"
                        )
                        
                        if selected_answer_index is not None:
                            problem = solved_problems[selected_answer_index]
                            
                            st.markdown("---")
                            st.subheader("학생 답변 채점")
                            
                            # 문제 및 답변 표시
                            st.write("**문제:**")
                            st.write(problem["problem"]["question"])
                            
                            st.write("**맥락:**")
                            st.write(problem["problem"]["context"])
                            
                            st.write("**학생 답변:**")
                            st.write(problem["answer"])
                            
                            # AI 첨삭 결과 표시
                            with st.expander("AI 첨삭 결과 보기"):
                                st.markdown(problem["feedback"])
                            
                            # 교사 첨삭 입력
                            st.subheader("교사 첨삭")
                            
                            # 이전 교사 첨삭이 있으면 표시
                            previous_feedback = problem.get("teacher_feedback", "")
                            previous_score = problem.get("teacher_score", 0)
                            
                            teacher_feedback = st.text_area(
                                "첨삭 내용을 입력하세요:",
                                value=previous_feedback,
                                height=200
                            )
                            
                            teacher_score = st.slider(
                                "점수 (0-100):",
                                0, 100, previous_score if previous_score else 70
                            )
                            
                            if st.button("채점 저장"):
                                # 교사 첨삭 정보 저장
                                st.session_state.student_records[selected_student]["solved_problems"][selected_answer_index]["teacher_feedback"] = teacher_feedback
                                st.session_state.student_records[selected_student]["solved_problems"][selected_answer_index]["teacher_score"] = teacher_score
                                st.session_state.student_records[selected_student]["solved_problems"][selected_answer_index]["graded_by"] = st.session_state.username
                                st.session_state.student_records[selected_student]["solved_problems"][selected_answer_index]["graded_at"] = datetime.datetime.now().isoformat()
                                
                                save_users_data()
                                st.success("채점이 저장되었습니다.")
            else:
                st.info("이 학생의 학습 기록이 없습니다.")

def teacher_profile():
    st.header("내 프로필")
    
    username = st.session_state.username
    user_data = st.session_state.users[username]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("기본 정보")
        st.write(f"**이름:** {user_data['name']}")
        st.write(f"**이메일:** {user_data.get('email', '')}")
        st.write(f"**사용자 유형:** 교사")
        
        if "created_at" in user_data:
            try:
                created_at = datetime.datetime.fromisoformat(user_data["created_at"])
                st.write(f"**가입일:** {created_at.strftime('%Y-%m-%d')}")
            except:
                st.write(f"**가입일:** {user_data['created_at']}")
        
        # 교사 통계
        st.subheader("교사 활동 통계")
        
        # 출제한 문제 수
        problem_count = 0
        for problem in st.session_state.teacher_problems.values():
            if problem.get("created_by") == username:
                problem_count += 1
        
        st.write(f"**출제한 문제 수:** {problem_count}")
        
        # 등록한 학생 수
        student_count = 0
        for student in st.session_state.users.values():
            if student.get("role") == "student" and student.get("created_by") == username:
                student_count += 1
        
        st.write(f"**등록한 학생 수:** {student_count}")
        
        # 채점한 답변 수
        graded_count = 0
        for student_id, student_record in st.session_state.student_records.items():
            for problem in student_record.get("solved_problems", []):
                if problem.get("graded_by") == username:
                    graded_count += 1
        
        st.write(f"**채점한 답변 수:** {graded_count}")
    
    with col2:
        st.subheader("비밀번호 변경")
        
        current_password = st.text_input("현재 비밀번호", type="password")
        new_password = st.text_input("새 비밀번호", type="password")
        confirm_password = st.text_input("새 비밀번호 확인", type="password")
        
        if st.button("비밀번호 변경"):
            if not current_password or not new_password or not confirm_password:
                st.error("모든 필드를 입력해주세요.")
            elif hash_password(current_password) != user_data["password"]:
                st.error("현재 비밀번호가 올바르지 않습니다.")
            elif new_password != confirm_password:
                st.error("새 비밀번호와 확인이 일치하지 않습니다.")
            elif len(new_password) < 6:
                st.error("비밀번호는 최소 6자 이상이어야 합니다.")
            else:
                st.session_state.users[username]["password"] = hash_password(new_password)
                save_users_data()
                st.success("비밀번호가 성공적으로 변경되었습니다.")

# Admin Dashboard
def admin_dashboard():
    st.title(f"관리자 대시보드 - {st.session_state.users[st.session_state.username]['name']}님")
    
    # 사이드바 - 관리자 메뉴
    st.sidebar.title("관리자 메뉴")
    
    menu = st.sidebar.radio(
        "메뉴 선택:",
        ["API 키 설정", "사용자 관리", "백업 및 복원", "시스템 정보"]
    )
    
    if menu == "API 키 설정":
        admin_api_settings()
    elif menu == "사용자 관리":
        admin_user_management()
    elif menu == "백업 및 복원":
        admin_backup_restore()
    elif menu == "시스템 정보":
        admin_system_info()
    
    # 로그아웃 버튼
    logout_button = st.sidebar.button("로그아웃")
    if logout_button:
        logout_user()
        st.rerun()

def admin_api_settings():
    st.header("API 키 설정")
    
    st.info("이 페이지에서 OpenAI 및 Google Gemini API 키를 설정할 수 있습니다. API 키는 암호화되지 않고 저장되므로 주의하세요.")
    
    # API 키 유지/리셋 옵션
    st.subheader("API 키 관리 옵션")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("API 키 유지하기"):
            st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
            st.session_state.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
            st.success("API 키가 환경 변수에서 다시 로드되었습니다.")
    
    with col2:
        if st.button("API 키 초기화"):
            st.session_state.openai_api_key = ""
            st.session_state.gemini_api_key = ""
            try:
                with open(".env", "w") as f:
                    f.write("OPENAI_API_KEY=\n")
                    f.write("GEMINI_API_KEY=\n")
                st.success("API 키가 초기화되었습니다.")
            except Exception as e:
                st.error(f"API 키 초기화 중 오류가 발생했습니다: {e}")
    
    st.markdown("---")
    
    # OpenAI API 키 설정
    st.subheader("OpenAI API 키")
    openai_api_key = st.text_input(
        "OpenAI API 키:", 
        value=st.session_state.openai_api_key,
        type="password"
    )
    
    if st.button("OpenAI API 키 저장"):
        st.session_state.openai_api_key = openai_api_key.strip()
        # .env 파일에 저장
        try:
            with open(".env", "w") as f:
                f.write(f"OPENAI_API_KEY={openai_api_key.strip()}\n")
                if st.session_state.gemini_api_key:
                    f.write(f"GEMINI_API_KEY={st.session_state.gemini_api_key}\n")
            st.success("OpenAI API 키가 저장되었습니다.")
        except Exception as e:
            st.error(f"API 키 저장 중 오류가 발생했습니다: {e}")
    
    st.markdown("---")
    
    # Gemini API 키 설정
    st.subheader("Google Gemini API 키")
    gemini_api_key = st.text_input(
        "Gemini API 키:", 
        value=st.session_state.gemini_api_key,
        type="password"
    )
    
    if st.button("Gemini API 키 저장"):
        st.session_state.gemini_api_key = gemini_api_key.strip()
        # .env 파일에 저장
        try:
            with open(".env", "w") as f:
                if st.session_state.openai_api_key:
                    f.write(f"OPENAI_API_KEY={st.session_state.openai_api_key}\n")
                f.write(f"GEMINI_API_KEY={gemini_api_key.strip()}\n")
            st.success("Gemini API 키가 저장되었습니다.")
            # Gemini API 초기화
            if gemini_api_key.strip():
                genai.configure(api_key=gemini_api_key.strip())
        except Exception as e:
            st.error(f"API 키 저장 중 오류가 발생했습니다: {e}")
    
    st.markdown("---")
    
    # API 키 테스트
    st.subheader("API 키 테스트")
    
    test_option = st.radio("테스트할 API 선택:", ["OpenAI", "Gemini"], horizontal=True)
    
    if st.button("API 연결 테스트"):
        if test_option == "OpenAI":
            if not st.session_state.openai_api_key:
                st.error("OpenAI API 키가 설정되지 않았습니다.")
            else:
                try:
                    with st.spinner("OpenAI API 연결 테스트 중..."):
                        client = openai.OpenAI(api_key=st.session_state.openai_api_key)
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "You are a helpful assistant."},
                                {"role": "user", "content": "Hello, can you hear me? Please respond with 'Yes, I can hear you clearly.'"}
                            ],
                            max_tokens=20
                        )
                        
                        if "I can hear you" in response.choices[0].message.content:
                            st.success("OpenAI API 연결 테스트 성공!")
                        else:
                            st.warning(f"API가 응답했지만 예상과 다릅니다: {response.choices[0].message.content}")
                except Exception as e:
                    st.error(f"OpenAI API 연결 테스트 실패: {e}")
        
        elif test_option == "Gemini":
            if not st.session_state.gemini_api_key:
                st.error("Gemini API 키가 설정되지 않았습니다.")
            else:
                try:
                    with st.spinner("Gemini API 연결 테스트 중..."):
                        model = genai.GenerativeModel('gemini-pro')
                        response = model.generate_content("Hello, can you hear me? Please respond with 'Yes, I can hear you clearly.'")
                        if "I can hear you" in response.text:
                            st.success("Gemini API 연결 테스트 성공!")
                        else:
                            st.warning(f"API가 응답했지만 예상과 다릅니다: {response.text}")
                except Exception as e:
                    st.error(f"Gemini API 연결 테스트 실패: {e}")

def admin_user_management():
    st.header("사용자 관리")
    
    tab1, tab2, tab3 = st.tabs(["사용자 등록", "사용자 목록", "계정 수정"])
    
    # 사용자 등록 탭
    with tab1:
        st.subheader("새 사용자 등록")
        
        username = st.text_input("사용자 아이디:", key="new_user_username")
        name = st.text_input("이름:", key="new_user_name")
        email = st.text_input("이메일 (선택):", key="new_user_email")
        role = st.selectbox("역할:", ["student", "teacher", "admin"], key="new_user_role")
        password = st.text_input("비밀번호:", type="password", key="new_user_password")
        confirm_password = st.text_input("비밀번호 확인:", type="password", key="new_user_confirm")
        
        if st.button("사용자 등록", key="register_new_user"):
            if not username or not name or not password:
                st.error("사용자 아이디, 이름, 비밀번호는 필수 입력사항입니다.")
            elif password != confirm_password:
                st.error("비밀번호와 비밀번호 확인이 일치하지 않습니다.")
            elif username in st.session_state.users:
                st.error(f"이미 존재하는 아이디입니다: {username}")
            elif len(password) < 6:
                st.error("비밀번호는 최소 6자 이상이어야 합니다.")
            else:
                # 사용자 등록
                success, message = register_user(
                    username, 
                    password, 
                    role, 
                    name, 
                    email, 
                    created_by=st.session_state.username
                )
                
                if success:
                    st.success(f"사용자 '{name}'이(가) 성공적으로 등록되었습니다.")
                else:
                    st.error(message)
    
    # 사용자 목록 탭
    with tab2:
        st.subheader("등록된 사용자 목록")
        
        # 표로 보여주기
        user_data_list = []
        for username, user_data_item in st.session_state.users.items():
            try:
                created_at = datetime.datetime.fromisoformat(user_data_item.get("created_at", "")).strftime("%Y-%m-%d")
            except:
                created_at = user_data_item.get("created_at", "")
            
            user_data_list.append({
                "아이디": username,
                "이름": user_data_item.get("name", ""),
                "이메일": user_data_item.get("email", ""),
                "역할": user_data_item.get("role", ""),
                "등록일": created_at,
                "등록자": user_data_item.get("created_by", "")
            })
        
        if user_data_list:
            df = pd.DataFrame(user_data_list)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("등록된 사용자가 없습니다.")
        
        # 사용자 삭제
        st.subheader("사용자 삭제")
        selected_user = st.selectbox(
            "삭제할 사용자 선택:",
            [username for username in st.session_state.users.keys() if username != st.session_state.username],
            format_func=lambda x: f"{x} ({st.session_state.users[x].get('name', '')}, {st.session_state.users[x].get('role', '')})"
        )
        
        if selected_user:
            st.warning(f"주의: 사용자 계정을 삭제하면 모든 관련 데이터가 함께 삭제됩니다.")
            st.info(f"삭제할 사용자: {selected_user} ({st.session_state.users[selected_user].get('name', '')})")
            
            confirm_delete = st.checkbox("삭제를 확인합니다")
            
            if st.button("선택한 사용자 삭제") and confirm_delete:
                # 사용자 삭제
                if selected_user in st.session_state.users:
                    selected_role = st.session_state.users[selected_user].get("role", "")
                    del st.session_state.users[selected_user]
                    
                    # 역할에 따른 추가 데이터 삭제
                    if selected_role == "student":
                        if selected_user in st.session_state.student_records:
                            del st.session_state.student_records[selected_user]
                    elif selected_role == "teacher":
                        # 교사가 출제한 문제 삭제
                        teacher_problems = {k: v for k, v in st.session_state.teacher_problems.items() 
                                           if v.get("created_by") != selected_user}
                        st.session_state.teacher_problems = teacher_problems
                    
                    save_users_data()
                    st.success(f"사용자 '{selected_user}'이(가) 삭제되었습니다.")
                    st.rerun()
    
    # 계정 수정 탭
    with tab3:
        st.subheader("계정 정보 수정")
        
        edit_user = st.selectbox(
            "수정할 사용자 선택:",
            list(st.session_state.users.keys()),
            format_func=lambda x: f"{x} ({st.session_state.users[x].get('name', '')}, {st.session_state.users[x].get('role', '')})"
        )
        
        if edit_user:
            user_data = st.session_state.users[edit_user]
            
            st.write(f"**사용자 아이디:** {edit_user}")
            
            edit_name = st.text_input("이름:", value=user_data.get("name", ""))
            edit_email = st.text_input("이메일:", value=user_data.get("email", ""))
            
            # 비밀번호 초기화
            st.subheader("비밀번호 초기화")
            new_password = st.text_input("새 비밀번호:", type="password")
            confirm_password = st.text_input("새 비밀번호 확인:", type="password")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("정보 수정"):
                    # 정보 수정
                    st.session_state.users[edit_user]["name"] = edit_name
                    st.session_state.users[edit_user]["email"] = edit_email
                    
                    save_users_data()
                    st.success("사용자 정보가 수정되었습니다.")
            
            with col2:
                if st.button("비밀번호 초기화"):
                    if not new_password or not confirm_password:
                        st.error("비밀번호와 확인을 모두 입력해주세요.")
                    elif new_password != confirm_password:
                        st.error("비밀번호와 확인이 일치하지 않습니다.")
                    elif len(new_password) < 6:
                        st.error("비밀번호는 최소 6자 이상이어야 합니다.")
                    else:
                        # 비밀번호 초기화
                        st.session_state.users[edit_user]["password"] = hash_password(new_password)
                        
                        save_users_data()
                        st.success("비밀번호가 초기화되었습니다.")

def admin_backup_restore():
    st.header("백업 및 복원")
    
    tab1, tab2 = st.tabs(["데이터 백업", "데이터 복원"])
    
    # 데이터 백업 탭
    with tab1:
        st.subheader("현재 데이터 백업")
        
        # 백업 형식 선택
        backup_format = st.radio("백업 형식 선택:", ["JSON", "CSV"])
        
        if st.button("백업 파일 생성"):
            try:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if backup_format == "JSON":
                    # JSON 백업 - API 키 제외
                    users_data = {
                        "users": st.session_state.users,
                        "teacher_problems": st.session_state.teacher_problems,
                        "student_records": st.session_state.student_records
                    }
                    # API 키 관련 데이터 제거
                    if 'openai_api_key' in users_data:
                        del users_data['openai_api_key']
                    if 'gemini_api_key' in users_data:
                        del users_data['gemini_api_key']
                    
                    json_str = json.dumps(users_data, ensure_ascii=False, indent=4)
                    
                    st.download_button(
                        label="JSON 백업 파일 다운로드",
                        data=json_str,
                        file_name=f"ai_english_backup_{timestamp}.json",
                        mime="application/json"
                    )
                
                else:
                    # CSV 백업
                    # 사용자 데이터 (API 키 제외)
                    users_df = pd.DataFrame([
                        {
                            "username": username,
                            "name": data.get("name", ""),
                            "email": data.get("email", ""),
                            "role": data.get("role", ""),
                            "password": data.get("password", ""),
                            "created_by": data.get("created_by", ""),
                            "created_at": data.get("created_at", "")
                        }
                        for username, data in st.session_state.users.items()
                    ])
                    
                    # CSV 파일들을 ZIP으로 압축
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        # 사용자 데이터 저장
                        users_csv = users_df.to_csv(index=False)
                        zip_file.writestr('users.csv', users_csv)
                        
                        # 문제 데이터 저장
                        problems_df = pd.DataFrame([
                            {
                                "key": key,
                                "category": data.get("category", ""),
                                "question": data.get("question", ""),
                                "context": data.get("context", ""),
                                "example": data.get("example", ""),
                                "level": data.get("level", ""),
                                "created_by": data.get("created_by", ""),
                                "created_at": data.get("created_at", "")
                            }
                            for key, data in st.session_state.teacher_problems.items()
                        ])
                        problems_csv = problems_df.to_csv(index=False)
                        zip_file.writestr('problems.csv', problems_csv)
                        
                        # 학생 기록 데이터 저장
                        records_data = []
                        for student_id, record in st.session_state.student_records.items():
                            for problem in record.get("solved_problems", []):
                                records_data.append({
                                    "student_id": student_id,
                                    "timestamp": problem.get("timestamp", ""),
                                    "question": problem.get("problem", {}).get("question", ""),
                                    "answer": problem.get("answer", ""),
                                    "feedback": problem.get("feedback", ""),
                                    "teacher_feedback": problem.get("teacher_feedback", ""),
                                    "score": problem.get("teacher_score", "")
                                })
                        
                        records_df = pd.DataFrame(records_data)
                        records_csv = records_df.to_csv(index=False)
                        zip_file.writestr('student_records.csv', records_csv)
                    
                    st.download_button(
                        label="CSV 백업 파일 다운로드 (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name=f"ai_english_backup_{timestamp}.zip",
                        mime="application/zip"
                    )
                
                st.success("백업 파일이 생성되었습니다. 다운로드 버튼을 클릭하여 저장하세요.")
            
            except Exception as e:
                st.error(f"백업 파일 생성 중 오류가 발생했습니다: {e}")
    
    # 데이터 복원 탭
    with tab2:
        st.subheader("백업 데이터 복원")
        
        st.warning("데이터 복원 시 현재 시스템의 모든 데이터가 백업 파일의 데이터로 대체됩니다.")
        
        # 복원 형식 선택
        restore_format = st.radio("복원 파일 형식:", ["JSON", "CSV (ZIP)"])
        
        if restore_format == "JSON":
            uploaded_file = st.file_uploader("JSON 백업 파일 업로드", type=["json"])
            
            if uploaded_file is not None:
                try:
                    backup_data = json.loads(uploaded_file.getvalue().decode("utf-8"))
                    
                    if "users" not in backup_data or "teacher_problems" not in backup_data or "student_records" not in backup_data:
                        st.error("유효하지 않은 백업 파일입니다. 필수 데이터 구조가 누락되었습니다.")
                    else:
                        st.write("백업 파일 정보:")
                        st.write(f"- 사용자 수: {len(backup_data['users'])}")
                        st.write(f"- 교사 문제 수: {len(backup_data['teacher_problems'])}")
                        st.write(f"- 학생 기록 수: {len(backup_data['student_records'])}")
                        
                        confirm_restore = st.checkbox("복원을 확인합니다. 현재 데이터가 모두 대체됩니다.")
                        
                        if st.button("데이터 복원") and confirm_restore:
                            st.session_state.users = backup_data["users"]
                            st.session_state.teacher_problems = backup_data["teacher_problems"]
                            st.session_state.student_records = backup_data["student_records"]
                            
                            save_users_data()
                            st.success("데이터가 성공적으로 복원되었습니다.")
                            st.info("변경 사항을 적용하려면 앱을 새로고침하세요.")
                
                except Exception as e:
                    st.error(f"JSON 파일 처리 중 오류가 발생했습니다: {e}")
        
        else:
            uploaded_file = st.file_uploader("ZIP 백업 파일 업로드", type=["zip"])
            
            if uploaded_file is not None:
                try:
                    zip_buffer = io.BytesIO(uploaded_file.getvalue())
                    
                    with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                        # 사용자 데이터 복원
                        users_df = pd.read_csv(zip_file.open('users.csv'))
                        
                        # 문제 데이터 복원
                        problems_df = pd.read_csv(zip_file.open('problems.csv'))
                        
                        # 학생 기록 데이터 복원
                        records_df = pd.read_csv(zip_file.open('student_records.csv'))
                        
                        st.write("백업 파일 정보:")
                        st.write(f"- 사용자 수: {len(users_df)}")
                        st.write(f"- 교사 문제 수: {len(problems_df)}")
                        st.write(f"- 학생 기록 수: {len(records_df)}")
                        
                        confirm_restore = st.checkbox("복원을 확인합니다. 현재 데이터가 모두 대체됩니다.")
                        
                        if st.button("데이터 복원") and confirm_restore:
                            # CSV 데이터를 원래 형식으로 변환
                            st.session_state.users = {
                                row['username']: {
                                    'name': row['name'],
                                    'email': row['email'],
                                    'role': row['role'],
                                    'password': row['password'],
                                    'created_by': row['created_by'],
                                    'created_at': row['created_at']
                                }
                                for _, row in users_df.iterrows()
                            }
                            
                            st.session_state.teacher_problems = {
                                row['key']: {
                                    'category': row['category'],
                                    'question': row['question'],
                                    'context': row['context'],
                                    'example': row['example'],
                                    'level': row['level'],
                                    'created_by': row['created_by'],
                                    'created_at': row['created_at']
                                }
                                for _, row in problems_df.iterrows()
                            }
                            
                            # 학생 기록 재구성
                            st.session_state.student_records = {}
                            for _, row in records_df.iterrows():
                                student_id = row['student_id']
                                if student_id not in st.session_state.student_records:
                                    st.session_state.student_records[student_id] = {
                                        'solved_problems': [],
                                        'total_problems': 0
                                    }
                                
                                st.session_state.student_records[student_id]['solved_problems'].append({
                                    'timestamp': row['timestamp'],
                                    'problem': {'question': row['question']},
                                    'answer': row['answer'],
                                    'feedback': row['feedback'],
                                    'teacher_feedback': row['teacher_feedback'],
                                    'teacher_score': row['score']
                                })
                                st.session_state.student_records[student_id]['total_problems'] += 1
                            
                            save_users_data()
                            st.success("데이터가 성공적으로 복원되었습니다.")
                            st.info("변경 사항을 적용하려면 앱을 새로고침하세요.")
                
                except Exception as e:
                    st.error(f"ZIP 파일 처리 중 오류가 발생했습니다: {e}")

def admin_system_info():
    st.header("시스템 정보")
    
    st.subheader("앱 정보")
    st.write("**앱 이름:** AI 영어 첨삭 앱")
    st.write("**버전:** 1.0.0")
    
    st.subheader("사용 통계")
    
    # 사용자 통계
    st.write(f"**총 사용자 수:** {len(st.session_state.users)}")
    
    # 역할별 사용자 수
    role_counts = {"student": 0, "teacher": 0, "admin": 0}
    for user in st.session_state.users.values():
        role = user.get("role", "")
        if role in role_counts:
            role_counts[role] += 1
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("학생 수", role_counts["student"])
    
    with col2:
        st.metric("교사 수", role_counts["teacher"])
    
    with col3:
        st.metric("관리자 수", role_counts["admin"])
    
    # 문제 통계
    st.subheader("문제 통계")
    
    total_sample_problems = len(SAMPLE_PROBLEMS)
    total_teacher_problems = len(st.session_state.teacher_problems)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("예제 문제 수", total_sample_problems)
    
    with col2:
        st.metric("교사 출제 문제 수", total_teacher_problems)
    
    # 카테고리별 문제 분포
    categories = {}
    
    # 예제 문제 카테고리
    for problem in SAMPLE_PROBLEMS.values():
        category = problem.get("category", "기타")
        if category in categories:
            categories[category] += 1
        else:
            categories[category] = 1
    
    # 교사 출제 문제 카테고리
    for problem in st.session_state.teacher_problems.values():
        category = problem.get("category", "기타")
        if category in categories:
            categories[category] += 1
        else:
            categories[category] = 1
    
    if categories:
        st.subheader("카테고리별 문제 분포")
        
        df = pd.DataFrame({
            "카테고리": list(categories.keys()),
            "문제 수": list(categories.values())
        })
        
        chart = alt.Chart(df).mark_bar().encode(
            x="문제 수:Q",
            y=alt.Y("카테고리:N", sort="-x"),
            color=alt.Color("카테고리:N", legend=None),
            tooltip=["카테고리", "문제 수"]
        ).properties(
            title="카테고리별 문제 분포"
        )
        
        st.altair_chart(chart, use_container_width=True)
    
    # 학습 통계
    st.subheader("학습 통계")
    
    total_solved = 0
    for student_data in st.session_state.student_records.values():
        total_solved += student_data.get("total_problems", 0)
    
    st.metric("총 학습 문제 수", total_solved)
    
    # 최근 활동
    st.subheader("최근 활동")
    
    recent_activities = []
    
    # 최근 등록된 사용자
    for username, user_data in st.session_state.users.items():
        if "created_at" in user_data:
            try:
                created_at = datetime.datetime.fromisoformat(user_data["created_at"])
                recent_activities.append({
                    "timestamp": created_at,
                    "activity": f"새 사용자 등록: {username} ({user_data.get('name', '')})",
                    "type": "user_registration"
                })
            except:
                pass
    
    # 최근 출제된 문제
    for problem_key, problem in st.session_state.teacher_problems.items():
        if "created_at" in problem:
            try:
                created_at = datetime.datetime.fromisoformat(problem["created_at"])
                recent_activities.append({
                    "timestamp": created_at,
                    "activity": f"새 문제 출제: {problem_key}",
                    "type": "problem_creation"
                })
            except:
                pass
    
    # 최근 학습 기록
    for student_id, student_data in st.session_state.student_records.items():
        for problem in student_data.get("solved_problems", []):
            if "timestamp" in problem:
                try:
                    timestamp = datetime.datetime.fromisoformat(problem["timestamp"])
                    student_name = st.session_state.users.get(student_id, {}).get("name", student_id)
                    recent_activities.append({
                        "timestamp": timestamp,
                        "activity": f"학습 완료: {student_name} - {problem['problem']['question'][:30]}...",
                        "type": "problem_solving"
                    })
                except:
                    pass
    
    # 최근 순으로 정렬 및 최근 10개만 표시
    recent_activities = sorted(recent_activities, key=lambda x: x["timestamp"], reverse=True)[:10]
    
    if recent_activities:
        for activity in recent_activities:
            st.write(f"**{activity['timestamp'].strftime('%Y-%m-%d %H:%M')}** - {activity['activity']}")
    else:
        st.info("최근 활동 기록이 없습니다.")

def view_teacher_problems():
    if 'teacher_problems' in st.session_state and st.session_state.teacher_problems:
        st.subheader("저장된 문제 목록")
        
        # 필터 옵션
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_school = st.selectbox("학교급 필터:", ["전체", "중학교", "고등학교"])
        with col2:
            filter_grade = st.selectbox("학년 필터:", ["전체", "1학년", "2학년", "3학년"])
        with col3:
            filter_difficulty = st.selectbox("난이도 필터:", ["전체", "상", "중", "하"])
        
        # 필터링된 문제 목록 표시
        filtered_problems = {}
        for key, problem in st.session_state.teacher_problems.items():
            if (filter_school == "전체" or problem.get("school_type") == filter_school) and \
               (filter_grade == "전체" or problem.get("grade") == filter_grade) and \
               (filter_difficulty == "전체" or problem.get("difficulty") == filter_difficulty):
                filtered_problems[key] = problem
        
        if filtered_problems:
            for key, problem in filtered_problems.items():
                with st.expander(f"{problem.get('school_type', '')} {problem.get('grade', '')} - {problem.get('topic', '')} ({problem.get('difficulty', '')})"):
                    st.text(f"작성자: {problem.get('created_by', '')}")
                    st.text(f"작성일: {problem.get('created_at', '')}")
                    st.markdown("---")
                    st.markdown(problem.get('content', ''))
                    
                    # 문제 수정/삭제 버튼
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"수정 ({key})", key=f"edit_{key}"):
                            edited_content = st.text_area(
                                "문제 내용 수정",
                                value=problem.get('content', ''),
                                height=400,
                                key=f"edit_area_{key}"
                            )
                            if st.button(f"수정 사항 저장", key=f"save_{key}"):
                                st.session_state.teacher_problems[key]['content'] = edited_content
                                save_users_data()
                                st.success("문제가 수정되었습니다.")
                                st.rerun()
                    
                    with col2:
                        if st.button(f"삭제 ({key})", key=f"delete_{key}"):
                            if key in st.session_state.teacher_problems:
                                del st.session_state.teacher_problems[key]
                                save_users_data()
                                st.success(f"문제가 삭제되었습니다.")
                                st.rerun()
        else:
            st.info("선택한 필터에 해당하는 문제가 없습니다.")
    else:
        st.info("저장된 문제가 없습니다.")

def display_and_solve_problem(problem_key, problem_data):
    """문제를 표시하고 학생이 풀 수 있도록 하는 함수"""
    st.write("**문제:**")
    st.write(problem_data["question"])
    
    st.write("**맥락:**")
    st.write(problem_data["context"])
    
    # 답변 입력
    user_answer = st.text_area("답변을 입력하세요:", height=150)
    
    if st.button("답변 제출"):
        if not user_answer.strip():
            st.error("답변을 입력해주세요.")
            return
        
        # AI 첨삭 생성
        try:
            feedback = generate_feedback(problem_data, user_answer)
            
            # 학생 기록 저장
            username = st.session_state.username
            if username not in st.session_state.student_records:
                st.session_state.student_records[username] = {
                    "solved_problems": [],
                    "total_problems": 0
                }
            
            # 문제 풀이 기록 추가
            st.session_state.student_records[username]["solved_problems"].append({
                "problem": problem_data,
                "answer": user_answer,
                "feedback": feedback,
                "timestamp": datetime.datetime.now().isoformat()
            })
            
            # 총 문제 수 증가
            st.session_state.student_records[username]["total_problems"] += 1
            
            # 데이터 저장
            save_users_data()
            
            # 결과 표시
            st.success("답변이 제출되었습니다!")
            st.markdown("### AI 첨삭 결과")
            st.markdown(feedback)
            
        except Exception as e:
            st.error(f"첨삭 생성 중 오류가 발생했습니다: {str(e)}")

def generate_feedback(problem_data, user_answer):
    """AI를 사용하여 학생의 답변에 대한 첨삭을 생성하는 함수"""
    try:
        # OpenAI API 사용 시도
        if st.session_state.openai_api_key:
            client = openai.OpenAI(api_key=st.session_state.openai_api_key)
            prompt = get_correction_prompt(problem_data, user_answer)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            return response.choices[0].message.content
        
        # Gemini API 사용 시도
        elif st.session_state.gemini_api_key:
            model = genai.GenerativeModel('gemini-pro')
            prompt = get_correction_prompt(problem_data, user_answer)
            
            response = model.generate_content(prompt)
            return response.text
        
        else:
            raise Exception("API 키가 설정되지 않았습니다.")
    
    except Exception as e:
        raise Exception(f"첨삭 생성 중 오류 발생: {str(e)}")

# Main app function
def main():
    # 로그인 확인
    if not st.session_state.logged_in:
        login_page()
    else:
        # 역할에 따른 대시보드 표시
        if st.session_state.user_role == "student":
            student_dashboard()
        elif st.session_state.user_role == "teacher":
            teacher_dashboard()
        elif st.session_state.user_role == "admin":
            admin_dashboard()
        else:
            st.error("알 수 없는 사용자 역할입니다. 관리자에게 문의하세요.")
            logout_user()

# Run the app
if __name__ == "__main__":
    main()
