import os
import json
import base64
import time
import hashlib
import re
import uuid
import random
import traceback
from datetime import datetime

# 패키지 가용성 체크
try:
    import streamlit as st
    import openai
    from passlib.hash import pbkdf2_sha256
    from dotenv import load_dotenv
    USING_PASSLIB = True
except ImportError:
    class DummySt:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    st = DummySt()
    USING_PASSLIB = False
    pbkdf2_sha256 = None

# datetime 모듈 대체 클래스 (오류 방지용)
class DummyDatetime:
    @staticmethod
    def now():
        class DummyNow:
            def isoformat(self):
                return "0000-00-00T00:00:00"
        return DummyNow()
    
    @staticmethod
    def fromisoformat(date_str):
        class DummyDate:
            def strftime(self, format_str):
                return "0000-00-00 00:00:00"
            
            def date(self):
                return "0000-00-00"
        return DummyDate()

# datetime이 없는 경우 더미로 대체
if 'datetime' not in globals():
    datetime = DummyDatetime

# 기본 모듈 import
import streamlit as st

# 선택적 모듈들
try:
    import pandas as pd
except ImportError:
    # DataFrame을 흉내내는 간단한 클래스
    class DummyDataFrame:
        def __init__(self, data=None):
            self.data = data or {}
        
        def __str__(self):
            return str(self.data)
    
    class DummyPandas:
        def DataFrame(self, data=None):
            return DummyDataFrame(data)
    
    pd = DummyPandas()

# OpenAI 관련 기능
has_openai = False
try:
    import openai
    has_openai = True
except ImportError:
    has_openai = False
    # 간단한 대체 클래스
    class DummyOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = self
            self.completions = self
        
        def create(self, *args, **kwargs):
            class DummyResponse:
                def __init__(self):
                    self.choices = [self]
                    self.message = self
                    self.content = "OpenAI API를 사용할 수 없습니다."
            return DummyResponse()
    
    # 가짜 openai 모듈 생성
    openai = type('openai', (), {'OpenAI': DummyOpenAI})

# 비밀번호 관련 기능
try:
    from passlib.hash import pbkdf2_sha256
    USING_PASSLIB = True
except ImportError:
    USING_PASSLIB = False
    pbkdf2_sha256 = None

# Initialize session state variables if they don't exist
if 'username' not in st.session_state:
    st.session_state.username = None
if 'users' not in st.session_state:
    st.session_state.users = {}
if 'teacher_problems' not in st.session_state:
    st.session_state.teacher_problems = {}
if 'student_records' not in st.session_state:
    st.session_state.student_records = {}
if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")

# Helper functions
def hash_password(password):
    """비밀번호를 해싱합니다."""
    if USING_PASSLIB and pbkdf2_sha256:
        try:
            return pbkdf2_sha256.hash(password)
        except Exception:
            # 실패하면 기본 방식 사용
            return hashlib.sha256(password.encode()).hexdigest()
    else:
        return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password, hashed_password):
    """
    비밀번호 검증 함수
    plain_password: 사용자가 입력한 비밀번호
    hashed_password: 저장된 해시된 비밀번호
    """
    try:
        # 해시된 비밀번호가 없는 경우 (예: 기본 계정)
        if not hashed_password or hashed_password == plain_password:
            return plain_password == hashed_password
            
        # pbkdf2_sha256로 해시된 비밀번호 검증
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        print(f"비밀번호 검증 오류: {str(e)}")
        # 기본 문자열 비교
        return plain_password == hashed_password

def save_users_data():
    try:
        with open("data/users.json", "w") as f:
            json.dump(st.session_state.users, f, indent=2)
    except Exception as e:
        st.error(f"사용자 데이터 저장 중 오류 발생: {str(e)}")

def load_users_data():
    try:
        with open("data/users.json", "r") as f:
            st.session_state.users = json.load(f)
    except FileNotFoundError:
        st.session_state.users = {}

def logout_user():
    st.session_state.username = None

def register_user(username, password, role, name, email="", created_by="system"):
    if username in st.session_state.users:
        return False, "이미 존재하는 아이디입니다."
    
    # 사용자 정보 저장
    st.session_state.users[username] = {
        "password": hash_password(password),
        "role": role,
        "name": name,
        "email": email,
        "created_at": datetime.now().isoformat(),
        "created_by": created_by
    }
    
    # JSON 파일에 저장
    save_users_data()
    
    return True, "사용자가 성공적으로 등록되었습니다."

# 사용자 정보 가져오기
def get_user_data():
    # 현재 로그인한 사용자의 정보를 가져오기
    username = st.session_state.username
    user_data = st.session_state.users.get(username, {})
    return username, user_data

# Teacher dashboard
def teacher_dashboard():
    st.title(f"👨‍🏫 {st.session_state.users[st.session_state.username]['name']} 선생님 대시보드")
    
    # 사이드바 메뉴
    with st.sidebar:
        st.header("메뉴")
        selected_menu = st.radio(
            "메뉴 선택:",
            ["내 정보", "학생 관리", "문제 출제", "문제 목록", "문제 저장소", "채점"],
            key="teacher_menu"
        )
        
        # 로그아웃 버튼
        if st.button("로그아웃", key="teacher_logout"):
            logout_user()
            st.rerun()
    
    # 선택된 메뉴에 따라 다른 내용 표시
    if selected_menu == "내 정보":
        teacher_my_info()
    elif selected_menu == "학생 관리":
        teacher_student_management()
    elif selected_menu == "문제 출제":
        teacher_problem_creation()
    elif selected_menu == "문제 목록":
        teacher_problem_list()
    elif selected_menu == "문제 저장소":
        teacher_problem_repository()
    elif selected_menu == "채점":
        teacher_grading()

# 교사용 문제 저장소 인터페이스
def teacher_problem_repository():
    st.header("📚 문제 저장소")
    st.info("이 페이지에서는 모든 교사들이 공유하는 문제 저장소에 접근하고 관리할 수 있습니다.")
    
    # 탭 생성
    tab1, tab2 = st.tabs(["저장소 문제 보기", "내 문제 저장소에 추가"])
    
    # 저장소 문제 보기 탭
    with tab1:
        st.subheader("저장소 문제 목록")
        
        # 필터링 옵션
        col1, col2, col3 = st.columns(3)
        with col1:
            problem_type_filter = st.selectbox(
                "문제 유형",
                ["모두", "객관식", "주관식"],
                key="repo_type_filter"
            )
        
        with col2:
            difficulty_filter = st.selectbox(
                "난이도",
                ["모두", "쉬움", "보통", "어려움"],
                key="repo_difficulty_filter"
            )
            
        with col3:
            subject_filter = st.selectbox(
                "과목",
                ["모두", "수학", "영어", "국어", "과학", "사회", "기타"],
                key="repo_subject_filter"
            )
        
        search_query = st.text_input("검색어", key="repo_search_query")
        
        # 저장소 문제 필터링
        filtered_problems = []
        
        for problem in st.session_state.problem_repository.get("problems", []):
            # 문제 유형 필터
            if problem_type_filter != "모두" and problem.get("type", "주관식") != (
                "객관식" if problem_type_filter == "객관식" else "주관식"
            ):
                continue
                
            # 난이도 필터
            if difficulty_filter != "모두" and problem.get("difficulty", "보통") != difficulty_filter:
                continue
                
            # 과목 필터
            if subject_filter != "모두" and problem.get("subject", "기타") != subject_filter:
                continue
                
            # 검색어 필터
            if search_query and search_query.lower() not in problem.get("title", "").lower() and search_query.lower() not in problem.get("content", "").lower():
                continue
                
            filtered_problems.append(problem)
        
        # 필터링된 문제 목록 표시
        if not filtered_problems:
            st.warning("조건에 맞는 문제가 없습니다.")
        else:
            st.success(f"{len(filtered_problems)}개의 문제를 찾았습니다.")
            
            for i, problem in enumerate(filtered_problems):
                with st.expander(f"{i+1}. [{problem.get('subject', '기타')}] {problem.get('title', '제목 없음')} ({problem.get('difficulty', '보통')})"):
                    st.write(f"**제목:** {problem.get('title', '제목 없음')}")
                    st.write(f"**과목:** {problem.get('subject', '기타')}")
                    st.write(f"**난이도:** {problem.get('difficulty', '보통')}")
                    st.write(f"**유형:** {problem.get('type', '주관식')}")
                    st.write(f"**등록자:** {problem.get('created_by', '알 수 없음')}")
                    st.write(f"**등록일:** {problem.get('created_at', '알 수 없음')}")
                    
                    st.markdown("---")
                    st.markdown("**문제 내용:**")
                    st.markdown(problem.get("content", "내용 없음"))
                    
                    if problem.get("type") == "객관식":
                        st.markdown("**선택지:**")
                        options = problem.get("options", [])
                        for j, option in enumerate(options):
                            st.markdown(f"{j+1}. {option}")
                        st.markdown(f"**정답:** {problem.get('answer', '정답 없음')}")
                    else:
                        if "answer" in problem:
                            st.markdown("**정답 예시:**")
                            st.markdown(problem.get("answer", "정답 없음"))
                    
                    if "explanation" in problem and problem["explanation"]:
                        st.markdown("**해설:**")
                        st.markdown(problem.get("explanation", "해설 없음"))
                    
                    # 내 문제 목록에 추가 버튼
                    if st.button(f"내 문제 목록에 추가", key=f"add_to_my_problems_{i}"):
                        # 이미 내 문제 목록에 있는지 확인
                        existing_problem = False
                        for teacher_problem in st.session_state.teacher_problems.get(st.session_state.username, []):
                            if teacher_problem.get("title") == problem.get("title") and teacher_problem.get("content") == problem.get("content"):
                                existing_problem = True
                                break
                        
                        if existing_problem:
                            st.error("이미 내 문제 목록에 있는 문제입니다.")
                        else:
                            # 교사의 문제 목록에 추가
                            if st.session_state.username not in st.session_state.teacher_problems:
                                st.session_state.teacher_problems[st.session_state.username] = []
                            
                            # 문제 복사본 생성 및 내 문제에 추가
                            new_problem = problem.copy()
                            new_problem["imported_from_repository"] = True
                            new_problem["original_author"] = problem.get("created_by", "알 수 없음")
                            new_problem["created_by"] = st.session_state.username
                            new_problem["created_at"] = datetime.now().isoformat()
                            
                            st.session_state.teacher_problems[st.session_state.username].append(new_problem)
                            
                            # 변경사항 저장
                            save_teacher_problems()
                            
                            st.success("내 문제 목록에 추가되었습니다!")
                            st.rerun()
    
    # 내 문제 저장소에 추가 탭
    with tab2:
        st.subheader("내 문제를 저장소에 추가")
        
        # 교사의 문제 목록 가져오기
        teacher_problems = st.session_state.teacher_problems.get(st.session_state.username, [])
        
        if not teacher_problems:
            st.warning("등록한 문제가 없습니다. '문제 출제' 메뉴에서 먼저 문제를 만들어주세요.")
        else:
            st.success(f"{len(teacher_problems)}개의 문제가 있습니다.")
            
            # 저장소에 추가할 문제 선택
            selected_problem_idx = st.selectbox(
                "저장소에 추가할 문제 선택:",
                range(len(teacher_problems)),
                format_func=lambda i: f"[{teacher_problems[i].get('subject', '기타')}] {teacher_problems[i].get('title', '제목 없음')}"
            )
            
            selected_problem = teacher_problems[selected_problem_idx]
            
            # 선택한 문제 정보 표시
            st.markdown("---")
            st.markdown("**선택한 문제 정보:**")
            st.markdown(f"**제목:** {selected_problem.get('title', '제목 없음')}")
            st.markdown(f"**난이도:** {selected_problem.get('difficulty', '보통')}")
            st.markdown(f"**내용:** {selected_problem.get('content', '내용 없음')}")
            
            # 저장소에 추가하기 전에 문제 정보 편집
            st.markdown("---")
            st.markdown("**저장소 등록 정보 편집:**")
            
            # 기본값은 선택한 문제의 정보를 사용
            repo_title = st.text_input("제목", value=selected_problem.get("title", ""))
            
            col1, col2 = st.columns(2)
            with col1:
                repo_difficulty = st.selectbox(
                    "난이도",
                    ["쉬움", "보통", "어려움"],
                    index=["쉬움", "보통", "어려움"].index(selected_problem.get("difficulty", "보통"))
                )
            
            with col2:
                repo_subject = st.selectbox(
                    "과목",
                    ["수학", "영어", "국어", "과학", "사회", "기타"],
                    index=["수학", "영어", "국어", "과학", "사회", "기타"].index(selected_problem.get("subject", "기타")) 
                    if selected_problem.get("subject") in ["수학", "영어", "국어", "과학", "사회", "기타"] else 5
                )
            
            repo_content = st.text_area("문제 내용", value=selected_problem.get("content", ""))
            
            # 문제 유형에 따라 다른 필드 표시
            if selected_problem.get("type") == "객관식":
                # 객관식 문제일 경우
                st.markdown("**선택지:**")
                repo_options = []
                
                for i, option in enumerate(selected_problem.get("options", [])):
                    repo_options.append(st.text_input(f"선택지 {i+1}", value=option, key=f"repo_option_{i}"))
                
                repo_answer = st.text_input("정답", value=selected_problem.get("answer", ""))
            else:
                # 주관식 문제일 경우
                repo_answer = st.text_area("정답 예시", value=selected_problem.get("answer", ""))
            
            repo_explanation = st.text_area("문제 해설", value=selected_problem.get("explanation", ""))
            
            # 저장소에 추가 버튼
            if st.button("저장소에 문제 추가", type="primary"):
                if not repo_title:
                    st.error("제목을 입력해주세요.")
                elif not repo_content:
                    st.error("문제 내용을 입력해주세요.")
                else:
                    # 저장소에 추가할 문제 생성
                    repo_problem = {
                        "id": str(uuid.uuid4()),
                        "title": repo_title,
                        "content": repo_content,
                        "difficulty": repo_difficulty,
                        "subject": repo_subject,
                        "type": selected_problem.get("type", "주관식"),
                        "created_by": st.session_state.username,
                        "created_at": datetime.now().isoformat(),
                        "explanation": repo_explanation
                    }
                    
                    # 문제 유형에 따라 다른 필드 추가
                    if selected_problem.get("type") == "객관식":
                        repo_problem["options"] = [opt for opt in repo_options if opt]
                        repo_problem["answer"] = repo_answer
                    else:
                        repo_problem["answer"] = repo_answer
                    
                    # 저장소에 문제 추가
                    st.session_state.problem_repository["problems"].append(repo_problem)
                    
                    # 저장소 저장
                    save_problem_repository()
                    
                    st.success("문제가 저장소에 성공적으로 추가되었습니다!")
                    time.sleep(2)
                    st.rerun()

