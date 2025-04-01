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
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    USING_PASSLIB = True
except ImportError:
    USING_PASSLIB = False
    pwd_context = None

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
    if USING_PASSLIB and pwd_context:
        try:
            return pwd_context.hash(password)
        except Exception:
            # 실패하면 기본 방식 사용
            return hashlib.sha256(password.encode()).hexdigest()
    else:
        return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password, hashed_password):
    """평문 비밀번호가 해시된 비밀번호와 일치하는지 검증합니다."""
    if USING_PASSLIB and pwd_context and '$' in hashed_password:
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            # 실패하면 기본 방식으로 비교
            return hash_password(plain_password) == hashed_password
    else:
        # 기본 방식으로 비교
        return hash_password(plain_password) == hashed_password

def save_users_data():
    with open("users.json", "w") as f:
        json.dump(st.session_state.users, f)

def load_users_data():
    try:
        with open("users.json", "r") as f:
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
    username, user_data = get_user_data()
    st.title(f"교사 대시보드 - {user_data['name']}님")
    
    # 사이드바 - 교사 메뉴
    st.sidebar.title("교사 메뉴")
    
    menu = st.sidebar.radio(
        "메뉴 선택:",
        ["내 정보", "학생 관리", "문제 출제", "문제 목록", "채점하기"]
    )
    
    # 로그아웃 버튼
    logout_button = st.sidebar.button("로그아웃")
    if logout_button:
        logout_user()
        st.rerun()
    
    if menu == "내 정보":
        st.header("내 정보")
        
        col1, col2 = st.columns(2)
        
        with col1:
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
    
    elif menu == "학생 관리":
        st.header("학생 관리")
        
        tab1, tab2 = st.tabs(["학생 등록", "학생 목록"])
        
        # 학생 등록 탭
        with tab1:
            st.subheader("새 학생 등록")
            
            student_username = st.text_input("학생 아이디:", key="new_student_username")
            student_name = st.text_input("학생 이름:", key="new_student_name")
            student_email = st.text_input("이메일 (선택):", key="new_student_email")
            student_password = st.text_input("비밀번호:", type="password", key="new_student_password")
            confirm_password = st.text_input("비밀번호 확인:", type="password", key="new_student_confirm")
            
            if st.button("학생 등록", key="register_new_student"):
                if not student_username or not student_name or not student_password:
                    st.error("학생 아이디, 이름, 비밀번호는 필수 입력사항입니다.")
                elif student_password != confirm_password:
                    st.error("비밀번호와 비밀번호 확인이 일치하지 않습니다.")
                elif student_username in st.session_state.users:
                    st.error(f"이미 존재하는 아이디입니다: {student_username}")
                elif len(student_password) < 6:
                    st.error("비밀번호는 최소 6자 이상이어야 합니다.")
                else:
                    # 학생 등록
                    success, message = register_user(
                        student_username, 
                        student_password, 
                        "student", 
                        student_name, 
                        student_email, 
                        created_by=username
                    )
                    
                    if success:
                        st.success(f"학생 '{student_name}'이(가) 성공적으로 등록되었습니다.")
                    else:
                        st.error(message)
        
        # 학생 목록 탭
        with tab2:
            st.subheader("등록된 학생 목록")
            
            # 해당 교사가 등록한 학생만 필터링
            student_list = []
            for student_id, student_data in st.session_state.users.items():
                if student_data.get("role") == "student" and student_data.get("created_by") == username:
                    student_list.append({
                        "아이디": student_id,
                        "이름": student_data.get("name", ""),
                        "이메일": student_data.get("email", ""),
                        "등록일": student_data.get("created_at", "")
                    })
            
            if student_list:
                df = pd.DataFrame(student_list)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("등록된 학생이 없습니다.")
            
            # 학생 삭제
            if student_list:
                st.subheader("학생 삭제")
                selected_student = st.selectbox(
                    "삭제할 학생 선택:",
                    [student["아이디"] for student in student_list],
                    format_func=lambda x: f"{x} ({st.session_state.users[x].get('name', '')})"
                )
                
                if selected_student:
                    confirm_delete = st.checkbox("삭제를 확인합니다")
                    
                    if st.button("선택한 학생 삭제") and confirm_delete:
                        # 학생 삭제
                        if selected_student in st.session_state.users:
                            del st.session_state.users[selected_student]
                            
                            # 학생 기록 삭제
                            if selected_student in st.session_state.student_records:
                                del st.session_state.student_records[selected_student]
                            
                            save_users_data()
                            # 학생 기록 저장
                            with open("student_records.json", "w") as f:
                                json.dump(st.session_state.student_records, f)
                                
                            st.success(f"학생 '{selected_student}'이(가) 삭제되었습니다.")
                            st.rerun()
    
    elif menu == "문제 출제":
        st.header("새 문제 출제")
        
        # 문제 출제 폼
        problem_title = st.text_input("문제 제목:")
        problem_description = st.text_area("문제 내용:", height=200)
        
        col1, col2 = st.columns(2)
        
        with col1:
            problem_level = st.selectbox("난이도:", ["초급", "중급", "고급"])
        
        with col2:
            expected_time = st.number_input("예상 풀이 시간(분):", min_value=1, max_value=120, value=10)
        
        if st.button("문제 저장"):
            if not problem_title or not problem_description:
                st.error("문제 제목과 내용을 모두 입력해주세요.")
            else:
                # 문제 ID 생성
                problem_id = f"p_{int(time.time())}_{username}"
                
                # 문제 데이터 저장
                st.session_state.teacher_problems[problem_id] = {
                    "title": problem_title,
                    "description": problem_description,
                    "level": problem_level,
                    "expected_time": expected_time,
                    "created_by": username,
                    "created_at": datetime.datetime.now().isoformat()
                }
                
                # 파일에 저장
                with open("teacher_problems.json", "w") as f:
                    json.dump(st.session_state.teacher_problems, f)
                
                st.success("문제가 성공적으로 저장되었습니다.")
    
    elif menu == "문제 목록":
        st.header("내 문제 목록")
        
        # 해당 교사가 출제한 문제만 필터링
        teacher_problem_list = []
        
        for problem_id, problem_data in st.session_state.teacher_problems.items():
            if problem_data.get("created_by") == username:
                # 채점 현황 계산
                solved_count = 0
                graded_count = 0
                
                for student_id, student_record in st.session_state.student_records.items():
                    for problem in student_record.get("solved_problems", []):
                        if problem.get("problem_id") == problem_id:
                            solved_count += 1
                            if "score" in problem:
                                graded_count += 1
                
                teacher_problem_list.append({
                    "problem_id": problem_id,
                    "title": problem_data.get("title", "제목 없음"),
                    "level": problem_data.get("level", "기본"),
                    "created_at": problem_data.get("created_at", ""),
                    "solved_count": solved_count,
                    "graded_count": graded_count
                })
        
        if not teacher_problem_list:
            st.info("출제한 문제가 없습니다. '문제 출제' 메뉴에서 새 문제를 출제해보세요.")
        else:
            # 정렬 옵션
            sort_option = st.selectbox(
                "정렬 방식:",
                ["최신순", "채점 필요순", "풀이 많은순"]
            )
            
            if sort_option == "최신순":
                teacher_problem_list = sorted(teacher_problem_list, key=lambda x: x["created_at"], reverse=True)
            elif sort_option == "채점 필요순":
                teacher_problem_list = sorted(teacher_problem_list, key=lambda x: x["solved_count"] - x["graded_count"], reverse=True)
            elif sort_option == "풀이 많은순":
                teacher_problem_list = sorted(teacher_problem_list, key=lambda x: x["solved_count"], reverse=True)
            
            # 문제 목록 표시
            problems_df = pd.DataFrame([
                {
                    "제목": p["title"],
                    "난이도": p["level"],
                    "풀이 수": p["solved_count"],
                    "채점완료": p["graded_count"],
                    "채점필요": p["solved_count"] - p["graded_count"],
                    "생성일": p["created_at"],
                    "problem_id": p["problem_id"]
                } for p in teacher_problem_list
            ])
            
            if not problems_df.empty:
                try:
                    # 날짜 포맷 변환
                    problems_df["생성일"] = pd.to_datetime(problems_df["생성일"]).dt.strftime("%Y-%m-%d")
                except:
                    pass
                
                st.dataframe(problems_df[["제목", "난이도", "풀이 수", "채점필요", "생성일"]], use_container_width=True)
            
                # 문제 상세 보기 및 수정
                st.subheader("문제 관리")
                
                selected_problem_idx = st.selectbox(
                    "관리할 문제 선택:",
                    range(len(teacher_problem_list)),
                    format_func=lambda x: f"{teacher_problem_list[x]['title']} ({teacher_problem_list[x]['level']})"
                )
                
                if selected_problem_idx is not None:
                    selected_problem_id = teacher_problem_list[selected_problem_idx]["problem_id"]
                    selected_problem = st.session_state.teacher_problems[selected_problem_id]
                    
                    tab1, tab2 = st.tabs(["문제 상세", "문제 수정"])
                    
                    with tab1:
                        st.markdown(f"### {selected_problem.get('title', '제목 없음')}")
                        st.markdown(f"**난이도:** {selected_problem.get('level', '기본')}")
                        st.markdown(f"**예상 시간:** {selected_problem.get('expected_time', 10)}분")
                        
                        st.markdown("### 문제 내용")
                        st.write(selected_problem.get("description", "문제 내용이 없습니다."))
                        
                        # 풀이 통계
                        st.markdown("### 풀이 통계")
                        solved_count = teacher_problem_list[selected_problem_idx]["solved_count"]
                        graded_count = teacher_problem_list[selected_problem_idx]["graded_count"]
                        
                        st.write(f"- **총 풀이 수:** {solved_count}")
                        st.write(f"- **채점 완료:** {graded_count}")
                        st.write(f"- **채점 필요:** {solved_count - graded_count}")
                        
                        if solved_count > 0:
                            # 학생별 풀이 현황
                            st.markdown("### 학생별 풀이 현황")
                            
                            student_solutions = []
                            for student_id, student_record in st.session_state.student_records.items():
                                for problem in student_record.get("solved_problems", []):
                                    if problem.get("problem_id") == selected_problem_id:
                                        student_name = st.session_state.users.get(student_id, {}).get("name", "알 수 없음")
                                        
                                        student_solutions.append({
                                            "학생 ID": student_id,
                                            "학생 이름": student_name,
                                            "제출 시간": problem.get("solved_at", ""),
                                            "점수": problem.get("score", "채점 중"),
                                            "채점 상태": "완료" if "score" in problem else "필요",
                                            "problem_index": problem  # 실제 problem 객체를 저장
                                        })
                            
                            if student_solutions:
                                solutions_df = pd.DataFrame(student_solutions)
                                
                                try:
                                    # 날짜 포맷 변환
                                    solutions_df["제출 시간"] = pd.to_datetime(solutions_df["제출 시간"]).dt.strftime("%Y-%m-%d %H:%M")
                                except:
                                    pass
                                
                                st.dataframe(solutions_df[["학생 이름", "제출 시간", "점수", "채점 상태"]], use_container_width=True)
                            else:
                                st.info("아직 풀이 기록이 없습니다.")
                    
                    with tab2:
                        st.subheader("문제 수정")
                        
                        edited_title = st.text_input("문제 제목:", value=selected_problem.get("title", ""))
                        edited_description = st.text_area("문제 내용:", value=selected_problem.get("description", ""), height=200)
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            edited_level = st.selectbox(
                                "난이도:", 
                                ["초급", "중급", "고급"], 
                                index=["초급", "중급", "고급"].index(selected_problem.get("level", "중급"))
                            )
                        
                        with col2:
                            edited_time = st.number_input(
                                "예상 풀이 시간(분):", 
                                min_value=1, 
                                max_value=120, 
                                value=selected_problem.get("expected_time", 10)
                            )
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("수정 사항 저장"):
                                if not edited_title or not edited_description:
                                    st.error("문제 제목과 내용을 모두 입력해주세요.")
                                else:
                                    # 문제 데이터 업데이트
                                    st.session_state.teacher_problems[selected_problem_id].update({
                                        "title": edited_title,
                                        "description": edited_description,
                                        "level": edited_level,
                                        "expected_time": edited_time,
                                        "updated_at": datetime.datetime.now().isoformat()
                                    })
                                    
                                    # 파일에 저장
                                    with open("teacher_problems.json", "w") as f:
                                        json.dump(st.session_state.teacher_problems, f)
                                    
                                    st.success("문제가 성공적으로 수정되었습니다.")
                        
                        with col2:
                            if st.button("문제 삭제"):
                                # 문제를 바로 삭제하지 않고 삭제 마킹만 함
                                st.session_state.teacher_problems[selected_problem_id]["is_deleted"] = True
                                
                                # 파일에 저장
                                with open("teacher_problems.json", "w") as f:
                                    json.dump(st.session_state.teacher_problems, f)
                                
                                st.success("문제가 삭제되었습니다.")
                                st.rerun()
    
    elif menu == "채점하기":
        st.header("채점하기")
        
        # 채점이 필요한 답변 찾기
        ungraded_answers = []
        
        for student_id, student_record in st.session_state.student_records.items():
            for problem_idx, problem in enumerate(student_record.get("solved_problems", [])):
                if "score" not in problem:  # 채점되지 않은 답변
                    problem_id = problem.get("problem_id", "")
                    problem_data = st.session_state.teacher_problems.get(problem_id, {})
                    
                    # 해당 교사가 출제한 문제인 경우만 포함
                    if problem_data.get("created_by") == username:
                        student_name = st.session_state.users.get(student_id, {}).get("name", "알 수 없음")
                        
                        ungraded_answers.append({
                            "student_id": student_id,
                            "student_name": student_name,
                            "problem_id": problem_id,
                            "problem_title": problem_data.get("title", "삭제된 문제"),
                            "answer": problem.get("answer", ""),
                            "solved_at": problem.get("solved_at", ""),
                            "problem_index": problem_idx  # student_records에서의 인덱스
                        })
        
        if not ungraded_answers:
            st.info("채점할 답변이 없습니다.")
        else:
            # 채점할 답변 선택
            st.subheader("채점할 답변 선택")
            
            # 정렬 옵션
            sort_option = st.selectbox(
                "정렬 방식:",
                ["최신 제출순", "학생 이름순", "문제 제목순"]
            )
            
            if sort_option == "최신 제출순":
                ungraded_answers = sorted(ungraded_answers, key=lambda x: x["solved_at"], reverse=True)
            elif sort_option == "학생 이름순":
                ungraded_answers = sorted(ungraded_answers, key=lambda x: x["student_name"])
            elif sort_option == "문제 제목순":
                ungraded_answers = sorted(ungraded_answers, key=lambda x: x["problem_title"])
            
            # 답변 목록 표시
            ungraded_df = pd.DataFrame([
                {
                    "학생 이름": a["student_name"],
                    "문제 제목": a["problem_title"],
                    "제출 시간": a["solved_at"],
                    "answer_id": i  # 목록에서의 인덱스
                } for i, a in enumerate(ungraded_answers)
            ])
            
            try:
                # 날짜 포맷 변환
                ungraded_df["제출 시간"] = pd.to_datetime(ungraded_df["제출 시간"]).dt.strftime("%Y-%m-%d %H:%M")
            except:
                pass
            
            st.dataframe(ungraded_df[["학생 이름", "문제 제목", "제출 시간"]], use_container_width=True)
            
            # 채점할 답변 선택
            selected_answer_idx = st.selectbox(
                "채점할 답변 선택:",
                range(len(ungraded_answers)),
                format_func=lambda x: f"{ungraded_answers[x]['student_name']} - {ungraded_answers[x]['problem_title']}"
            )
            
            if selected_answer_idx is not None:
                selected_answer = ungraded_answers[selected_answer_idx]
                
                st.subheader(f"채점: {selected_answer['problem_title']}")
                st.subheader(f"학생: {selected_answer['student_name']}")
                
                # 문제 내용 표시
                problem_data = st.session_state.teacher_problems.get(selected_answer["problem_id"], {})
                
                with st.expander("문제 내용 보기", expanded=True):
                    st.write(problem_data.get("description", "문제 내용이 없습니다."))
                
                # 학생 답변 표시
                st.subheader("학생 답변")
                st.write(selected_answer["answer"])
                
                # 채점 입력
                st.subheader("채점")
                
                score = st.slider("점수:", min_value=0, max_value=100, value=80, step=5)
                feedback = st.text_area("피드백:", height=150)
                
                # 자동 피드백 생성 버튼 (선택 사항)
                if st.button("AI 피드백 생성"):
                    try:
                        if st.session_state.openai_api_key:
                            with st.spinner("피드백 생성 중..."):
                                generated_feedback = generate_feedback(
                                    problem_data.get("description", ""), 
                                    selected_answer["answer"], 
                                    score
                                )
                                feedback = generated_feedback
                                st.session_state.generated_feedback = generated_feedback
                                st.rerun()
                        else:
                            st.error("OpenAI API 키가 설정되지 않았습니다. 관리자 설정에서 API 키를 설정해주세요.")
                    except Exception as e:
                        st.error(f"피드백 생성 중 오류가 발생했습니다: {e}")
                
                # 이전에 생성된 피드백 표시
                if "generated_feedback" in st.session_state:
                    feedback = st.session_state.generated_feedback
                
                if st.button("채점 완료"):
                    if not feedback:
                        st.warning("피드백을 입력해주세요.")
                    else:
                        # 채점 결과 저장
                        student_id = selected_answer["student_id"]
                        problem_index = selected_answer["problem_index"]
                        
                        st.session_state.student_records[student_id]["solved_problems"][problem_index].update({
                            "score": score,
                            "feedback": feedback,
                            "graded_by": username,
                            "graded_at": datetime.datetime.now().isoformat()
                        })
                        
                        # 파일에 저장
                        with open("student_records.json", "w") as f:
                            json.dump(st.session_state.student_records, f)
                        
                        # 상태 초기화
                        if "generated_feedback" in st.session_state:
                            del st.session_state.generated_feedback
                        
                        st.success("채점이 완료되었습니다.")
                        st.rerun()

