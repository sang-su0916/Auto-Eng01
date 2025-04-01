import os
import json
import datetime
import hashlib
import base64
import pickle
import time
import zipfile
import io
import re
from pathlib import Path
import uuid
import sys

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
    """평문 비밀번호가 해시된 비밀번호와 일치하는지 검증합니다."""
    if USING_PASSLIB and pbkdf2_sha256 and '$' in hashed_password:
        try:
            return pbkdf2_sha256.verify(plain_password, hashed_password)
        except Exception:
            # 실패하면 기본 방식으로 비교
            return hash_password(plain_password) == hashed_password
    else:
        # 기본 방식으로 비교
        return hash_password(plain_password) == hashed_password

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
        "created_at": datetime.datetime.now().isoformat(),
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
                            completed_at = datetime.datetime.fromisoformat(completed_at).strftime("%Y-%m-%d %H:%M:%S")
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
                            started_at = datetime.datetime.fromisoformat(started_at).strftime("%Y-%m-%d %H:%M:%S")
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
            "started_at": datetime.datetime.now().isoformat(),
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
                    problem_record["updated_at"] = datetime.datetime.now().isoformat()
                    
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
                        problem_record["completed_at"] = datetime.datetime.now().isoformat()
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
                    problem_record["updated_at"] = datetime.datetime.now().isoformat()
                    
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
                        problem_record["submitted_at"] = datetime.datetime.now().isoformat()
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
    # 이미 API 키가 설정되어 있으면 유지
    if 'openai_api_key' in st.session_state and st.session_state.openai_api_key:
        return
    
    # 1. config.json 파일에서 로드 시도
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config_data = json.load(f)
                
            if "api_keys" in config_data and "openai" in config_data["api_keys"]:
                # API 키 복호화 (간단한 디코딩)
                encoded_key = config_data["api_keys"]["openai"]
                try:
                    st.session_state.openai_api_key = base64.b64decode(encoded_key.encode()).decode()
                    return
                except Exception:
                    # 디코딩 실패 시 다음 방법으로 넘어감
                    pass
    except Exception:
        # 파일 로드 실패 시 다음 방법으로 넘어감
        pass
    
    # 2. .env 파일에서 로드 시도
    try:
        if os.path.exists(".env"):
            env_vars = {}
            with open(".env", "r") as f:
                for line in f:
                    if "=" in line:
                        key, value = line.strip().split("=", 1)
                        env_vars[key] = value
            
            if "OPENAI_API_KEY" in env_vars and env_vars["OPENAI_API_KEY"]:
                st.session_state.openai_api_key = env_vars["OPENAI_API_KEY"]
                return
    except Exception:
        # 파일 로드 실패 시 다음 방법으로 넘어감
        pass
    
    # 3. 환경 변수에서 로드 시도
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        st.session_state.openai_api_key = api_key
    else:
        # 모든 방법이 실패하면 빈 문자열 설정
        st.session_state.openai_api_key = ""

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
                            "created_at": problem.get("created_at", datetime.now().isoformat()),
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
    # 세션 상태 변수 초기화
    if "username" not in st.session_state:
        st.session_state.username = None
    
    # 필요한 디렉토리 생성
    os.makedirs("data", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)
    
    # 사용자 데이터 로드
    if 'users' not in st.session_state:
        load_users_data()
    
    # 초기 관리자 계정 생성 (필요한 경우)
    if not any(user.get("role") == "admin" for user in st.session_state.users.values()):
        # 기본 관리자 계정 생성
        admin_password = hash_password("admin123")
        st.session_state.users["admin"] = {
            "username": "admin",
            "password_hash": admin_password,
            "name": "관리자",
            "role": "admin",
            "email": "admin@example.com",
            "created_at": datetime.now().isoformat(),
            "created_by": "system"
        }
        save_users_data()
        
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

# 앱 실행
if __name__ == "__main__":
    main() 