def teacher_my_info():
    username, user_data = get_user_data()
    st.header("내 정보")
    
    # 정보 표시
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("기본 정보")
        st.write(f"**이름:** {user_data.get('name', '')}")
        st.write(f"**아이디:** {st.session_state.username}")
        st.write(f"**이메일:** {user_data.get('email', '')}")
    
    with col2:
        st.subheader("통계")
        
        # 출제한 문제 수
        problem_count = len(st.session_state.teacher_problems.get(st.session_state.username, []))
        
        # 등록한 학생 수
        student_count = sum(1 for student in st.session_state.users.values()
                           if student.get("role") == "student" and student.get("created_by") == username)
        
        # 채점한 답변 수
        graded_count = 0
        for student_id, student_record in st.session_state.student_records.items():
            for problem in student_record.get("solved_problems", []):
                if problem.get("graded_by") == username:
                    graded_count += 1
        
        st.write(f"**출제한 문제 수:** {problem_count}")
        st.write(f"**등록한 학생 수:** {student_count}")
        st.write(f"**채점한 답변 수:** {graded_count}")
    
    # 비밀번호 변경
    st.markdown("---")
    st.subheader("비밀번호 변경")
    
    col1, col2 = st.columns(2)
    
    with col1:
        current_password = st.text_input("현재 비밀번호", type="password")
    
    with col2:
        new_password = st.text_input("새 비밀번호", type="password")
        confirm_password = st.text_input("새 비밀번호 확인", type="password")
    
    if st.button("비밀번호 변경"):
        if not current_password or not new_password or not confirm_password:
            st.error("모든 필드를 입력해야 합니다.")
        elif new_password != confirm_password:
            st.error("새 비밀번호와 확인이 일치하지 않습니다.")
        elif len(new_password) < 6:
            st.error("비밀번호는 최소 6자 이상이어야 합니다.")
        elif not verify_password(current_password, user_data.get("password", "")):
            st.error("현재 비밀번호가 일치하지 않습니다.")
        else:
            # 비밀번호 변경
            st.session_state.users[st.session_state.username]["password"] = hash_password(new_password)
            save_users_data()
            st.success("비밀번호가 성공적으로 변경되었습니다.")

def student_problem_solving():
    st.header("문제 풀기")
    
    # 교사가 출제한 모든 문제 목록 가져오기
    all_problems = st.session_state.teacher_problems
    
    if not all_problems:
        st.info("현재 풀 수 있는 문제가 없습니다. 나중에 다시 확인해주세요.")
        return
    
    # 학생 기록 불러오기
    student_records = st.session_state.student_records.get(st.session_state.username, {})
    solved_problems = student_records.get("problems", {})
    
    # 문제 필터링 옵션
    st.subheader("문제 필터링")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        filter_status = st.selectbox(
            "상태:",
            ["모두", "미시도", "진행 중", "완료"]
        )
    
    with col2:
        # 교사 목록 생성
        teacher_ids = list(set(problem.get("created_by", "") for problem in all_problems.values()))
        teacher_names = {teacher_id: st.session_state.users.get(teacher_id, {}).get("name", teacher_id) 
                        for teacher_id in teacher_ids}
        
        filter_teacher = st.selectbox(
            "교사:",
            ["모두"] + [f"{name} ({tid})" for tid, name in teacher_names.items()]
        )
    
    with col3:
        filter_difficulty = st.selectbox(
            "난이도:",
            ["모두", "쉬움", "중간", "어려움"]
        )
    
    with col4:
        filter_type = st.selectbox(
            "문제 유형:",
            ["모두", "객관식", "주관식"]
        )
    
    # 추가 필터링 옵션 (펼침 상자로 제공)
    with st.expander("추가 필터 옵션"):
        school_types = list(set(problem.get("school_type", "") for problem in all_problems.values() if "school_type" in problem))
        if school_types:
            filter_school = st.selectbox("학교 구분:", ["모두"] + school_types)
        else:
            filter_school = "모두"
            
        grades = list(set(problem.get("grade", "") for problem in all_problems.values() if "grade" in problem))
        if grades:
            filter_grade = st.selectbox("학년:", ["모두"] + grades)
        else:
            filter_grade = "모두"
            
        topics = list(set(problem.get("topic_category", "") for problem in all_problems.values() if "topic_category" in problem))
        if topics:
            filter_topic = st.selectbox("주제:", ["모두"] + topics)
        else:
            filter_topic = "모두"
    
    # 필터링 적용
    filtered_problems = {}
    
    for p_id, problem in all_problems.items():
        # 상태 필터링
        if filter_status != "모두":
            if p_id not in solved_problems:
                if filter_status != "미시도":
                    continue
            elif solved_problems[p_id].get("status") == "in_progress":
                if filter_status != "진행 중":
                    continue
            elif solved_problems[p_id].get("status") == "completed":
                if filter_status != "완료":
                    continue
        
        # 교사 필터링
        if filter_teacher != "모두":
            teacher_id = filter_teacher.split(" (")[-1][:-1]  # 교사 ID 추출
            if problem.get("created_by") != teacher_id:
                continue
        
        # 난이도 필터링
        if filter_difficulty != "모두" and problem.get("difficulty") != filter_difficulty:
            continue
            
        # 문제 유형 필터링
        if filter_type != "모두":
            problem_type = problem.get("problem_type", "essay")  # 기본값은 주관식
            if (filter_type == "객관식" and problem_type != "multiple_choice") or \
               (filter_type == "주관식" and problem_type == "multiple_choice"):
                continue
        
        # 학교 구분 필터링
        if filter_school != "모두" and problem.get("school_type") != filter_school:
            continue
            
        # 학년 필터링
        if filter_grade != "모두" and problem.get("grade") != filter_grade:
            continue
            
        # 주제 필터링
        if filter_topic != "모두" and problem.get("topic_category") != filter_topic:
            continue
        
        filtered_problems[p_id] = problem
    
    # 필터링된 문제 목록 표시
    st.subheader("문제 목록")
    
    if not filtered_problems:
        st.info("필터 조건에 맞는 문제가 없습니다.")
        return
    
    # 문제 선택 목록
    problem_options = []
    for p_id, problem in filtered_problems.items():
        teacher_name = st.session_state.users.get(problem.get("created_by", ""), {}).get("name", "알 수 없음")
        
        # 문제 상태 확인
        status = "미시도"
        score = ""
        if p_id in solved_problems:
            if solved_problems[p_id].get("status") == "in_progress":
                status = "진행 중"
            elif solved_problems[p_id].get("status") == "completed":
                status = "완료"
                score = f" (점수: {solved_problems[p_id].get('score', 0)})"
        
        # 문제 유형 아이콘
        type_icon = "🔤" if problem.get("problem_type") == "multiple_choice" else "📝"
        
        # 학교/학년 정보
        school_grade = ""
        if "school_type" in problem and "grade" in problem:
            school_grade = f" - {problem.get('school_type')} {problem.get('grade')}학년"
        
        # 문제 옵션 생성
        problem_options.append(
            f"{type_icon} {problem.get('title')} - {teacher_name}{school_grade} - {problem.get('difficulty', '중간')} [{status}{score}]"
        )
    
    selected_problem_idx = st.selectbox(
        "문제 선택:",
        range(len(problem_options)),
        format_func=lambda x: problem_options[x]
    )
    
    selected_problem_id = list(filtered_problems.keys())[selected_problem_idx]
    selected_problem = filtered_problems[selected_problem_id]
    
    # 선택한 문제 미리보기
    with st.expander("문제 미리보기", expanded=False):
        st.subheader(selected_problem.get("title", ""))
        
        # 문제 타입에 따라 미리보기 형식 변경
        if selected_problem.get("problem_type") == "multiple_choice":
            st.markdown("**문제 유형:** 객관식")
        else:
            st.markdown("**문제 유형:** 주관식")
            
        st.markdown(f"**난이도:** {selected_problem.get('difficulty', '중간')}")
        st.markdown(f"**예상 시간:** {selected_problem.get('expected_time', 10)}분")
        if "topic_category" in selected_problem:
            st.markdown(f"**주제:** {selected_problem.get('topic_category', '')}")
            
        # 내용 일부만 표시
        description = selected_problem.get("description", "")
        if len(description) > 200:
            st.markdown(f"**내용:** {description[:200]}...")
        else:
            st.markdown(f"**내용:** {description}")
    
    # 선택한 문제 풀기 버튼
    if st.button("선택한 문제 풀기"):
        # 문제 풀기 페이지로 전환
        st.session_state.problem_solving_id = selected_problem_id
        st.rerun()