def generate_feedback(problem, answer, score):
    """피드백을 생성합니다."""
    # OpenAI API가 없거나 API 키가 없으면 기본 피드백 사용
    if not has_openai or not st.session_state.openai_api_key:
        return generate_default_feedback(score, answer)
    
    try:
        client = openai.OpenAI(api_key=st.session_state.openai_api_key)
        
        prompt = f"""
        문제: {problem}
        
        학생 답변: {answer}
        
        점수: {score}/100
        
        위 영어 문제와 학생의 답변을 바탕으로 교사의 입장에서 피드백을 작성해주세요.
        
        피드백은 다음 요소를 포함해야 합니다:
        1. 잘한 점
        2. 개선이 필요한 점
        3. 점수에 맞는 종합적인 평가
        4. 추가 학습을 위한 조언
        
        한국어로 작성해주세요. 응원과 격려의 메시지도 포함해주세요.
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful English teacher providing feedback to students."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        st.warning(f"API 호출 중 오류가 발생했습니다: {str(e)}")
        return generate_default_feedback(score, answer)

def generate_default_feedback(score, answer):
    """점수에 따른 기본 피드백을 생성합니다."""
    answer_length = len(answer.split())
    
    if score >= 90:
        return f"""
        🌟 피드백 🌟
        
        잘한 점:
        - 문제를 정확하게 이해하고 적절한 답변을 제공했습니다. ({answer_length}단어 작성)
        - 영어 표현이 자연스럽고 문법적으로 정확합니다.
        
        개선할 점:
        - 조금 더 다양한 어휘를 사용하면 표현이 풍부해질 것입니다.
        
        종합 평가:
        {score}점의 우수한 성적을 받았습니다. 앞으로도 이런 수준을 유지하시기 바랍니다.
        
        조언:
        영어 독서량을 늘려 더 다양한 표현을 익히면 좋겠습니다.
        """
    elif score >= 70:
        return f"""
        🌟 피드백 🌟
        
        잘한 점:
        - 문제의 주요 내용을 이해하고 적절히 대응했습니다. ({answer_length}단어 작성)
        - 기본적인 영어 표현을 잘 사용했습니다.
        
        개선할 점:
        - 문법적인 오류가 일부 있습니다.
        - 더 구체적인 예시를 들면 좋겠습니다.
        
        종합 평가:
        {score}점으로 양호한 수준입니다. 조금만 더 노력하면 더 좋은 결과를 얻을 수 있을 것입니다.
        
        조언:
        기본 문법을 복습하고, 영어로 일기를 써보는 연습을 해보세요.
        """
    else:
        return f"""
        🌟 피드백 🌟
        
        잘한 점:
        - 문제에 대한 답변을 시도했습니다. ({answer_length}단어 작성)
        - 기본적인 의사 전달은 가능한 수준입니다.
        
        개선할 점:
        - 문법적인 오류가 많이 발견됩니다.
        - 문제의 핵심을 더 정확하게 파악할 필요가 있습니다.
        
        종합 평가:
        {score}점으로 기본기를 더 다질 필요가 있습니다. 지속적인 연습이 필요합니다.
        
        조언:
        기초 영어 문법을 체계적으로 복습하고, 기본 문장 구조를 익히는 연습을 해보세요.
        영어 학습에 더 많은 시간을 투자하면 좋겠습니다.
        """

# Main
def main():
    # 세션 상태 초기화
    if "users" not in st.session_state:
        st.session_state.users = {}
    
    if "teacher_problems" not in st.session_state:
        st.session_state.teacher_problems = {}
    
    if "student_records" not in st.session_state:
        st.session_state.student_records = {}
    
    # 데이터 로드
    load_users_data()
    
    try:
        with open("teacher_problems.json", "r") as f:
            st.session_state.teacher_problems = json.load(f)
    except FileNotFoundError:
        st.session_state.teacher_problems = {}
    
    try:
        with open("student_records.json", "r") as f:
            st.session_state.student_records = json.load(f)
    except FileNotFoundError:
        st.session_state.student_records = {}
    
    # OpenAI API 키 설정
    if "openai_api_key" not in st.session_state:
        st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
    
    # 초기 관리자 계정 생성 (필요한 경우)
    if not any(user.get("role") == "admin" for user in st.session_state.users.values()):
        register_user("admin", "admin123", "admin", "관리자", created_by="system")
    
    # 문제 풀이 모드인 경우
    if st.session_state.get("solving_mode", False) and st.session_state.get("current_problem_id"):
        display_and_solve_problem()
        return
    
    # 로그인 상태 확인
    if not st.session_state.username:
        login_page()
    else:
        # 사용자 역할에 따른 대시보드 표시
        user_role = st.session_state.users[st.session_state.username].get("role")
        
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

def login_page():
    st.title("English Auto-Grading System")
    st.markdown("#### 영어 자동 채점 시스템")
    
    # 사용법 설명을 숨김 장치로 구현
    with st.expander("💡 시스템 사용법 (클릭하여 펼치기/접기)"):
        st.markdown("""
        ### 📌 시스템 사용 안내
        
        #### 👨‍🏫 교사용 계정
        - **문제 출제**: 다양한 난이도의 영어 문제를 출제할 수 있습니다.
        - **채점 관리**: 학생들이 제출한 답변을 검토하고 점수를 부여할 수 있습니다.
        - **학생 관리**: 학생 계정을 생성하고 학습 진행 상황을 모니터링할 수 있습니다.
        
        #### 👨‍🎓 학생용 계정
        - **문제 풀기**: 교사가 출제한 문제를 선택하여 풀 수 있습니다.
        - **결과 확인**: 제출한 답변에 대한 채점 결과와 피드백을 확인할 수 있습니다.
        - **학습 통계**: 자신의 학습 진행 상황을 통계로 확인할 수 있습니다.
        
        #### 👨‍💼 관리자용 계정
        - **시스템 관리**: 전체 시스템 설정 및 사용자 관리를 수행할 수 있습니다.
        - **데이터 관리**: 데이터 백업 및 복원 기능을 사용할 수 있습니다.
        
        #### 기본 관리자 계정
        - 아이디: admin
        - 비밀번호: admin123
        """)
    
    tab1, tab2 = st.tabs(["로그인", "비밀번호 찾기"])
    
    with tab1:
        st.subheader("로그인")
        
        username = st.text_input("아이디:")
        password = st.text_input("비밀번호:", type="password")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            login_button = st.button("로그인", use_container_width=True)
        
        if login_button:
            if not username or not password:
                st.error("아이디와 비밀번호를 모두 입력해주세요.")
            elif username not in st.session_state.users:
                st.error("존재하지 않는 아이디입니다.")
            elif not verify_password(password, st.session_state.users[username]["password"]):
                st.error("비밀번호가 일치하지 않습니다.")
            else:
                st.session_state.username = username
                st.success(f"{st.session_state.users[username]['name']}님, 환영합니다!")
                st.rerun()
    
    with tab2:
        st.subheader("비밀번호 찾기")
        
        username = st.text_input("아이디:", key="reset_username")
        email = st.text_input("가입시 등록한 이메일:", key="reset_email")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            reset_button = st.button("비밀번호 재설정", use_container_width=True)
        
        if reset_button:
            if not username or not email:
                st.error("아이디와 이메일을 모두 입력해주세요.")
            elif username not in st.session_state.users:
                st.error("존재하지 않는 아이디입니다.")
            elif st.session_state.users[username].get("email", "") != email:
                st.error("등록된 이메일과 일치하지 않습니다.")
            else:
                # 실제로는 이메일 발송 로직이 필요하지만, 여기서는 간단히 처리
                new_password = "resetpw123"
                st.session_state.users[username]["password"] = hash_password(new_password)
                save_users_data()
                
                st.success(f"비밀번호가 재설정되었습니다. 임시 비밀번호: {new_password}")
                st.info("로그인 후 반드시 비밀번호를 변경해주세요.")

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
    
    st.info("이 페이지에서 OpenAI API 키를 설정할 수 있습니다. API 키는 암호화되지 않고 저장되므로 주의하세요.")
    
    # API 키 유지/리셋 옵션
    st.subheader("API 키 관리 옵션")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("API 키 유지하기"):
            st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
            st.success("API 키가 환경 변수에서 다시 로드되었습니다.")
    
    with col2:
        if st.button("API 키 초기화"):
            st.session_state.openai_api_key = ""
            try:
                with open(".env", "w") as f:
                    f.write("OPENAI_API_KEY=\n")
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
            st.success("OpenAI API 키가 저장되었습니다.")
        except Exception as e:
            st.error(f"API 키 저장 중 오류가 발생했습니다: {e}")
    
    st.markdown("---")
    
    # API 키 테스트
    st.subheader("API 키 테스트")
    
    if st.button("API 연결 테스트"):
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

def admin_backup_restore():
    st.header("백업 및 복원")
    
    tab1, tab2 = st.tabs(["백업", "복원"])
    
    # 백업 탭
    with tab1:
        st.subheader("시스템 백업")
        st.write("현재 시스템의 모든 데이터를 백업 파일로 다운로드합니다.")
        
        # 백업 포맷 선택
        backup_format = st.radio("백업 파일 형식:", ["JSON", "CSV"], horizontal=True)
        
        # 백업 데이터 준비
        backup_data = {
            "users": st.session_state.users,
            "teacher_problems": st.session_state.teacher_problems,
            "student_records": st.session_state.student_records,
            "backup_date": datetime.datetime.now().isoformat()
        }
        
        # 백업 파일 생성
        if st.button("백업 파일 생성"):
            try:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if backup_format == "JSON":
                    # JSON 백업 생성
                    backup_json = json.dumps(backup_data, indent=4)
                    
                    # 다운로드 버튼 표시
                    filename = f"auto_eng_backup_{timestamp}.json"
                    
                    st.download_button(
                        label="백업 파일 다운로드 (JSON)",
                        data=backup_json,
                        file_name=filename,
                        mime="application/json"
                    )
                else:  # CSV
                    # CSV 백업 생성 - 데이터를 평면화하여 CSV로 변환
                    buffer = io.BytesIO()
                    with zipfile.ZipFile(buffer, 'w') as zip_file:
                        # 사용자 데이터
                        users_df = pd.DataFrame.from_dict(st.session_state.users, orient='index')
                        users_csv = users_df.to_csv(index=True)
                        zip_file.writestr('users.csv', users_csv)
                        
                        # 문제 데이터
                        problems_df = pd.DataFrame.from_dict(st.session_state.teacher_problems, orient='index')
                        problems_csv = problems_df.to_csv(index=True)
                        zip_file.writestr('teacher_problems.csv', problems_csv)
                        
                        # 학생 기록 데이터 - 복잡한 구조이므로 JSON으로 저장
                        records_json = json.dumps(st.session_state.student_records)
                        zip_file.writestr('student_records.json', records_json)
                        
                        # 메타데이터
                        meta = {"backup_date": datetime.datetime.now().isoformat()}
                        meta_json = json.dumps(meta)
                        zip_file.writestr('metadata.json', meta_json)
                    
                    # 다운로드 버튼 표시
                    filename = f"auto_eng_backup_{timestamp}.zip"
                    
                    st.download_button(
                        label="백업 파일 다운로드 (CSV/ZIP)",
                        data=buffer.getvalue(),
                        file_name=filename,
                        mime="application/zip"
                    )
                
                st.success("백업 파일이 생성되었습니다. 위 버튼을 클릭하여 다운로드하세요.")
            except Exception as e:
                st.error(f"백업 파일 생성 중 오류가 발생했습니다: {e}")
    
    # 복원 탭
    with tab2:
        st.subheader("시스템 복원")
        st.warning("주의: 복원을 진행하면 현재 시스템의 모든 데이터가 백업 파일의 데이터로 대체됩니다.")
        
        # 파일 형식 선택
        restore_format = st.radio("복원 파일 형식:", ["JSON", "CSV/ZIP"], horizontal=True)
        
        # 파일 업로더
        if restore_format == "JSON":
            uploaded_file = st.file_uploader("백업 파일 업로드", type=["json"])
        else:
            uploaded_file = st.file_uploader("백업 파일 업로드", type=["zip"])
        
        if uploaded_file is not None:
            try:
                if restore_format == "JSON":
                    # JSON 파일 로드
                    backup_data = json.load(uploaded_file)
                    
                    # 백업 데이터 미리보기
                    st.subheader("백업 데이터 미리보기")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"**사용자 수:** {len(backup_data.get('users', {}))}")
                    
                    with col2:
                        st.write(f"**문제 수:** {len(backup_data.get('teacher_problems', {}))}")
                    
                    with col3:
                        st.write(f"**학생 기록 수:** {len(backup_data.get('student_records', {}))}")
                    
                    backup_date = backup_data.get("backup_date", "알 수 없음")
                    if backup_date != "알 수 없음":
                        try:
                            backup_date = datetime.datetime.fromisoformat(backup_date).strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            pass
                    
                    st.write(f"**백업 날짜:** {backup_date}")
                else:  # CSV/ZIP
                    # ZIP 파일 처리
                    with zipfile.ZipFile(uploaded_file) as zip_file:
                        # 메타데이터 확인
                        with zip_file.open('metadata.json') as f:
                            metadata = json.loads(f.read())
                            backup_date = metadata.get("backup_date", "알 수 없음")
                            if backup_date != "알 수 없음":
                                try:
                                    backup_date = datetime.datetime.fromisoformat(backup_date).strftime("%Y-%m-%d %H:%M:%S")
                                except:
                                    pass
                        
                        # 사용자 데이터 확인
                        with zip_file.open('users.csv') as f:
                            users_df = pd.read_csv(f, index_col=0)
                            user_count = len(users_df)
                        
                        # 문제 데이터 확인
                        with zip_file.open('teacher_problems.csv') as f:
                            problems_df = pd.read_csv(f, index_col=0)
                            problem_count = len(problems_df)
                        
                        # 학생 기록 데이터 확인
                        with zip_file.open('student_records.json') as f:
                            student_records = json.loads(f.read())
                            record_count = len(student_records)
                        
                        # 데이터 미리보기
                        st.subheader("백업 데이터 미리보기")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.write(f"**사용자 수:** {user_count}")
                        
                        with col2:
                            st.write(f"**문제 수:** {problem_count}")
                        
                        with col3:
                            st.write(f"**학생 기록 수:** {record_count}")
                        
                        st.write(f"**백업 날짜:** {backup_date}")
                
                # 복원 확인
                confirm_restore = st.checkbox("복원을 진행하시겠습니까? 현재 데이터가 모두 삭제됩니다.")
                
                if st.button("복원 진행") and confirm_restore:
                    if restore_format == "JSON":
                        # JSON 데이터 복원
                        st.session_state.users = backup_data.get("users", {})
                        st.session_state.teacher_problems = backup_data.get("teacher_problems", {})
                        st.session_state.student_records = backup_data.get("student_records", {})
                    else:  # CSV/ZIP
                        # ZIP 데이터 복원
                        with zipfile.ZipFile(uploaded_file) as zip_file:
                            # 사용자 데이터 복원
                            with zip_file.open('users.csv') as f:
                                users_df = pd.read_csv(f, index_col=0)
                                st.session_state.users = users_df.to_dict(orient='index')
                            
                            # 문제 데이터 복원
                            with zip_file.open('teacher_problems.csv') as f:
                                problems_df = pd.read_csv(f, index_col=0)
                                st.session_state.teacher_problems = problems_df.to_dict(orient='index')
                            
                            # 학생 기록 데이터 복원
                            with zip_file.open('student_records.json') as f:
                                st.session_state.student_records = json.loads(f.read())
                    
                    # 파일 저장
                    save_users_data()
                    
                    with open("teacher_problems.json", "w") as f:
                        json.dump(st.session_state.teacher_problems, f)
                    
                    with open("student_records.json", "w") as f:
                        json.dump(st.session_state.student_records, f)
                    
                    st.success("시스템 복원이 완료되었습니다.")
                    st.info("3초 후 페이지가 새로고침됩니다...")
                    
                    # 3초 후 페이지 새로고침
                    time.sleep(3)
                    st.rerun()
            
            except Exception as e:
                st.error(f"백업 파일 처리 중 오류가 발생했습니다: {e}")

def admin_system_info():
    st.header("시스템 정보")
    
    # 시스템 기본 정보
    st.subheader("기본 정보")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Streamlit 버전:** {st.__version__}")
        st.write(f"**Python 버전:** {os.sys.version.split()[0]}")
        st.write(f"**현재 시간:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    with col2:
        st.write(f"**사용자 수:** {len(st.session_state.users)}")
        st.write(f"**문제 수:** {len(st.session_state.teacher_problems)}")
        st.write(f"**학생 기록 수:** {len(st.session_state.student_records)}")
    
    # 데이터 통계
    st.subheader("데이터 통계")
    
    # 역할별 사용자 수
    role_counts = {"student": 0, "teacher": 0, "admin": 0}
    for user in st.session_state.users.values():
        role = user.get("role", "")
        if role in role_counts:
            role_counts[role] += 1
    
    # 데이터 프레임으로 표시
    role_df = pd.DataFrame({
        "역할": ["학생", "교사", "관리자"],
        "사용자 수": [role_counts["student"], role_counts["teacher"], role_counts["admin"]]
    })
    
    st.bar_chart(role_df.set_index("역할"))
    
    # 시스템 상태
    st.subheader("시스템 파일 상태")
    
    file_status = []
    
    # 파일 존재 확인
    for file_name in ["users.json", "teacher_problems.json", "student_records.json"]:
        file_exists = os.path.exists(file_name)
        file_size = os.path.getsize(file_name) if file_exists else 0
        file_modify_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_name)).strftime("%Y-%m-%d %H:%M:%S") if file_exists else "-"
        
        file_status.append({
            "파일명": file_name,
            "존재 여부": "O" if file_exists else "X",
            "파일 크기": f"{file_size} bytes" if file_exists else "-",
            "수정 시간": file_modify_time
        })
    
    st.table(pd.DataFrame(file_status))
    
    # 데이터 초기화 옵션
    st.subheader("데이터 초기화")
    st.warning("주의: 데이터 초기화는 복구할 수 없습니다. 초기화 전에 반드시 백업하세요.")
    
    reset_options = st.multiselect(
        "초기화할 데이터 선택:",
        ["사용자 데이터", "문제 데이터", "학생 기록 데이터"]
    )
    
    confirm_reset = st.checkbox("초기화를 확인합니다. 이 작업은 되돌릴 수 없습니다.")
    
    if st.button("선택한 데이터 초기화") and confirm_reset and reset_options:
        if "사용자 데이터" in reset_options:
            # 관리자 계정은 유지
            admin_accounts = {k: v for k, v in st.session_state.users.items() if v.get("role") == "admin"}
            st.session_state.users = admin_accounts
            save_users_data()
        
        if "문제 데이터" in reset_options:
            st.session_state.teacher_problems = {}
            with open("teacher_problems.json", "w") as f:
                json.dump({}, f)
        
        if "학생 기록 데이터" in reset_options:
            st.session_state.student_records = {}
            with open("student_records.json", "w") as f:
                json.dump({}, f)
        
        st.success(f"선택한 데이터 ({', '.join(reset_options)})가 초기화되었습니다.")
        st.info("3초 후 페이지가 새로고침됩니다...")
        
        # 3초 후 페이지 새로고침
        time.sleep(3)
        st.rerun()

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

def student_dashboard():
    st.title(f"학생 대시보드 - {st.session_state.users[st.session_state.username]['name']}님")
    
    # 사이드바 - 학생 메뉴
    st.sidebar.title("학생 메뉴")
    
    menu = st.sidebar.radio(
        "메뉴 선택:",
        ["내 정보", "문제 풀기", "내 기록"]
    )
    
    if menu == "내 정보":
        student_my_info()
    elif menu == "문제 풀기":
        student_problem_solving()
    elif menu == "내 기록":
        student_records_view()
    
    # 로그아웃 버튼
    logout_button = st.sidebar.button("로그아웃")
    if logout_button:
        logout_user()
        st.rerun()

def student_my_info():
    st.header("내 정보")
    
    user_data = st.session_state.users[st.session_state.username]
    
    # 정보 표시
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("기본 정보")
        st.write(f"**이름:** {user_data.get('name', '')}")
        st.write(f"**아이디:** {st.session_state.username}")
        st.write(f"**이메일:** {user_data.get('email', '')}")
    
    with col2:
        st.subheader("통계")
        
        # 학생 기록 불러오기
        student_records = st.session_state.student_records.get(st.session_state.username, {})
        
        # 기본 통계 계산
        problems_attempted = len(student_records.get("problems", {}))
        problems_completed = sum(1 for problem in student_records.get("problems", {}).values() 
                               if problem.get("status") == "completed")
        
        total_score = sum(problem.get("score", 0) for problem in student_records.get("problems", {}).values() 
                         if problem.get("status") == "completed")
        
        if problems_completed > 0:
            average_score = total_score / problems_completed
        else:
            average_score = 0
        
        st.write(f"**시도한 문제 수:** {problems_attempted}")
        st.write(f"**완료한 문제 수:** {problems_completed}")
        st.write(f"**평균 점수:** {average_score:.1f}")
    
    # 비밀번호 변경
    st.markdown("---")
    st.subheader("비밀번호 변경")
    
    col1, col2 = st.columns(2)
    
    with col1:
        current_password = st.text_input("현재 비밀번호:", type="password")
    
    with col2:
        new_password = st.text_input("새 비밀번호:", type="password")
        confirm_password = st.text_input("새 비밀번호 확인:", type="password")
    
    if st.button("비밀번호 변경"):
        if not current_password or not new_password or not confirm_password:
            st.error("모든 필드를 입력해주세요.")
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
    
    col1, col2, col3 = st.columns(3)
    
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
        
        problem_options.append(f"{problem.get('title')} - {teacher_name} - {problem.get('difficulty', '중간')} [{status}{score}]")
    
    selected_problem_idx = st.selectbox(
        "문제 선택:",
        range(len(problem_options)),
        format_func=lambda x: problem_options[x]
    )
    
    selected_problem_id = list(filtered_problems.keys())[selected_problem_idx]
    selected_problem = filtered_problems[selected_problem_id]
    
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
    problem_id = st.session_state.problem_solving_id
    
    # 문제 정보 가져오기
    problem_data = st.session_state.teacher_problems.get(problem_id, {})
    
    if not problem_data:
        st.error("문제 정보를 찾을 수 없습니다.")
        if st.button("돌아가기"):
            st.session_state.pop("problem_solving_id", None)
            st.rerun()
        return
    
    # 학생 기록 확인/초기화
    if st.session_state.username not in st.session_state.student_records:
        st.session_state.student_records[st.session_state.username] = {"problems": {}}
    
    student_records = st.session_state.student_records[st.session_state.username]
    
    if "problems" not in student_records:
        student_records["problems"] = {}
    
    # 문제 상태 확인
    is_completed = False
    student_answer = ""
    
    if problem_id in student_records["problems"]:
        problem_record = student_records["problems"][problem_id]
        
        if problem_record.get("status") == "completed":
            is_completed = True
        else:
            # 진행 중인 문제면 답변 불러오기
            student_answer = problem_record.get("answer", "")
    else:
        # 새 문제면 기록 초기화
        student_records["problems"][problem_id] = {
            "status": "in_progress",
            "started_at": datetime.datetime.now().isoformat(),
            "answer": ""
        }
    
    # 문제 화면 표시
    teacher_name = st.session_state.users.get(problem_data.get("created_by", ""), {}).get("name", "알 수 없음")
    
    st.title(f"문제: {problem_data.get('title', '제목 없음')}")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.write(f"**출제자:** {teacher_name}")
    
    with col2:
        st.write(f"**난이도:** {problem_data.get('difficulty', '중간')}")
    
    with col3:
        if is_completed:
            st.write(f"**점수:** {student_records['problems'][problem_id].get('score', 0)}")
    
    st.markdown("---")
    
    # 문제 내용 표시
    st.subheader("문제 내용")
    st.write(problem_data.get("description", "내용 없음"))
    
    # 문제가 이미 완료되었다면, 결과만 표시
    if is_completed:
        st.success("이 문제는 이미 제출하여 평가되었습니다.")
        
        st.subheader("나의 답변")
        st.write(student_records["problems"][problem_id].get("answer", ""))
        
        st.subheader("평가 결과")
        st.write(f"**점수:** {student_records['problems'][problem_id].get('score', 0)}")
        
        st.subheader("피드백")
        st.write(student_records["problems"][problem_id].get("feedback", "피드백 없음"))
        
        if st.button("문제 목록으로 돌아가기"):
            st.session_state.pop("problem_solving_id", None)
            st.rerun()
        
        return
    
    # 답변 입력 영역
    st.subheader("답변 작성")
    
    answer = st.text_area("답변을 작성하세요:", height=200, value=student_answer)
    
    # 임시 저장
    if answer != student_answer and answer.strip():
        student_records["problems"][problem_id]["answer"] = answer
        with open("student_records.json", "w") as f:
            json.dump(st.session_state.student_records, f)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("임시 저장"):
            if not answer.strip():
                st.error("답변을 작성해주세요.")
            else:
                student_records["problems"][problem_id]["answer"] = answer
                with open("student_records.json", "w") as f:
                    json.dump(st.session_state.student_records, f)
                st.success("답변이 임시 저장되었습니다.")
    
    with col2:
        if st.button("제출하기"):
            if not answer.strip():
                st.error("답변을 작성해주세요.")
            else:
                # 답변 제출 - 교사가 채점할 때까지 completed 상태가 아님
                student_records["problems"][problem_id]["answer"] = answer
                student_records["problems"][problem_id]["submitted_at"] = datetime.datetime.now().isoformat()
                student_records["problems"][problem_id]["status"] = "submitted"
                
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

# 앱 실행
if __name__ == "__main__":
    main() 