def student_records_view():
    st.header("내 학습 기록")
    
    # 학생 기록 불러오기
    student_records = st.session_state.student_records.get(st.session_state.username, {})
    solved_problems = student_records.get("problems", {})
    
    if not solved_problems:
        st.info("아직 풀었던 문제가 없습니다.")
        return
    
    # 통계 요약
    st.subheader("학습 통계 요약")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        problems_attempted = len(solved_problems)
        st.metric("시도한 문제 수", problems_attempted)
    
    with col2:
        problems_completed = sum(1 for problem in solved_problems.values() 
                               if problem.get("status") == "completed")
        st.metric("완료한 문제 수", problems_completed)
    
    with col3:
        # 평균 점수 계산
        total_score = sum(problem.get("score", 0) for problem in solved_problems.values() 
                         if problem.get("status") == "completed")
        
        if problems_completed > 0:
            average_score = total_score / problems_completed
        else:
            average_score = 0
        
        st.metric("평균 점수", f"{average_score:.1f}")
    
    # 기록 자세히 보기
    st.subheader("문제 기록 자세히 보기")
    
    tab1, tab2 = st.tabs(["완료한 문제", "진행 중인 문제"])
    
    # 완료한 문제 탭
    with tab1:
        completed_problems = {p_id: problem for p_id, problem in solved_problems.items() 
                             if problem.get("status") == "completed"}
        
        if not completed_problems:
            st.info("아직 완료한 문제가 없습니다.")
        else:
            for p_id, problem_record in completed_problems.items():
                problem_data = st.session_state.teacher_problems.get(p_id, {})
                teacher_name = st.session_state.users.get(problem_data.get("created_by", ""), {}).get("name", "알 수 없음")
                
                with st.expander(f"{problem_data.get('title', '제목 없음')} - 점수: {problem_record.get('score', 0)}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**출제자:** {teacher_name}")
                        st.write(f"**난이도:** {problem_data.get('difficulty', '중간')}")
                        
                        # 완료 시간 형식화
                        completed_at = problem_record.get("completed_at", "")
                        try:
                            completed_at = datetime.fromisoformat(completed_at).strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            pass
                        
                        st.write(f"**완료 시간:** {completed_at}")
                    
                    with col2:
                        st.write(f"**점수:** {problem_record.get('score', 0)}")
                        st.write(f"**피드백:** {problem_record.get('feedback', '피드백 없음')}")
                    
                    st.markdown("---")
                    st.write("**문제:**")
                    st.write(problem_data.get("description", "내용 없음"))
                    
                    st.write("**나의 답변:**")
                    st.write(problem_record.get("answer", "답변 없음"))
    
    # 진행 중인 문제 탭
    with tab2:
        in_progress_problems = {p_id: problem for p_id, problem in solved_problems.items() 
                               if problem.get("status") == "in_progress"}
        
        if not in_progress_problems:
            st.info("현재 진행 중인 문제가 없습니다.")
        else:
            for p_id, problem_record in in_progress_problems.items():
                problem_data = st.session_state.teacher_problems.get(p_id, {})
                teacher_name = st.session_state.users.get(problem_data.get("created_by", ""), {}).get("name", "알 수 없음")
                
                with st.expander(f"{problem_data.get('title', '제목 없음')} - 진행 중"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**출제자:** {teacher_name}")
                        st.write(f"**난이도:** {problem_data.get('difficulty', '중간')}")
                    
                    with col2:
                        # 시작 시간 형식화
                        started_at = problem_record.get("started_at", "")
                        try:
                            started_at = datetime.fromisoformat(started_at).strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            pass
                        
                        st.write(f"**시작 시간:** {started_at}")
                    
                    st.markdown("---")
                    st.write("**문제:**")
                    st.write(problem_data.get("description", "내용 없음"))
                    
                    # 계속 풀기 버튼
                    if st.button(f"계속 풀기 - {problem_data.get('title', '제목 없음')}", key=f"continue_{p_id}"):
                        st.session_state.problem_solving_id = p_id
                        st.rerun()

def display_and_solve_problem():
    st.header("문제 풀기")
    
    if "problem_solving_id" not in st.session_state:
        st.error("문제를 찾을 수 없습니다.")
        if st.button("문제 목록으로 돌아가기"):
            st.rerun()
        return
    
    problem_id = st.session_state.problem_solving_id
    
    # 문제 데이터 가져오기
    problem_data = st.session_state.teacher_problems.get(problem_id)
    
    if not problem_data:
        st.error("선택한 문제를 찾을 수 없습니다.")
        if st.button("문제 목록으로 돌아가기"):
            st.session_state.pop("problem_solving_id", None)
            st.rerun()
        return
    
    # 학생 기록 초기화 또는 업데이트
    if st.session_state.username not in st.session_state.student_records:
        st.session_state.student_records[st.session_state.username] = {"problems": {}}
    
    student_records = st.session_state.student_records[st.session_state.username]
    
    if "problems" not in student_records:
        student_records["problems"] = {}
    
    # 해당 문제에 대한 학생 기록이 없으면 초기화
    if problem_id not in student_records["problems"]:
        student_records["problems"][problem_id] = {
            "status": "in_progress",
            "started_at": datetime.now().isoformat(),
            "answer": "",
            "score": 0
        }
    
    problem_record = student_records["problems"][problem_id]
    is_completed = problem_record.get("status") == "completed"
    
    # 문제 정보 표시
    st.subheader(problem_data.get("title", "제목 없음"))
    
    # 교사 및 난이도 정보
    teacher_name = st.session_state.users.get(problem_data.get("created_by", ""), {}).get("name", "알 수 없음")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**출제자:** {teacher_name}")
    with col2:
        st.write(f"**난이도:** {problem_data.get('difficulty', '중간')}")
    with col3:
        if is_completed:
            st.write(f"**점수:** {problem_record.get('score', 0)}")
        else:
            st.write(f"**예상 시간:** {problem_data.get('expected_time', 10)}분")
    
    # 학교/학년 정보가 있으면 표시
    if "school_type" in problem_data and "grade" in problem_data:
        st.write(f"**대상:** {problem_data.get('school_type')} {problem_data.get('grade')}학년")
    
    # 주제 정보가 있으면 표시
    if "topic_category" in problem_data:
        st.write(f"**주제:** {problem_data.get('topic_category')}")
    
    # 구분선
    st.markdown("---")
    
    # 문제 내용 표시
    st.markdown("### 문제")
    st.markdown(problem_data.get("description", ""))
    
    # 구분선
    st.markdown("---")
    
    # 문제 유형에 따라 다른 UI 표시
    problem_type = problem_data.get("problem_type", "essay")  # 기본값은 주관식
    
    if is_completed:
        # 완료된 문제인 경우 결과 표시
        st.markdown("### 나의 답변")
        
        if problem_type == "multiple_choice":
            # 객관식 문제
            options = problem_data.get("options", [])
            correct_answer = problem_data.get("correct_answer", 0)
            student_answer = int(problem_record.get("answer", "0"))
            
            for i, option_text in enumerate(options, 1):
                if i == correct_answer and i == student_answer:
                    st.success(f"{i}. {option_text} ✓ (내 선택, 정답)")
                elif i == correct_answer:
                    st.success(f"{i}. {option_text} ✓ (정답)")
                elif i == student_answer:
                    st.error(f"{i}. {option_text} ✗ (내 선택)")
                else:
                    st.write(f"{i}. {option_text}")
            
            # 해설 표시
            if "explanation" in problem_data:
                st.markdown("### 해설")
                st.markdown(problem_data.get("explanation", ""))
            
        else:
            # 주관식 문제
            st.write(problem_record.get("answer", ""))
        
        # 피드백 표시
        if "feedback" in problem_record:
            st.markdown("### 피드백")
            st.markdown(problem_record.get("feedback", ""))
            
            # 샘플 답안이 있으면 표시
            if "sample_answer" in problem_data:
                st.markdown("### 예시 답안")
                st.markdown(problem_data.get("sample_answer", ""))
    
    else:
        # 진행 중인 문제
        st.markdown("### 답변 작성")
        
        answer = problem_record.get("answer", "")
        
        if problem_type == "multiple_choice":
            # 객관식 문제 UI
            options = problem_data.get("options", [])
            selected_option = 0
            
            try:
                selected_option = int(answer) if answer else 0
            except ValueError:
                selected_option = 0
                
            # 라디오 버튼으로 보기 선택
            option_radio = st.radio(
                "답변 선택:",
                range(1, len(options) + 1),
                format_func=lambda i: f"{i}. {options[i-1]}",
                index=selected_option - 1 if 0 < selected_option <= len(options) else 0
            )
            
            # 임시 저장 및 제출 버튼
            col1, col2 = st.columns(2)
            with col1:
                if st.button("임시 저장"):
                    problem_record["answer"] = str(option_radio)
                    problem_record["updated_at"] = datetime.now().isoformat()
                    
                    with open("student_records.json", "w") as f:
                        json.dump(st.session_state.student_records, f)
                    
                    st.success("답변이 임시 저장되었습니다.")
            
            with col2:
                submit_button = st.button("답변 제출")
                if submit_button:
                    if not option_radio:
                        st.error("답변을 선택해주세요.")
                    else:
                        # 자동 채점
                        correct_answer = problem_data.get("correct_answer", 0)
                        score = 100 if option_radio == correct_answer else 0
                        
                        # 학생 기록 업데이트
                        problem_record["answer"] = str(option_radio)
                        problem_record["score"] = score
                        problem_record["completed_at"] = datetime.now().isoformat()
                        problem_record["status"] = "completed"
                        problem_record["feedback"] = f"{'정답입니다! 🎉' if score == 100 else '아쉽게도 오답입니다. 😢'}"
                        
                        if "explanation" in problem_data:
                            problem_record["feedback"] += f"\n\n{problem_data.get('explanation', '')}"
                        
                        with open("student_records.json", "w") as f:
                            json.dump(st.session_state.student_records, f)
                        
                        st.success("답변이 제출되었습니다.")
                        time.sleep(1)
                        st.rerun()
        
        else:
            # 주관식 문제 UI
            answer_text = st.text_area("답변:", value=answer, height=200)
            
            # 글자 수 표시
            st.write(f"글자 수: {len(answer_text)} 자")
            
            # 임시 저장 및 제출 버튼
            col1, col2 = st.columns(2)
            with col1:
                if st.button("임시 저장"):
                    problem_record["answer"] = answer_text
                    problem_record["updated_at"] = datetime.now().isoformat()
                    
                    with open("student_records.json", "w") as f:
                        json.dump(st.session_state.student_records, f)
                    
                    st.success("답변이 임시 저장되었습니다.")
            
            with col2:
                submit_button = st.button("답변 제출")
                if submit_button:
                    if not answer_text.strip():
                        st.error("답변을 작성해주세요.")
                    else:
                        # 학생 기록 업데이트
                        problem_record["answer"] = answer_text
                        problem_record["submitted_at"] = datetime.now().isoformat()
                        problem_record["status"] = "submitted"
                        
                        with open("student_records.json", "w") as f:
                            json.dump(st.session_state.student_records, f)
                        
                        st.success("답변이 제출되었습니다. 교사의 채점을 기다려주세요.")
                        
                        # 3초 후 문제 목록으로 돌아가기
                        time.sleep(3)
                        st.session_state.pop("problem_solving_id", None)
                        st.rerun()
    
    if st.button("취소하고 돌아가기"):
        st.session_state.pop("problem_solving_id", None)
        st.rerun()

# 객관식 문제 파싱 함수
def parse_multiple_choice_problems(content):
    problems = []
    problem_blocks = re.split(r'문제\s*\d+:', content)
    
    for block in problem_blocks:
        if not block.strip():
            continue
        
        problem = {}
        
        # 제목 추출
        title_match = re.search(r'제목:\s*(.*?)(?:\n|$)', block)
        if title_match:
            problem['title'] = title_match.group(1).strip()
        
        # 내용 추출
        desc_match = re.search(r'내용:\s*(.*?)(?:\n보기1:|$)', block, re.DOTALL)
        if desc_match:
            problem['description'] = desc_match.group(1).strip()
        
        # 보기 추출
        options = []
        for i in range(1, 5):
            option_match = re.search(fr'보기{i}:\s*(.*?)(?:\n|$)', block)
            if option_match:
                options.append(option_match.group(1).strip())
        
        if options:
            problem['options'] = options
        
        # 정답 추출
        answer_match = re.search(r'정답:\s*(\d+)', block)
        if answer_match:
            problem['correct_answer'] = int(answer_match.group(1))
        
        # 해설 추출
        explanation_match = re.search(r'해설:\s*(.*?)(?:\n예상 시간:|$)', block, re.DOTALL)
        if explanation_match:
            problem['explanation'] = explanation_match.group(1).strip()
        
        # 예상 시간 추출
        time_match = re.search(r'예상 시간:\s*(\d+)', block)
        if time_match:
            problem['expected_time'] = int(time_match.group(1))
        
        # 최소한의 정보가 있으면 추가
        if 'title' in problem and 'description' in problem:
            problems.append(problem)
    
    return problems

# 주관식 문제 파싱 함수
def parse_essay_problems(content):
    problems = []
    problem_blocks = re.split(r'문제\s*\d+:', content)
    
    for block in problem_blocks:
        if not block.strip():
            continue
        
        problem = {}
        
        # 제목 추출
        title_match = re.search(r'제목:\s*(.*?)(?:\n|$)', block)
        if title_match:
            problem['title'] = title_match.group(1).strip()
        
        # 내용 추출
        desc_match = re.search(r'내용:\s*(.*?)(?:\n예시 답안:|$)', block, re.DOTALL)
        if desc_match:
            problem['description'] = desc_match.group(1).strip()
        
        # 예시 답안 추출
        sample_match = re.search(r'예시 답안:\s*(.*?)(?:\n채점 기준:|$)', block, re.DOTALL)
        if sample_match:
            problem['sample_answer'] = sample_match.group(1).strip()
        
        # 채점 기준 추출
        criteria_match = re.search(r'채점 기준:\s*(.*?)(?:\n예상 시간:|$)', block, re.DOTALL)
        if criteria_match:
            problem['grading_criteria'] = criteria_match.group(1).strip()
        
        # 예상 시간 추출
        time_match = re.search(r'예상 시간:\s*(\d+)', block)
        if time_match:
            problem['expected_time'] = int(time_match.group(1))
        
        # 최소한의 정보가 있으면 추가
        if 'title' in problem and 'description' in problem:
            problems.append(problem)
    
    return problems

# 설정 파일 및 환경 변수에서 API 키 로드
def load_api_keys():
    # 기본 API 키 (하드코딩된 옵션) - 실제 배포 시 빈 문자열로 변경하세요
    DEFAULT_OPENAI_API_KEY = "your_default_openai_key_here"  # 개발용 기본 키 (실제 사용 시 변경 필요)
    
    # 이미 세션에 키가 있는 경우 그대로 사용
    if 'openai_api_key' not in st.session_state:
        # 다양한 소스에서 API 키 로드 시도
        openai_key = None
        
        # 1. 환경 변수에서 로드
        openai_key = os.getenv("OPENAI_API_KEY")
        
        # 2. .env 파일에서 로드 시도
        if not openai_key and is_package_available("dotenv"):
            try:
                from dotenv import load_dotenv
                load_dotenv()
                openai_key = os.getenv("OPENAI_API_KEY")
            except Exception:
                pass
        
        # 3. config.json 파일에서 로드 시도
        if not openai_key:
            try:
                if os.path.exists("config.json"):
                    with open("config.json", "r") as f:
                        config = json.load(f)
                        openai_key = config.get("openai_api_key")
            except Exception:
                pass
        
        # 4. API 키가 여전히 없으면 기본값 사용
        if not openai_key:
            openai_key = DEFAULT_OPENAI_API_KEY
        
        st.session_state.openai_api_key = openai_key
    
    # OpenAI 클라이언트 초기화 (openai 라이브러리가 있는 경우)
    if has_openai and st.session_state.openai_api_key:
        try:
            st.session_state.openai_client = openai.OpenAI(api_key=st.session_state.openai_api_key)
        except Exception:
            # 초기화 실패 시 클라이언트는 None으로 설정
            st.session_state.openai_client = None

# 문제 저장소 로드 함수
def load_problem_repository():
    try:
        with open("data/problem_repository.json", "r") as f:
            st.session_state.problem_repository = json.load(f)
    except FileNotFoundError:
        # 저장소 파일이 없으면 빈 저장소 생성
        st.session_state.problem_repository = {
            "problems": [],
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "version": "1.0"
            }
        }
        # 빈 저장소 파일 생성
        save_problem_repository()

# 문제 저장소 저장 함수
def save_problem_repository():
    # 마지막 업데이트 시간 갱신
    st.session_state.problem_repository["metadata"]["last_updated"] = datetime.now().isoformat()
    
    try:
        with open("data/problem_repository.json", "w") as f:
            json.dump(st.session_state.problem_repository, f, indent=2)
    except Exception as e:
        st.error(f"문제 저장소 저장 중 오류 발생: {str(e)}")

def student_dashboard():
    st.title(f"👨‍🎓 {st.session_state.users[st.session_state.username]['name']} 학생 대시보드")
    
    # 첫 로그인 확인
    first_login = st.session_state.users[st.session_state.username].get("first_login", True)
    
    # 사이드바 메뉴
    with st.sidebar:
        st.header("메뉴")
        options = ["내 정보", "문제 풀기", "내 기록", "문제 저장소"]
        
        if "student_menu" not in st.session_state:
            # 첫 로그인 시 기본 메뉴를 '문제 풀기'로 설정
            st.session_state.student_menu = "문제 풀기" if first_login else "내 정보"
        
        selected_menu = st.radio(
            "메뉴 선택:",
            options,
            index=options.index(st.session_state.student_menu)
        )
        
        # 메뉴 상태 저장
        st.session_state.student_menu = selected_menu
        
        # 로그아웃 버튼
        if st.button("로그아웃", key="student_logout"):
            logout_user()
            st.rerun()
    
    # 선택된 메뉴에 따라 다른 내용 표시
    if selected_menu == "내 정보":
        student_my_info()
    elif selected_menu == "문제 풀기":
        # 문제 풀기 모드인 경우
        if st.session_state.get("problem_solving_id"):
            display_and_solve_problem()
        else:
            student_problem_solving()
    elif selected_menu == "내 기록":
        student_records_view()
    elif selected_menu == "문제 저장소":
        student_problem_repository_view()
    
    # 첫 로그인 플래그 업데이트
    if first_login:
        st.session_state.users[st.session_state.username]["first_login"] = False
        save_users_data()

# 학생용 문제 저장소 뷰 인터페이스
def student_problem_repository_view():
    st.header("📚 문제 저장소")
    st.info("이 페이지에서는 교사들이 공유한 모든 문제를 검색하고 풀 수 있습니다.")
    
    # 필터링 옵션
    st.subheader("문제 검색")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        problem_type_filter = st.selectbox(
            "문제 유형",
            ["모두", "객관식", "주관식"],
            key="student_repo_type_filter"
        )
    
    with col2:
        difficulty_filter = st.selectbox(
            "난이도",
            ["모두", "쉬움", "보통", "어려움"],
            key="student_repo_difficulty_filter"
        )
        
    with col3:
        subject_filter = st.selectbox(
            "과목",
            ["모두", "수학", "영어", "국어", "과학", "사회", "기타"],
            key="student_repo_subject_filter"
        )
    
    search_query = st.text_input("검색어", key="student_repo_search_query")
    
    # 저장소 문제 필터링
    filtered_problems = []
    
    for problem in st.session_state.problem_repository.get("problems", []):
        # 문제 유형 필터
        if problem_type_filter != "모두" and problem.get("type", "주관식") != (
            "객관식" if problem_type_filter == "객관식" else "주관식"
        ):
            continue
            
        # 난이도 필터
        if difficulty_filter != "모두" and problem.get("difficulty", "보통") != difficulty_filter:
            continue
            
        # 과목 필터
        if subject_filter != "모두" and problem.get("subject", "기타") != subject_filter:
            continue
            
        # 검색어 필터
        if search_query and search_query.lower() not in problem.get("title", "").lower() and search_query.lower() not in problem.get("content", "").lower():
            continue
            
        filtered_problems.append(problem)
    
    # 필터링된 문제 목록 표시
    if not filtered_problems:
        st.warning("조건에 맞는 문제가 없습니다.")
    else:
        st.success(f"{len(filtered_problems)}개의 문제를 찾았습니다.")
        
        for i, problem in enumerate(filtered_problems):
            author_name = st.session_state.users.get(problem.get("created_by", ""), {}).get("name", "알 수 없음")
            
            with st.expander(f"{i+1}. [{problem.get('subject', '기타')}] {problem.get('title', '제목 없음')} ({problem.get('difficulty', '보통')})"):
                st.write(f"**제목:** {problem.get('title', '제목 없음')}")
                st.write(f"**과목:** {problem.get('subject', '기타')}")
                st.write(f"**난이도:** {problem.get('difficulty', '보통')}")
                st.write(f"**유형:** {problem.get('type', '주관식')}")
                st.write(f"**출제자:** {author_name}")
                
                st.markdown("---")
                st.markdown("**문제 내용:**")
                st.markdown(problem.get("content", "내용 없음"))
                
                # 문제 풀기 버튼
                repo_problem_id = problem.get("id")
                if repo_problem_id and st.button(f"이 문제 풀기", key=f"solve_repo_problem_{i}"):
                    # 임시 문제 ID 생성 (충돌 방지)
                    temp_problem_id = f"repo_{repo_problem_id}"
                    
                    # 문제가 이미 교사 문제 목록에 없으면 추가
                    if temp_problem_id not in st.session_state.teacher_problems:
                        # 저장소 문제를 교사 문제 형식으로 변환
                        teacher_problem = {
                            "id": temp_problem_id,
                            "title": problem.get("title", ""),
                            "description": problem.get("content", ""),
                            "difficulty": problem.get("difficulty", "보통"),
                            "created_by": problem.get("created_by", "system"),
                            "created_at": datetime.now().isoformat(),
                            "problem_type": "multiple_choice" if problem.get("type") == "객관식" else "essay",
                            "subject": problem.get("subject", "기타"),
                            "from_repository": True
                        }
                        
                        # 문제 유형에 따라 추가 필드 추가
                        if problem.get("type") == "객관식":
                            teacher_problem["options"] = problem.get("options", [])
                            teacher_problem["correct_answer"] = problem.get("answer", "")
                        else:
                            teacher_problem["answer"] = problem.get("answer", "")
                            
                        if "explanation" in problem:
                            teacher_problem["explanation"] = problem.get("explanation", "")
                        
                        # 교사 문제 목록에 추가
                        st.session_state.teacher_problems[temp_problem_id] = teacher_problem
                    
                    # 문제 풀기 페이지로 전환
                    st.session_state.problem_solving_id = temp_problem_id
                    st.rerun()

def teacher_problem_creation():
    st.header("문제 출제")
    
    # 문제 출제 방식 선택
    problem_creation_method = st.radio(
        "문제 출제 방식 선택:",
        ["직접 문제 출제", "CSV 파일 업로드", "AI 문제 자동 생성"]
    )
    
    if problem_creation_method == "CSV 파일 업로드":
        st.subheader("CSV 파일로 문제 업로드")
        
        # CSV 파일 형식 안내
        with st.expander("CSV 파일 형식 안내", expanded=False):
            st.markdown("""
            ### CSV 파일 형식 안내
            
            CSV 파일은 다음 필드를 포함해야 합니다:
            - **title**: 문제 제목
            - **description**: 문제 내용
            - **difficulty**: 난이도 (쉬움, 보통, 어려움)
            - **expected_time**: 예상 풀이 시간(분)
            - **type**: 문제 유형 (객관식, 주관식, 서술식)
            
            객관식일 경우 추가 필드:
            - **options**: 선택지 (쉼표로 구분)
            - **correct_answer**: 정답 번호 (1부터 시작)
            
            서술식/주관식일 경우 추가 필드:
            - **answer**: 예시 답안
            - **grading_criteria**: 채점 기준 (선택사항)
            """)
        
        # 샘플 CSV 파일 다운로드 버튼들
        st.markdown("### 샘플 CSV 파일 다운로드")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 객관식 문제 샘플
            multiple_choice_sample = """title,description,difficulty,expected_time,type,options,correct_answer,explanation
"영어 단어 선택하기","다음 중 'apple'의 뜻으로 올바른 것은?",쉬움,1,객관식,"사과,바나나,오렌지,포도",1,"'apple'은 영어로 '사과'를 의미합니다."
"수학 문제","2 + 2 = ?",쉬움,1,객관식,"3,4,5,6",2,"2 + 2 = 4 입니다."
"과학 퀴즈","다음 중 포유류가 아닌 것은?",보통,2,객관식,"고래,박쥐,닭,개",3,"닭은 조류입니다. 나머지는 모두 포유류입니다."
"""
            
            if st.download_button(
                label="객관식 문제 샘플",
                data=multiple_choice_sample,
                file_name="multiple_choice_sample.csv",
                mime="text/csv"
            ):
                st.success("객관식 문제 샘플 다운로드 완료!")
        
        with col2:
            # 주관식 문제 샘플
            short_answer_sample = """title,description,difficulty,expected_time,type,answer,grading_criteria
"영어 단어 쓰기","'사과'를 영어로 쓰시오.",쉬움,1,주관식,"apple","철자가 정확해야 함"
"수도 이름","대한민국의 수도는?",쉬움,1,주관식,"서울","서울, 서울특별시 모두 정답"
"간단한 계산","7 × 8의 값을 구하시오.",보통,2,주관식,"56","정확한 숫자만 정답"
"""
            
            if st.download_button(
                label="주관식 문제 샘플",
                data=short_answer_sample,
                file_name="short_answer_sample.csv",
                mime="text/csv"
            ):
                st.success("주관식 문제 샘플 다운로드 완료!")
        
        with col3:
            # 서술식 문제 샘플
            essay_sample = """title,description,difficulty,expected_time,type,answer,grading_criteria
"자기소개","자신에 대해 100단어 이상으로 소개해 보세요.",보통,10,서술식,"(예시 답안은 학생마다 다름)","1. 100단어 이상 작성 (30점) 2. 문법 및 맞춤법 (30점) 3. 내용의 충실성 (40점)"
"환경 문제 에세이","환경 오염의 주요 원인과 해결책에 대해 서술하시오.",어려움,15,서술식,"환경 오염의 주요 원인으로는 산업 활동, 교통, 폐기물 처리 등이 있습니다. 해결책으로는 친환경 에너지 사용, 재활용 촉진, 환경 교육 강화 등이 있습니다.","1. 원인 분석 (40점) 2. 해결책 제시 (40점) 3. 논리적 구성 (20점)"
"역사적 사건 분석","한국 전쟁이 한반도에 미친 영향에 대해 설명하시오.",어려움,20,서술식,"한국 전쟁은 정치, 경제, 사회적으로 큰 영향을 미쳤습니다. 정치적으로는 분단이 고착화되었고, 경제적으로는 전후 재건 과정을 겪었으며, 사회적으로는 이산가족 문제 등이 발생했습니다.","1. 정치적 영향 (30점) 2. 경제적 영향 (30점) 3. 사회적 영향 (30점) 4. 자료 활용 (10점)"
"""
            
            if st.download_button(
                label="서술식 문제 샘플",
                data=essay_sample,
                file_name="essay_sample.csv",
                mime="text/csv"
            ):
                st.success("서술식 문제 샘플 다운로드 완료!")
        
        # CSV 파일 업로드
        uploaded_file = st.file_uploader("CSV 파일 선택", type=["csv"])
        
        if uploaded_file is not None:
            try:
                # pandas로 CSV 파일 읽기
                df = pd.read_csv(uploaded_file)
                
                # 데이터 미리보기
                st.write("업로드된 데이터 미리보기:")
                st.dataframe(df.head())
                
                # 필수 필드 확인
                required_fields = ["title", "description", "difficulty", "type"]
                missing_fields = [field for field in required_fields if field not in df.columns]
                
                if missing_fields:
                    st.error(f"필수 필드가 누락되었습니다: {', '.join(missing_fields)}")
                else:
                    # 데이터 처리 및 문제 추가 로직
                    if st.button("문제 추가하기"):
                        success_count = 0
                        error_count = 0
                        
                        # 교사의 문제 목록 초기화
                        if st.session_state.username not in st.session_state.teacher_problems:
                            st.session_state.teacher_problems[st.session_state.username] = []
                        
                        for _, row in df.iterrows():
                            try:
                                problem = {
                                    "id": str(uuid.uuid4()),
                                    "title": row["title"],
                                    "description": row["description"],
                                    "difficulty": row["difficulty"],
                                    "created_by": st.session_state.username,
                                    "created_at": datetime.now().isoformat()
                                }
                                
                                # 문제 유형에 따른 추가 필드
                                problem_type = row["type"]
                                if problem_type == "객관식":
                                    problem["problem_type"] = "multiple_choice"
                                    # 선택지 처리
                                    if "options" in row and not pd.isna(row["options"]):
                                        problem["options"] = [opt.strip() for opt in str(row["options"]).split(",")]
                                    else:
                                        problem["options"] = []
                                    
                                    # 정답 처리
                                    if "correct_answer" in row and not pd.isna(row["correct_answer"]):
                                        problem["correct_answer"] = int(row["correct_answer"])
                                else:
                                    problem["problem_type"] = "essay"
                                
                                # 공통 추가 필드
                                if "expected_time" in row and not pd.isna(row["expected_time"]):
                                    problem["expected_time"] = int(row["expected_time"])
                                
                                if "answer" in row and not pd.isna(row["answer"]):
                                    problem["sample_answer"] = row["answer"]
                                
                                if "explanation" in row and not pd.isna(row["explanation"]):
                                    problem["explanation"] = row["explanation"]
                                
                                if "grading_criteria" in row and not pd.isna(row["grading_criteria"]):
                                    problem["grading_criteria"] = row["grading_criteria"]
                                
                                # 교사의 문제 목록에 추가
                                st.session_state.teacher_problems[st.session_state.username].append(problem)
                                success_count += 1
                            except Exception as e:
                                error_count += 1
                                st.error(f"문제 추가 중 오류 발생: {e}")
                        
                        # 변경사항 저장
                        save_teacher_problems()
                        
                        if success_count > 0:
                            st.success(f"{success_count}개의 문제가 성공적으로 추가되었습니다.")
                        if error_count > 0:
                            st.warning(f"{error_count}개의 문제 추가 중 오류가 발생했습니다.")
                        
                        # 3초 후 새로고침
                        time.sleep(3)
                        st.rerun()
                
            except Exception as e:
                st.error(f"파일 처리 중 오류가 발생했습니다: {e}")
    
    elif problem_creation_method == "직접 문제 출제":
        st.subheader("직접 문제 출제")
        
        # 문제 정보 입력 폼
        problem_type = st.selectbox(
            "문제 유형:",
            ["주관식", "객관식", "서술식"]
        )
        
        title = st.text_input("문제 제목:")
        description = st.text_area("문제 내용:")
        
        col1, col2 = st.columns(2)
        
        with col1:
            difficulty = st.selectbox(
                "난이도:",
                ["쉬움", "보통", "어려움"]
            )
            
            expected_time = st.number_input("예상 풀이 시간(분):", min_value=1, value=5)
        
        with col2:
            subject = st.selectbox(
                "과목:",
                ["수학", "영어", "국어", "과학", "사회", "기타"]
            )
            
            school_type = st.selectbox(
                "학교 구분:",
                ["초등학교", "중학교", "고등학교", "기타"]
            )
            
            grade = st.selectbox(
                "학년:",
                ["1", "2", "3", "4", "5", "6"]
            )
        
        # 문제 유형에 따른 추가 필드
        if problem_type == "객관식":
            st.subheader("선택지 입력")
            
            options = []
            for i in range(4):
                option = st.text_input(f"선택지 {i+1}:", key=f"option_{i}")
                options.append(option)
            
            correct_answer = st.number_input("정답 번호:", min_value=1, max_value=4, value=1)
            explanation = st.text_area("문제 해설:")
            
        else:  # 주관식 또는 서술식
            sample_answer = st.text_area("예시 답안:")
            grading_criteria = st.text_area("채점 기준:")
        
        # 문제 추가 버튼
        if st.button("문제 추가"):
            if not title or not description:
                st.error("제목과 내용은 필수 입력 항목입니다.")
            elif problem_type == "객관식" and (not all(options) or not correct_answer):
                st.error("객관식 문제는 모든 선택지와 정답을 입력해야 합니다.")
            elif (problem_type == "주관식" or problem_type == "서술식") and not sample_answer:
                st.error("주관식/서술식 문제는 예시 답안을 입력해야 합니다.")
            else:
                # 교사의 문제 목록 초기화
                if st.session_state.username not in st.session_state.teacher_problems:
                    st.session_state.teacher_problems[st.session_state.username] = []
                
                # 새 문제 생성
                new_problem = {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "description": description,
                    "difficulty": difficulty,
                    "subject": subject,
                    "school_type": school_type,
                    "grade": grade,
                    "expected_time": expected_time,
                    "created_by": st.session_state.username,
                    "created_at": datetime.now().isoformat()
                }
                
                # 문제 유형에 따른 추가 필드
                if problem_type == "객관식":
                    new_problem["problem_type"] = "multiple_choice"
                    new_problem["options"] = options
                    new_problem["correct_answer"] = correct_answer
                    new_problem["explanation"] = explanation
                else:
                    new_problem["problem_type"] = "essay" if problem_type == "주관식" else "long_essay"
                    new_problem["sample_answer"] = sample_answer
                    new_problem["grading_criteria"] = grading_criteria
                
                # 교사의 문제 목록에 추가
                st.session_state.teacher_problems[st.session_state.username].append(new_problem)
                
                # 변경사항 저장
                save_teacher_problems()
                
                st.success("문제가 성공적으로 추가되었습니다!")
                time.sleep(2)
                st.rerun()
    
    else:  # AI 문제 자동 생성
        st.subheader("AI 문제 자동 생성")
        
        # API 키 확인
        if not st.session_state.get("openai_api_key"):
            st.error("OpenAI API 키가 설정되지 않았습니다. 관리자에게 문의하세요.")
            return
        
        # AI 문제 생성 설정
        col1, col2 = st.columns(2)
        
        with col1:
            ai_subject = st.selectbox(
                "과목:",
                ["수학", "영어", "국어", "과학", "사회"]
            )
            
            ai_school_type = st.selectbox(
                "학교 구분:",
                ["중학교", "고등학교"]
            )
        
        with col2:
            ai_grade = st.selectbox(
                "학년:",
                ["1", "2", "3"]
            )
            
            ai_difficulty = st.selectbox(
                "난이도:",
                ["쉬움", "보통", "어려움"]
            )
        
        ai_topic = st.text_input("주제(구체적일수록 좋습니다):", value="임의대로", help="비워두면 '임의대로'로 설정됩니다")
        if not ai_topic.strip():
            ai_topic = "임의대로"
        
        ai_problem_type = st.radio(
            "문제 유형:",
            ["객관식", "주관식", "서술식"]
        )
        
        problem_count = st.slider("생성할 문제 수:", min_value=1, max_value=5, value=3)
        
        # 문제 생성 버튼
        if st.button("AI로 문제 생성"):
            with st.spinner("AI가 문제를 생성 중입니다... (최대 1분 소요)"):
                try:
                    # OpenAI API 호출
                    client = openai.OpenAI(api_key=st.session_state.openai_api_key)
                    
                    # 프롬프트 생성
                    system_prompt = f"""
                    당신은 교육 전문가로서 학생들을 위한 고품질 문제를 생성합니다.
                    다음 조건에 맞는 {problem_count}개의 문제를 생성해 주세요:
                    - 과목: {ai_subject}
                    - 학교: {ai_school_type}
                    - 학년: {ai_grade}학년
                    - 난이도: {ai_difficulty}
                    - 주제: {ai_topic}
                    - 문제 유형: {ai_problem_type}
                    
                    문제 형식은 다음과 같이 제공해 주세요:
                    """
                    
                    if ai_problem_type == "객관식":
                        system_prompt += """
                        문제 1:
                        제목: [문제 제목]
                        내용: [문제 내용]
                        보기1: [선택지 1]
                        보기2: [선택지 2]
                        보기3: [선택지 3]
                        보기4: [선택지 4]
                        정답: [정답 번호(1~4)]
                        해설: [문제 해설]
                        예상 시간: [풀이 예상 시간(분)]
                        
                        문제 2:
                        ...
                        """
                    else:
                        system_prompt += """
                        문제 1:
                        제목: [문제 제목]
                        내용: [문제 내용]
                        예시 답안: [모범 답안]
                        채점 기준: [채점 기준]
                        예상 시간: [풀이 예상 시간(분)]
                        
                        문제 2:
                        ...
                        """
                    
                    # API 호출
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"{ai_subject} {ai_school_type} {ai_grade}학년 학생들을 위한 {ai_topic} 관련 {ai_problem_type} {problem_count}개를 생성해 주세요."}
                        ],
                        temperature=0.7,
                        max_tokens=2000
                    )
                    
                    # 응답 처리
                    generated_content = response.choices[0].message.content
                    
                    st.subheader("생성된 문제")
                    st.write(generated_content)
                    
                    # 생성된 문제 파싱 및 저장
                    st.info("""
                    💾 문제 저장 안내:
                    1. 생성된 문제는 자동으로 파싱되어 교사의 문제 저장소에 저장됩니다.
                    2. 저장된 문제는 'data/teacher_problems.json' 파일에 보관됩니다.
                    3. 저장된 문제는 '문제 저장소' 메뉴에서 확인할 수 있습니다.
                    """)
                    
                    if st.button("생성된 문제 저장", key="save_generated"):
                        problems = []
                        try:
                            if ai_problem_type == "객관식":
                                problems = parse_multiple_choice_problems(generated_content)
                            else:
                                problems = parse_essay_problems(generated_content)
                            
                            # 교사의 문제 목록 초기화
                            if st.session_state.username not in st.session_state.teacher_problems:
                                st.session_state.teacher_problems[st.session_state.username] = []
                            
                            # 문제 추가
                            for problem in problems:
                                problem["created_by"] = st.session_state.username
                                problem["created_at"] = datetime.now().isoformat()
                                st.session_state.teacher_problems[st.session_state.username].append(problem)
                            
                            # 변경사항 저장
                            save_teacher_problems()
                            st.success(f"{len(problems)}개의 문제가 성공적으로 저장되었습니다!")
                            
                            # 저장 위치 안내
                            st.info("저장된 문제는 '문제 저장소' 메뉴에서 확인할 수 있습니다.")
                            time.sleep(2)
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"문제 저장 중 오류가 발생했습니다: {str(e)}")
                
                except Exception as e:
                    st.error(f"AI 문제 생성 중 오류가 발생했습니다: {str(e)}")

def main():
    # 앱 초기화
    init_app()
    
    # 앱 시작 시 설정 파일에서 API 키 로드
    load_api_keys()
    
    # 세션 상태 초기화
    if 'users' not in st.session_state:
        load_users_data()
    
    if 'teacher_problems' not in st.session_state:
        load_teacher_problems()
    
    if 'student_records' not in st.session_state:
        load_student_records()
    
    # 문제 저장소 초기화
    if 'problem_repository' not in st.session_state:
        load_problem_repository()
    
    # 로그인 상태 확인
    if st.session_state.username is None:
        login_page()
    else:
        # 사용자 역할에 따라 다른 대시보드 표시
        user_role = st.session_state.users.get(st.session_state.username, {}).get("role")
        
        if user_role == "admin":
            admin_dashboard()
        elif user_role == "teacher":
            teacher_dashboard()
        elif user_role == "student":
            student_dashboard()
        else:
            st.error("알 수 없는 사용자 역할입니다.")
            logout_user()
            st.rerun()

# 앱 초기화 함수
def init_app():
    """앱 초기화 함수"""
    if "initialized" not in st.session_state:
        st.session_state.initialized = False
        st.session_state.username = None
        st.session_state.users = {}
        
    if not st.session_state.initialized:
        # 기본 사용자 데이터 초기화
        default_users = {
            'admin': {
                'username': 'admin',
                'password': 'admin',
                'role': 'admin',
                'name': '관리자'
            },
            'teacher': {
                'username': 'teacher',
                'password': 'teacher',
                'role': 'teacher',
                'name': '선생님'
            },
            'student': {
                'username': 'student',
                'password': 'student',
                'role': 'student',
                'name': '학생'
            }
        }
        
        # 기존 사용자 데이터가 있으면 로드
        if os.path.exists('users.json'):
            try:
                with open('users.json', 'r', encoding='utf-8') as f:
                    st.session_state.users = json.load(f)
            except:
                st.session_state.users = default_users
        else:
            st.session_state.users = default_users
            
        # 초기화 완료 표시
        st.session_state.initialized = True

# 데이터 로드 함수
def load_users_data():
    try:
        with open("data/users.json", "r") as f:
            st.session_state.users = json.load(f)
    except FileNotFoundError:
        st.session_state.users = {}
        
def load_teacher_problems():
    try:
        with open("data/teacher_problems.json", "r") as f:
            st.session_state.teacher_problems = json.load(f)
    except FileNotFoundError:
        st.session_state.teacher_problems = {}
        
def load_student_records():
    try:
        with open("data/student_records.json", "r") as f:
            st.session_state.student_records = json.load(f)
    except FileNotFoundError:
        st.session_state.student_records = {}

# teacher_student_management 함수 추가
def teacher_student_management():
    st.header("학생 관리")
    
    # 학생 목록 가져오기
    students = {username: user_data for username, user_data in st.session_state.users.items() 
                if user_data.get("role") == "student"}
    
    if not students:
        st.info("등록된 학생이 없습니다.")
        
        # 새 학생 등록 폼
        with st.expander("새 학생 등록", expanded=True):
            add_new_student()
            
        return
    
    # 학생 목록 및, 정보 표시
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("학생 목록")
        selected_student = st.selectbox(
            "학생 선택:",
            list(students.keys()),
            format_func=lambda x: f"{students[x].get('name', '')} ({x})"
        )
    
    with col2:
        if selected_student:
            st.subheader("학생 정보")
            student_data = students[selected_student]
            
            # 학생 기본 정보
            st.markdown(f"**이름:** {student_data.get('name', '')}")
            st.markdown(f"**아이디:** {selected_student}")
            st.markdown(f"**이메일:** {student_data.get('email', '없음')}")
            st.markdown(f"**등록일:** {student_data.get('created_at', '알 수 없음')}")
            st.markdown(f"**등록자:** {student_data.get('created_by', '알 수 없음')}")
            
            # 학생 기록 불러오기
            student_records = st.session_state.student_records.get(selected_student, {})
            solved_problems = student_records.get("problems", {})
            
            # 학습 통계
            st.subheader("학습 통계")
            
            problems_attempted = len(solved_problems)
            problems_completed = sum(1 for problem in solved_problems.values() 
                                   if problem.get("status") == "completed")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("시도한 문제 수", problems_attempted)
            with col2:
                st.metric("완료한 문제 수", problems_completed)
            with col3:
                if problems_completed > 0:
                    total_score = sum(problem.get("score", 0) for problem in solved_problems.values() 
                                     if problem.get("status") == "completed")
                    average_score = total_score / problems_completed
                    st.metric("평균 점수", f"{average_score:.1f}")
                else:
                    st.metric("평균 점수", "0.0")
            
            # 학생 계정 관리 옵션
            st.subheader("계정 관리")
            
            if st.button("비밀번호 초기화"):
                if st.session_state.users[selected_student].get("password_reset_by_teacher"):
                    st.warning("이미 비밀번호가 초기화되었습니다.")
                else:
                    # 임시 비밀번호 생성 및 설정
                    temp_password = "".join([str(random.randint(0, 9)) for _ in range(6)])
                    st.session_state.users[selected_student]["password_hash"] = hash_password(temp_password)
                    st.session_state.users[selected_student]["password_reset_by_teacher"] = True
                    
                    # 사용자 데이터 저장
                    save_users_data()
                    
                    st.success(f"비밀번호가 초기화되었습니다. 임시 비밀번호: {temp_password}")
            
            if st.button("학생 계정 삭제", type="primary"):
                # 확인 대화상자
                confirmation = st.text_input("삭제하려면 '삭제확인'을 입력하세요:")
                if confirmation == "삭제확인":
                    # 학생 계정 삭제
                    st.session_state.users.pop(selected_student, None)
                    
                    # 학생 기록 삭제
                    if selected_student in st.session_state.student_records:
                        st.session_state.student_records.pop(selected_student, None)
                    
                    # 변경사항 저장
                    save_users_data()
                    save_student_records()
                    
                    st.success("학생 계정이 삭제되었습니다.")
                    st.rerun()
    
    # 새 학생 등록 폼
    with st.expander("새 학생 등록"):
        add_new_student()

# 새 학생 등록 함수
def add_new_student():
    st.subheader("새 학생 등록")
    
    col1, col2 = st.columns(2)
    
    with col1:
        student_name = st.text_input("학생 이름:")
        student_username = st.text_input("학생 아이디:")
    
    with col2:
        student_email = st.text_input("이메일(선택사항):")
        student_password = st.text_input("비밀번호:", type="password")
    
    if st.button("학생 등록"):
        if not student_name or not student_username or not student_password:
            st.error("이름, 아이디, 비밀번호는 필수 입력 항목입니다.")
        elif student_username in st.session_state.users:
            st.error(f"아이디 '{student_username}'는 이미 사용 중입니다.")
        elif len(student_password) < 4:
            st.error("비밀번호는 최소 4자 이상이어야 합니다.")
        else:
            # 학생 등록
            password_hash = hash_password(student_password)
            
            st.session_state.users[student_username] = {
                "username": student_username,
                "password_hash": password_hash,
                "name": student_name,
                "email": student_email,
                "role": "student",
                "created_at": datetime.now().isoformat(),
                "created_by": st.session_state.username,
                "first_login": True
            }
            
            # 학생 기록 초기화
            if student_username not in st.session_state.student_records:
                st.session_state.student_records[student_username] = {
                    "problems": {}
                }
            
            # 변경사항 저장
            save_users_data()
            save_student_records()
            
            st.success(f"학생 '{student_name}'이(가) 성공적으로 등록되었습니다.")
            time.sleep(2)
            st.rerun()

# teacher_problem_list 함수 추가
def teacher_problem_list():
    st.header("내 문제 목록")
    
    # 교사가 출제한 문제 목록 가져오기
    teacher_problems = st.session_state.teacher_problems.get(st.session_state.username, [])
    
    if not teacher_problems:
        st.info("출제한 문제가 없습니다. '문제 출제' 메뉴에서 문제를 만들어주세요.")
        return
    
    # 정렬 옵션
    sort_option = st.selectbox(
        "정렬:",
        ["최신순", "난이도순"]
    )
    
    # 정렬
    if sort_option == "최신순":
        sorted_problems = sorted(teacher_problems, key=lambda x: x.get("created_at", ""), reverse=True)
    else:  # 난이도순
        difficulty_order = {"쉬움": 0, "보통": 1, "어려움": 2}
        sorted_problems = sorted(teacher_problems, key=lambda x: difficulty_order.get(x.get("difficulty", "보통"), 1))
    
    # 필터링 옵션들
    with st.expander("필터 옵션"):
        col1, col2 = st.columns(2)
        
        with col1:
            filter_difficulty = st.multiselect(
                "난이도:",
                ["쉬움", "보통", "어려움"],
                default=["쉬움", "보통", "어려움"]
            )
            
            filter_type = st.multiselect(
                "문제 유형:",
                ["객관식", "주관식", "서술식"],
                default=["객관식", "주관식", "서술식"]
            )
        
        with col2:
            # 출제일 범위 선택
            filter_date_range = st.date_input(
                "출제일 범위:",
                value=(datetime.strptime("2020-01-01", "%Y-%m-%d").date(), datetime.now().date()),
                format="YYYY-MM-DD"
            )
    
    # 필터링
    filtered_problems = []
    for problem in sorted_problems:
        # 난이도 필터링
        if problem.get("difficulty") not in filter_difficulty:
            continue
        
        # 문제 유형 필터링
        problem_type = problem.get("problem_type", "essay")
        if ((problem_type == "multiple_choice" and "객관식" not in filter_type) or
            (problem_type == "essay" and "주관식" not in filter_type) or
            (problem_type == "long_essay" and "서술식" not in filter_type)):
            continue
        
        # 출제일 필터링
        if "created_at" in problem:
            try:
                created_date = datetime.fromisoformat(problem["created_at"]).date()
                if len(filter_date_range) == 2:
                    if created_date < filter_date_range[0] or created_date > filter_date_range[1]:
                        continue
            except:
                pass
        
        filtered_problems.append(problem)
    
    # 필터링 결과 표시
    st.write(f"총 {len(filtered_problems)}개의 문제")
    
    # 문제 목록 표시
    for i, problem in enumerate(filtered_problems):
        # 문제 타입 표시
        problem_type = problem.get("problem_type", "essay")
        type_label = "객관식" if problem_type == "multiple_choice" else "주관식" if problem_type == "essay" else "서술식"
        
        # 문제 상태 정보
        total_attempts = 0
        completed_count = 0
        
        for student_id, student_record in st.session_state.student_records.items():
            for p_id, p_data in student_record.get("problems", {}).items():
                if p_id == problem.get("id"):
                    total_attempts += 1
                    if p_data.get("status") == "completed":
                        completed_count += 1
        
        # 문제 카드 표시
        with st.expander(f"{i+1}. [{type_label}] {problem.get('title', '제목 없음')} ({problem.get('difficulty', '보통')})"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**내용:** {problem.get('description', '내용 없음')}")
                
                if problem_type == "multiple_choice":
                    st.markdown("**선택지:**")
                    for j, option in enumerate(problem.get("options", [])):
                        st.markdown(f"{j+1}. {option}")
                    st.markdown(f"**정답:** {problem.get('correct_answer', '정답 없음')}")
                else:
                    if "sample_answer" in problem:
                        st.markdown(f"**예시 답안:** {problem.get('sample_answer', '답안 없음')}")
                    
                    if "grading_criteria" in problem:
                        st.markdown(f"**채점 기준:** {problem.get('grading_criteria', '채점 기준 없음')}")
            
            with col2:
                st.markdown(f"**시도 횟수:** {total_attempts}")
                st.markdown(f"**완료 횟수:** {completed_count}")
                st.markdown(f"**출제일:** {problem.get('created_at', '알 수 없음')[:10]}")
                
                # 문제 관리 버튼
                if st.button("문제 수정", key=f"edit_{i}"):
                    st.session_state.edit_problem_id = problem.get("id")
                    st.rerun()
                
                if st.button("문제 삭제", key=f"delete_{i}"):
                    # 삭제 확인
                    if st.button(f"정말 삭제하시겠습니까?", key=f"confirm_delete_{i}"):
                        # 문제 삭제
                        st.session_state.teacher_problems[st.session_state.username] = [
                            p for p in st.session_state.teacher_problems[st.session_state.username] 
                            if p.get("id") != problem.get("id")
                        ]
                        
                        # 변경사항 저장
                        save_teacher_problems()
                        
                        st.success("문제가 삭제되었습니다.")
                        time.sleep(2)
                        st.rerun()

# teacher_grading 함수 추가
def teacher_grading():
    st.header("학생 답안 채점")
    
    # 채점할 답안 찾기 (완료되지 않은 답안)
    pending_submissions = []
    
    for student_id, student_record in st.session_state.student_records.items():
        student_name = st.session_state.users.get(student_id, {}).get("name", student_id)
        
        for problem_id, problem_data in student_record.get("problems", {}).items():
            if problem_data.get("status") == "submitted" and not problem_data.get("score"):
                # 문제 정보 가져오기
                problem_info = None
                if problem_id in st.session_state.teacher_problems:
                    problem_info = st.session_state.teacher_problems[problem_id]
                else:
                    # 교사별 문제 목록에서 찾기
                    for teacher_id, problems in st.session_state.teacher_problems.items():
                        for problem in problems:
                            if problem.get("id") == problem_id:
                                problem_info = problem
                                break
                        if problem_info:
                            break
                
                if problem_info and problem_info.get("created_by") == st.session_state.username:
                    # 내가 출제한 문제만 추가
                    pending_submissions.append({
                        "student_id": student_id,
                        "student_name": student_name,
                        "problem_id": problem_id,
                        "problem_title": problem_info.get("title", "제목 없음"),
                        "submitted_at": problem_data.get("submitted_at", "")
                    })
    
    if not pending_submissions:
        st.info("현재 채점할 답안이 없습니다.")
        return
    
    # 채점할 답안 선택
    selected_submission_idx = st.selectbox(
        "채점할 답안 선택:",
        range(len(pending_submissions)),
        format_func=lambda x: f"{pending_submissions[x]['student_name']} - {pending_submissions[x]['problem_title']} ({pending_submissions[x]['submitted_at'][:10]})"
    )
    
    selected_submission = pending_submissions[selected_submission_idx]
    
    # 선택한 제출물 정보
    student_id = selected_submission["student_id"]
    problem_id = selected_submission["problem_id"]
    
    # 문제 및 답안 정보 가져오기
    problem_info = None
    for teacher_id, problems in st.session_state.teacher_problems.items():
        for problem in problems:
            if problem.get("id") == problem_id:
                problem_info = problem
                break
        if problem_info:
            break
    
    if not problem_info:
        st.error("문제 정보를 찾을 수 없습니다.")
        return
    
    student_answer = st.session_state.student_records[student_id]["problems"][problem_id].get("answer", "")
    
    # 채점 폼 표시
    st.subheader("채점 폼")
    
    # 문제 정보 표시
    with st.expander("문제 정보", expanded=True):
        st.markdown(f"**제목:** {problem_info.get('title', '제목 없음')}")
        st.markdown(f"**내용:** {problem_info.get('description', '내용 없음')}")
        
        if problem_info.get("problem_type") == "multiple_choice":
            st.markdown("**선택지:**")
            for i, option in enumerate(problem_info.get("options", [])):
                st.markdown(f"{i+1}. {option}")
            st.markdown(f"**정답:** {problem_info.get('correct_answer', '정답 없음')}")
        else:
            if "sample_answer" in problem_info:
                st.markdown(f"**예시 답안:** {problem_info.get('sample_answer', '예시 답안 없음')}")
            
            if "grading_criteria" in problem_info:
                st.markdown(f"**채점 기준:** {problem_info.get('grading_criteria', '채점 기준 없음')}")
    
    # 학생 답안 표시
    st.subheader("학생 답안")
    st.write(student_answer)
    
    # 채점 입력
    score = st.number_input("점수 (0-100):", min_value=0, max_value=100, value=80)
    feedback = st.text_area("피드백:", value=generate_default_feedback(score))
    
    # 채점 완료 버튼
    if st.button("채점 완료"):
        # 학생 기록 업데이트
        st.session_state.student_records[student_id]["problems"][problem_id]["score"] = score
        st.session_state.student_records[student_id]["problems"][problem_id]["feedback"] = feedback
        st.session_state.student_records[student_id]["problems"][problem_id]["graded_by"] = st.session_state.username
        st.session_state.student_records[student_id]["problems"][problem_id]["graded_at"] = datetime.now().isoformat()
        st.session_state.student_records[student_id]["problems"][problem_id]["status"] = "completed"
        
        # 변경사항 저장
        save_student_records()
        
        st.success("채점이 완료되었습니다.")
        time.sleep(2)
        st.rerun()

# 기본 피드백 생성 함수
def generate_default_feedback(score):
    if score >= 90:
        return "훌륭한 답변입니다! 내용이 정확하고 잘 구성되어 있습니다."
    elif score >= 80:
        return "좋은 답변입니다. 몇 가지 작은 개선 사항이 있지만 전반적으로 잘했습니다."
    elif score >= 70:
        return "괜찮은 답변입니다. 몇 가지 부분에서 개선이 필요합니다."
    elif score >= 60:
        return "기본적인 내용은 있지만, 더 많은 설명과 구체적인 내용이 필요합니다."
    else:
        return "더 많은 노력이 필요합니다. 문제의 요구사항을 다시 확인하고 답변을 보완해 보세요."

# student_my_info 함수 추가
def student_my_info():
    st.header("내 정보")
    
    # 학생 정보 가져오기
    student_data = st.session_state.users.get(st.session_state.username, {})
    
    # 기본 정보 표시
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("기본 정보")
        st.write(f"**이름:** {student_data.get('name', '')}")
        st.write(f"**아이디:** {st.session_state.username}")
        st.write(f"**이메일:** {student_data.get('email', '')}")
    
    with col2:
        st.subheader("학습 통계")
        
        # 학생 기록 불러오기
        student_records = st.session_state.student_records.get(st.session_state.username, {})
        problems = student_records.get("problems", {})
        
        # 기본 통계 계산
        problems_attempted = len(problems)
        problems_completed = sum(1 for problem in problems.values() 
                                if problem.get("status") == "completed")
        
        total_score = sum(problem.get("score", 0) for problem in problems.values() 
                          if problem.get("status") == "completed")
        
        if problems_completed > 0:
            average_score = total_score / problems_completed
        else:
            average_score = 0
        
        st.write(f"**시도한 문제 수:** {problems_attempted}")
        st.write(f"**완료한 문제 수:** {problems_completed}")
        st.write(f"**평균 점수:** {average_score:.1f}")
    
    # 비밀번호 변경 섹션
    st.markdown("---")
    st.subheader("비밀번호 변경")
    
    col1, col2 = st.columns(2)
    
    with col1:
        current_password = st.text_input("현재 비밀번호", type="password")
    
    with col2:
        new_password = st.text_input("새 비밀번호", type="password")
        confirm_password = st.text_input("새 비밀번호 확인", type="password")
    
    if st.button("비밀번호 변경"):
        if not current_password or not new_password or not confirm_password:
            st.error("모든 필드를 입력해야 합니다.")
        elif new_password != confirm_password:
            st.error("새 비밀번호와 확인이 일치하지 않습니다.")
        elif len(new_password) < 4:
            st.error("비밀번호는 최소 4자 이상이어야 합니다.")
        else:
            # 현재 비밀번호 확인
            if verify_password(student_data.get("password_hash", ""), current_password):
                # 새 비밀번호로 업데이트
                password_hash = hash_password(new_password)
                st.session_state.users[st.session_state.username]["password_hash"] = password_hash
                
                # 비밀번호 초기화 플래그 제거 (교사가 초기화한 경우)
                if "password_reset_by_teacher" in st.session_state.users[st.session_state.username]:
                    st.session_state.users[st.session_state.username].pop("password_reset_by_teacher", None)
                
                save_users_data()
                st.success("비밀번호가 성공적으로 변경되었습니다.")
            else:
                st.error("현재 비밀번호가 올바르지 않습니다.")

# save_teacher_problems 함수 추가
def save_teacher_problems():
    try:
        with open("data/teacher_problems.json", "w") as f:
            json.dump(st.session_state.teacher_problems, f, indent=2)
    except Exception as e:
        st.error(f"문제 데이터 저장 중 오류 발생: {str(e)}")

# save_student_records 함수 추가
def save_student_records():
    try:
        with open("data/student_records.json", "w") as f:
            json.dump(st.session_state.student_records, f, indent=2)
    except Exception as e:
        st.error(f"학생 기록 저장 중 오류 발생: {str(e)}")

# 로그인 페이지 함수
def login_page():
    """로그인 페이지"""
    st.markdown("""
        <style>
        .main-title {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin-bottom: 2rem;
        }
        .main-title h1 {
            font-size: 24px;
            color: #333;
            margin: 0;
        }
        .stTextInput > div > div > input {
            background-color: #f8f9fa;
        }
        .stButton > button {
            width: 100%;
            margin-top: 1rem;
        }
        .demo-info {
            background-color: #f8f9fa;
            padding: 1rem;
            border-radius: 5px;
            margin-top: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # 메인 타이틀
    col1, col2 = st.columns([1, 6])
    with col1:
        st.image("🎓", width=50)
    with col2:
        st.markdown("<h1>학습 관리 시스템</h1>", unsafe_allow_html=True)

    # 로그인 폼
    st.markdown("아이디")
    username = st.text_input("", placeholder="아이디를 입력하세요", key="username", label_visibility="collapsed")
    
    st.markdown("비밀번호")
    password = st.text_input("", type="password", placeholder="비밀번호를 입력하세요", key="password", label_visibility="collapsed")

    # 로그인 버튼
    if st.button("로그인", use_container_width=True):
        if not username or not password:
            st.error("아이디와 비밀번호를 모두 입력해주세요.")
        else:
            if username in st.session_state.users:
                user_data = st.session_state.users[username]
                if user_data['password'] == password:
                    st.session_state.username = username
                    role = user_data['role']
                    
                    # 역할에 따른 환영 메시지
                    if role == "admin":
                        st.success("👨‍💼 관리자로 로그인되었습니다.")
                    elif role == "teacher":
                        st.success("👨‍🏫 교사로 로그인되었습니다.")
                    elif role == "student":
                        st.success("👨‍🎓 학생으로 로그인되었습니다.")
                    
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("비밀번호가 일치하지 않습니다.")
            else:
                st.error("존재하지 않는 아이디입니다.")

    # 데모 계정 정보
    with st.expander("데모 계정 정보"):
        st.markdown("""
        🔑 데모 계정:
        
        - 관리자: admin / admin
        - 교사: teacher / teacher
        - 학생: student / student
        """)

    with tab2:
        st.markdown("### 👨‍🏫 교사 계정 신청")
        st.info("교사 계정은 관리자 승인 후 사용할 수 있습니다.")
        
        new_name = st.text_input("이름:", key="register_name", placeholder="실명을 입력하세요")
        new_username = st.text_input("사용할 아이디:", key="register_username", placeholder="사용할 아이디를 입력하세요")
        new_password = st.text_input("비밀번호:", type="password", key="register_password", placeholder="비밀번호를 입력하세요")
        confirm_password = st.text_input("비밀번호 확인:", type="password", key="confirm_password", placeholder="비밀번호를 다시 입력하세요")
        
        if st.button("계정 신청"):
            if not new_name or not new_username or not new_password or not confirm_password:
                st.error("모든 필드를 입력해주세요.")
            elif new_password != confirm_password:
                st.error("비밀번호가 일치하지 않습니다.")
            elif new_username in st.session_state.users:
                st.error("이미 사용 중인 아이디입니다.")
            else:
                st.session_state.users[new_username] = {
                    'username': new_username,
                    'password': new_password,
                    'name': new_name,
                    'role': 'pending_teacher'
                }
                save_users_data()
                st.success("교사 계정 신청이 완료되었습니다. 관리자 승인을 기다려주세요.")

# 관리자 대시보드 함수
def admin_dashboard():
    st.title("👨‍💼 관리자 대시보드")
    
    # 사이드바 메뉴
    with st.sidebar:
        st.header("관리자 메뉴")
        selected_menu = st.radio(
            "메뉴 선택:",
            ["사용자 관리", "API 설정", "백업/복원"]
        )
        
        # 로그아웃 버튼
        if st.button("로그아웃", key="admin_logout"):
            logout_user()
            st.rerun()
    
    # 선택된 메뉴에 따라 다른 내용 표시
    if selected_menu == "사용자 관리":
        admin_user_management()
    elif selected_menu == "API 설정":
        admin_api_settings()
    elif selected_menu == "백업/복원":
        admin_backup_restore()

# 관리자 사용자 관리 함수
def admin_user_management():
    st.header("사용자 관리")
    
    # 사용자 목록 가져오기
    all_users = st.session_state.users
    
    # 사용자 필터링 옵션
    filter_role = st.selectbox(
        "역할별 필터링:",
        ["모두", "관리자", "교사", "학생", "승인 대기 교사"]
    )
    
    # 역할별 필터링
    filtered_users = {}
    
    for username, user_data in all_users.items():
        role = user_data.get("role", "")
        
        if filter_role == "모두":
            filtered_users[username] = user_data
        elif filter_role == "관리자" and role == "admin":
            filtered_users[username] = user_data
        elif filter_role == "교사" and role == "teacher":
            filtered_users[username] = user_data
        elif filter_role == "학생" and role == "student":
            filtered_users[username] = user_data
        elif filter_role == "승인 대기 교사" and role == "pending_teacher":
            filtered_users[username] = user_data
    
    # 사용자 목록 표시
    if not filtered_users:
        st.info(f"{filter_role} 역할의 사용자가 없습니다.")
    else:
        st.success(f"{len(filtered_users)}명의 사용자가 있습니다.")
        
        # 사용자 목록 표시
        for username, user_data in filtered_users.items():
            with st.expander(f"{user_data.get('name', '')} ({username}) - {user_data.get('role', '')}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**이름:** {user_data.get('name', '')}")
                    st.write(f"**아이디:** {username}")
                    st.write(f"**이메일:** {user_data.get('email', '없음')}")
                
                with col2:
                    st.write(f"**역할:** {user_data.get('role', '')}")
                    st.write(f"**등록일:** {user_data.get('created_at', '알 수 없음')[:10]}")
                    st.write(f"**등록자:** {user_data.get('created_by', '알 수 없음')}")
                
                # 승인 대기 교사인 경우 승인/거부 버튼 표시
                if user_data.get("role") == "pending_teacher":
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("승인", key=f"approve_{username}"):
                            # 교사로 승인
                            st.session_state.users[username]["role"] = "teacher"
                            save_users_data()
                            st.success(f"{user_data.get('name', '')}님이 교사로 승인되었습니다.")
                            time.sleep(2)
                            st.rerun()
                    
                    with col2:
                        if st.button("거부", key=f"reject_{username}"):
                            # 사용자 삭제
                            st.session_state.users.pop(username, None)
                            save_users_data()
                            st.success(f"{user_data.get('name', '')}님의 교사 신청이 거부되었습니다.")
                            time.sleep(2)
                            st.rerun()
                
                # 일반 사용자인 경우 역할 변경 및 삭제 옵션
                elif username != st.session_state.username:  # 자기 자신은 변경 불가
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_role = st.selectbox(
                            "역할 변경:",
                            ["admin", "teacher", "student"],
                            index=["admin", "teacher", "student"].index(user_data.get("role", "student")),
                            key=f"role_{username}"
                        )
                        
                        if st.button("역할 변경", key=f"change_role_{username}"):
                            # 역할 변경
                            st.session_state.users[username]["role"] = new_role
                            save_users_data()
                            st.success(f"{user_data.get('name', '')}님의 역할이 {new_role}로 변경되었습니다.")
                            time.sleep(2)
                            st.rerun()
                    
                    with col2:
                        if st.button("사용자 삭제", key=f"delete_{username}"):
                            confirmation = st.text_input("삭제하려면 '삭제확인'을 입력하세요:", key=f"confirm_{username}")
                            
                            if confirmation == "삭제확인":
                                # 사용자 삭제
                                st.session_state.users.pop(username, None)
                                
                                # 교사인 경우 출제한 문제 삭제
                                if user_data.get("role") == "teacher" and username in st.session_state.teacher_problems:
                                    st.session_state.teacher_problems.pop(username, None)
                                
                                # 학생인 경우 학습 기록 삭제
                                if user_data.get("role") == "student" and username in st.session_state.student_records:
                                    st.session_state.student_records.pop(username, None)
                                
                                # 변경사항 저장
                                save_users_data()
                                save_teacher_problems()
                                save_student_records()
                                
                                st.success(f"{user_data.get('name', '')}님이 삭제되었습니다.")
                                time.sleep(2)
                                st.rerun()
    
    # 새 사용자 추가 폼
    with st.expander("새 사용자 추가", expanded=False):
        st.subheader("새 사용자 추가")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_name = st.text_input("이름:")
            new_username = st.text_input("아이디:")
            new_password = st.text_input("비밀번호:", type="password")
        
        with col2:
            new_email = st.text_input("이메일(선택사항):")
            new_role = st.selectbox(
                "역할:",
                ["admin", "teacher", "student"]
            )
        
        if st.button("사용자 추가"):
            if not new_name or not new_username or not new_password:
                st.error("이름, 아이디, 비밀번호는 필수 입력 항목입니다.")
            elif new_username in st.session_state.users:
                st.error(f"아이디 '{new_username}'는 이미 사용 중입니다.")
            elif len(new_password) < 4:
                st.error("비밀번호는 최소 4자 이상이어야 합니다.")
            else:
                # 사용자 추가
                register_user(new_username, new_password, new_role, new_name, new_email, created_by=st.session_state.username)
                
                st.success(f"사용자 '{new_name}'이(가) 성공적으로 추가되었습니다.")
                time.sleep(2)
                st.rerun()

# 관리자 API 설정 함수
def admin_api_settings():
    st.markdown("## 🔑 API 키 관리")
    
    # API 키 상태 표시
    api_key = st.session_state.get('openai_api_key', '')
    if api_key:
        st.success("사용자 지정 API 키가 설정되어 있습니다.")
    else:
        st.warning("API 키가 설정되어 있지 않습니다.")

    # API 키 설정 탭과 저장 옵션 탭 생성
    tab1, tab2 = st.tabs(["API 키 설정", "키 저장 옵션"])

    with tab1:
        # API 키 입력 및 설정
        new_api_key = st.text_input("OpenAI API 키 입력:", type="password", help="API 키는 안전하게 저장됩니다.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("API 키 설정", use_container_width=True):
                if new_api_key:
                    st.session_state['openai_api_key'] = new_api_key
                    st.success("API 키가 성공적으로 설정되었습니다.")
                    st.rerun()
                else:
                    st.error("API 키를 입력해주세요.")
        
        with col2:
            if st.button("API 키 초기화", use_container_width=True):
                if 'openai_api_key' in st.session_state:
                    del st.session_state['openai_api_key']
                st.success("API 키가 초기화되었습니다.")
                st.rerun()

    with tab2:
        st.markdown("### API 키 저장 방법 선택")
        save_option = st.radio(
            "API 키 저장 방식:",
            ["저장하지 않음 (세션만 유지)", "config.json 파일에 저장", "환경 변수로 저장", ".env 파일에 저장"],
            index=0
        )

        if st.button("저장 설정 적용"):
            if not api_key:
                st.error("저장할 API 키가 설정되어 있지 않습니다.")
                return

            if save_option == "config.json 파일에 저장":
                try:
                    config = {"openai_api_key": api_key}
                    with open("config.json", "w") as f:
                        json.dump(config, f)
                    st.success("API 키가 config.json 파일에 저장되었습니다.")
                except Exception as e:
                    st.error(f"저장 중 오류가 발생했습니다: {str(e)}")

            elif save_option == "환경 변수로 저장":
                try:
                    os.environ["OPENAI_API_KEY"] = api_key
                    st.success("API 키가 환경 변수에 저장되었습니다.")
                except Exception as e:
                    st.error(f"환경 변수 설정 중 오류가 발생했습니다: {str(e)}")

            elif save_option == ".env 파일에 저장":
                try:
                    with open(".env", "w") as f:
                        f.write(f"OPENAI_API_KEY={api_key}\n")
                    st.success("API 키가 .env 파일에 저장되었습니다.")
                except Exception as e:
                    st.error(f"저장 중 오류가 발생했습니다: {str(e)}")

    # API 연결 테스트
    st.markdown("### API 연결 테스트")
    if st.button("API 연결 테스트 실행"):
        if not api_key:
            st.error("API 키가 설정되어 있지 않습니다.")
            return
            
        try:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello!"}],
                max_tokens=5
            )
            st.success("API 연결 테스트 성공!")
        except Exception as e:
            st.error(f"API 연결 테스트 실패: {str(e)}")

# 관리자 백업/복원 함수
def admin_backup_restore():
    st.header("백업 및 복원")
    
    # cryptography 패키지 체크
    crypto_available = is_package_available("cryptography")
    
    # 탭 생성
    tab1, tab2 = st.tabs(["백업", "복원"])
    
    # 백업 탭
    with tab1:
        st.subheader("데이터 백업")
        st.info("현재 시스템의 모든 데이터를 백업합니다.")
        
        # 백업 옵션
        include_users = st.checkbox("사용자 데이터 포함", value=True)
        include_problems = st.checkbox("문제 데이터 포함", value=True)
        include_records = st.checkbox("학습 기록 포함", value=True)
        include_repository = st.checkbox("문제 저장소 포함", value=True)
        
        # 파일 형식 선택
        file_format = st.radio("백업 파일 형식", ["JSON", "CSV"])
        
        # 암호화 옵션 (cryptography 라이브러리가 있는 경우에만)
        encrypt_backup = False
        encryption_key = ""
        
        if crypto_available and file_format == "JSON":
            encrypt_backup = st.checkbox("백업 파일 암호화", value=False)
            if encrypt_backup:
                encryption_key = st.text_input("암호화 키 (복원 시 필요)", type="password")
                if not encryption_key:
                    st.warning("암호화 키를 설정하세요. 이 키는 복원 시 반드시 필요합니다.")
        elif crypto_available and file_format == "CSV":
            st.info("CSV 형식은 암호화를 지원하지 않습니다.")
        else:
            if file_format == "JSON":
                st.warning("암호화 기능을 사용하려면 'cryptography' 라이브러리를 설치하세요: pip install cryptography")
        
        # 백업 버튼
        if st.button("백업 파일 생성"):
            if encrypt_backup and not encryption_key and file_format == "JSON":
                st.error("암호화를 위한 키를 입력해주세요.")
            else:
                # 백업 데이터 생성
                backup_data = {
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0"
                }
                
                if include_users:
                    backup_data["users"] = st.session_state.users
                
                if include_problems:
                    backup_data["teacher_problems"] = st.session_state.teacher_problems
                
                if include_records:
                    backup_data["student_records"] = st.session_state.student_records
                
                if include_repository:
                    backup_data["problem_repository"] = st.session_state.problem_repository
                
                if file_format == "JSON":
                    # JSON 형식으로 백업
                    backup_json = json.dumps(backup_data, indent=2)
                    
                    # 필요한 경우 암호화
                    if encrypt_backup and crypto_available:
                        try:
                            import base64
                            from cryptography.fernet import Fernet
                            from cryptography.hazmat.primitives import hashes
                            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
                            
                            # 비밀번호로부터 키 생성
                            salt = b'salt_'  # 실제 운영에서는 랜덤 솔트 사용
                            kdf = PBKDF2HMAC(
                                algorithm=hashes.SHA256(),
                                length=32,
                                salt=salt,
                                iterations=100000
                            )
                            key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
                            f = Fernet(key)
                            encrypted_backup = f.encrypt(backup_json.encode())
                            
                            # 암호화된 백업 파일 다운로드
                            st.download_button(
                                label="암호화된 백업 파일 다운로드",
                                data=encrypted_backup,
                                file_name=f"backup_encrypted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/octet-stream"
                            )
                        except Exception as e:
                            st.error(f"암호화 중 오류 발생: {str(e)}")
                            st.info("일반 백업 파일로 다운로드합니다.")
                            st.download_button(
                                label="백업 파일 다운로드",
                                data=backup_json,
                                file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json"
                            )
                    else:
                        # 일반 백업 파일 다운로드
                        st.download_button(
                            label="백업 파일 다운로드",
                            data=backup_json,
                            file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                else:
                    # CSV 형식으로 백업
                    try:
                        import pandas as pd
                        import io
                        
                        # 각 데이터를 DataFrame으로 변환
                        dfs = {}
                        if include_users:
                            users_df = pd.DataFrame.from_dict(st.session_state.users, orient='index')
                            dfs['users'] = users_df
                        
                        if include_problems:
                            problems_df = pd.DataFrame.from_dict(st.session_state.teacher_problems, orient='index')
                            dfs['problems'] = problems_df
                        
                        if include_records:
                            records_df = pd.DataFrame.from_dict(st.session_state.student_records, orient='index')
                            dfs['records'] = records_df
                        
                        if include_repository:
                            repository_df = pd.DataFrame(st.session_state.problem_repository.get('problems', []))
                            dfs['repository'] = repository_df
                        
                        # CSV 파일 생성
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            for name, df in dfs.items():
                                df.to_excel(writer, sheet_name=name)
                        
                        # 다운로드 버튼
                        st.download_button(
                            label="CSV 백업 파일 다운로드",
                            data=output.getvalue(),
                            file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.error(f"CSV 파일 생성 중 오류 발생: {str(e)}")
    
    # 복원 탭
    with tab2:
        st.subheader("데이터 복원")
        st.warning("경고: 복원 작업은 현재 데이터를 덮어쓰게 됩니다. 복원 전에 백업을 권장합니다.")
        
        # 파일 형식 선택
        restore_format = st.radio("복원 파일 형식", ["JSON", "CSV"])
        
        # 복원 파일 업로드
        if restore_format == "JSON":
            uploaded_file = st.file_uploader("백업 파일 선택", type=["json"])
        else:
            uploaded_file = st.file_uploader("백업 파일 선택", type=["xlsx"])
        
        # 암호화 옵션 (JSON 형식이고 cryptography 라이브러리가 있는 경우에만)
        is_encrypted = False
        decrypt_key = ""
        
        if crypto_available and restore_format == "JSON":
            is_encrypted = st.checkbox("암호화된 백업 파일")
            if is_encrypted:
                decrypt_key = st.text_input("암호화 키 입력", type="password")
        
        # 복원 옵션
        if uploaded_file is not None:
            st.info("복원할 데이터 선택:")
            restore_users = st.checkbox("사용자 데이터 복원", value=True)
            restore_problems = st.checkbox("문제 데이터 복원", value=True)
            restore_records = st.checkbox("학습 기록 복원", value=True)
            restore_repository = st.checkbox("문제 저장소 복원", value=True)
            
            if st.button("데이터 복원"):
                try:
                    if restore_format == "JSON":
                        # JSON 파일 복원
                        file_content = uploaded_file.read()
                        
                        # 암호화된 파일 복호화
                        if is_encrypted and crypto_available:
                            if not decrypt_key:
                                st.error("암호화된 파일을 복원하려면 암호화 키가 필요합니다.")
                                return
                            
                            try:
                                import base64
                                from cryptography.fernet import Fernet
                                from cryptography.hazmat.primitives import hashes
                                from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
                                
                                salt = b'salt_'
                                kdf = PBKDF2HMAC(
                                    algorithm=hashes.SHA256(),
                                    length=32,
                                    salt=salt,
                                    iterations=100000
                                )
                                key = base64.urlsafe_b64encode(kdf.derive(decrypt_key.encode()))
                                f = Fernet(key)
                                decrypted_content = f.decrypt(file_content)
                                backup_data = json.loads(decrypted_content)
                            except Exception as e:
                                st.error(f"복호화 실패: {str(e)}")
                                return
                        else:
                            backup_data = json.loads(file_content)
                        
                        # 데이터 복원
                        if restore_users and "users" in backup_data:
                            st.session_state.users = backup_data["users"]
                            save_users_data()
                        
                        if restore_problems and "teacher_problems" in backup_data:
                            st.session_state.teacher_problems = backup_data["teacher_problems"]
                            save_teacher_problems()
                        
                        if restore_records and "student_records" in backup_data:
                            st.session_state.student_records = backup_data["student_records"]
                            save_student_records()
                        
                        if restore_repository and "problem_repository" in backup_data:
                            st.session_state.problem_repository = backup_data["problem_repository"]
                            save_problem_repository()
                    else:
                        # CSV(Excel) 파일 복원
                        try:
                            import pandas as pd
                            
                            # Excel 파일 읽기
                            excel_data = pd.read_excel(uploaded_file, sheet_name=None)
                            
                            # 데이터 복원
                            if restore_users and 'users' in excel_data:
                                users_df = excel_data['users']
                                st.session_state.users = users_df.to_dict(orient='index')
                                save_users_data()
                            
                            if restore_problems and 'problems' in excel_data:
                                problems_df = excel_data['problems']
                                st.session_state.teacher_problems = problems_df.to_dict(orient='index')
                                save_teacher_problems()
                            
                            if restore_records and 'records' in excel_data:
                                records_df = excel_data['records']
                                st.session_state.student_records = records_df.to_dict(orient='index')
                                save_student_records()
                            
                            if restore_repository and 'repository' in excel_data:
                                repository_df = excel_data['repository']
                                st.session_state.problem_repository = {
                                    'problems': repository_df.to_dict(orient='records'),
                                    'metadata': {
                                        'last_updated': datetime.now().isoformat(),
                                        'version': '1.0'
                                    }
                                }
                                save_problem_repository()
                        except Exception as e:
                            st.error(f"CSV 파일 복원 중 오류 발생: {str(e)}")
                            return
                    
                    st.success("데이터가 성공적으로 복원되었습니다.")
                    st.info("변경사항을 적용하려면 앱을 새로고침하세요.")
                    
                    if st.button("앱 새로고침"):
                        st.rerun()
                    
                except Exception as e:
                    st.error(f"복원 중 오류 발생: {str(e)}")

# 패키지 가용성 체크 함수 추가
def is_package_available(package_name):
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False

# 앱 실행
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 오류 메시지 출력
        error_msg = f"오류가 발생했습니다: {str(e)}"
        traceback_str = traceback.format_exc()
        
        # 스트림릿이 사용 가능한 경우 오류 메시지 표시
        if 'st' in globals() and hasattr(st, 'error'):
            st.error(error_msg)
            st.error(traceback_str)
        else:
            # 콘솔에 오류 메시지 출력
            print(error_msg)
            print(traceback_str) 
