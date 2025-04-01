import streamlit as st
import os
import json
import datetime
import pandas as pd
import openai
import hashlib
import base64
import pickle
import time
import zipfile
import io
import re
from pathlib import Path

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
    return hashlib.sha256(password.encode()).hexdigest()

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

def admin_backup_restore():
    st.header("백업 및 복원")
    
    tab1, tab2 = st.tabs(["백업", "복원"])
    
    # 백업 탭
    with tab1:
        st.subheader("시스템 백업")
        st.write("현재 시스템의 모든 데이터를 백업 파일로 다운로드합니다.")
        
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
                # JSON 백업 생성
                backup_json = json.dumps(backup_data, indent=4)
                
                # 다운로드 버튼 표시
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"auto_eng_backup_{timestamp}.json"
                
                st.download_button(
                    label="백업 파일 다운로드",
                    data=backup_json,
                    file_name=filename,
                    mime="application/json"
                )
                
                st.success("백업 파일이 생성되었습니다. 위 버튼을 클릭하여 다운로드하세요.")
            except Exception as e:
                st.error(f"백업 파일 생성 중 오류가 발생했습니다: {e}")
    
    # 복원 탭
    with tab2:
        st.subheader("시스템 복원")
        st.warning("주의: 복원을 진행하면 현재 시스템의 모든 데이터가 백업 파일의 데이터로 대체됩니다.")
        
        uploaded_file = st.file_uploader("백업 파일 업로드", type=["json"])
        
        if uploaded_file is not None:
            try:
                # 백업 파일 로드
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
                
                # 복원 확인
                confirm_restore = st.checkbox("복원을 진행하시겠습니까? 현재 데이터가 모두 삭제됩니다.")
                
                if st.button("복원 진행") and confirm_restore:
                    # 데이터 복원
                    st.session_state.users = backup_data.get("users", {})
                    st.session_state.teacher_problems = backup_data.get("teacher_problems", {})
                    st.session_state.student_records = backup_data.get("student_records", {})
                    
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

def student_dashboard():
    username, user_data = get_user_data()
    st.title(f"학생 대시보드 - {user_data['name']}님")
    
    # 사이드바 - 학생 메뉴
    st.sidebar.title("학생 메뉴")
    
    menu = st.sidebar.radio(
        "메뉴 선택:",
        ["내 정보", "문제 풀기", "내 기록"]
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
            # 학생 통계
            st.subheader("학습 통계")
            
            # 학생 기록 가져오기
            student_record = st.session_state.student_records.get(username, {})
            solved_problems = student_record.get("solved_problems", [])
            
            # 푼 문제 수
            st.write(f"**푼 문제 수:** {len(solved_problems)}")
            
            # 평균 점수 계산
            total_score = 0
            graded_count = 0
            
            for problem in solved_problems:
                if "score" in problem:
                    total_score += problem["score"]
                    graded_count += 1
            
            avg_score = total_score / graded_count if graded_count > 0 else 0
            st.write(f"**평균 점수:** {avg_score:.1f}점")
            
            # 학습 시간
            total_time = sum([problem.get("time_spent", 0) for problem in solved_problems])
            st.write(f"**총 학습 시간:** {total_time//60}분 {total_time%60}초")
        
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
    
    elif menu == "문제 풀기":
        view_teacher_problems()
    
    elif menu == "내 기록":
        st.header("내 학습 기록")
        
        # 학생 기록 가져오기
        student_record = st.session_state.student_records.get(username, {})
        solved_problems = student_record.get("solved_problems", [])
        
        if not solved_problems:
            st.info("아직 푼 문제가 없습니다. '문제 풀기' 메뉴에서 문제를 풀어보세요.")
        else:
            # 문제 목록 표시
            problem_list = []
            
            for idx, problem in enumerate(solved_problems):
                problem_id = problem.get("problem_id", "")
                problem_data = st.session_state.teacher_problems.get(problem_id, {})
                
                problem_list.append({
                    "번호": idx + 1,
                    "제목": problem_data.get("title", "삭제된 문제"),
                    "점수": problem.get("score", "채점 중"),
                    "풀이 날짜": problem.get("solved_at", ""),
                    "채점 상태": "채점 완료" if "score" in problem else "채점 중",
                    "problem_id": problem_id
                })
            
            # 데이터프레임으로 변환하여 표시
            df = pd.DataFrame(problem_list)
            display_df = df[["번호", "제목", "점수", "풀이 날짜", "채점 상태"]]
            
            st.dataframe(display_df, use_container_width=True)
            
            # 문제 상세 보기
            selected_idx = st.selectbox(
                "상세 정보를 볼 문제를 선택하세요:",
                range(len(problem_list)),
                format_func=lambda x: f"{problem_list[x]['번호']}. {problem_list[x]['제목']}"
            )
            
            if selected_idx is not None:
                selected_problem = solved_problems[selected_idx]
                problem_id = selected_problem.get("problem_id", "")
                problem_data = st.session_state.teacher_problems.get(problem_id, {})
                
                st.subheader(f"문제: {problem_data.get('title', '삭제된 문제')}")
                
                # 문제 정보 표시
                st.markdown("**문제 설명:**")
                st.write(problem_data.get("description", "문제 내용이 없습니다."))
                
                st.markdown("**내 답변:**")
                st.write(selected_problem.get("answer", "답변 내용이 없습니다."))
                
                if "feedback" in selected_problem:
                    st.markdown("**피드백:**")
                    st.write(selected_problem.get("feedback", ""))
                
                if "score" in selected_problem:
                    st.markdown(f"**점수:** {selected_problem['score']}점")

def view_teacher_problems():
    st.header("문제 풀기")
    
    # 모든 문제 목록 가져오기
    problem_list = []
    
    for problem_id, problem_data in st.session_state.teacher_problems.items():
        # 삭제된 문제는 제외
        if problem_data.get("is_deleted", False):
            continue
        
        teacher_id = problem_data.get("created_by", "")
        teacher_name = st.session_state.users.get(teacher_id, {}).get("name", "알 수 없음")
        
        problem_list.append({
            "problem_id": problem_id,
            "title": problem_data.get("title", "제목 없음"),
            "level": problem_data.get("level", "기본"),
            "created_by": teacher_name,
            "created_at": problem_data.get("created_at", "")
        })
    
    # 문제가 없는 경우
    if not problem_list:
        st.info("아직 등록된 문제가 없습니다.")
        return
    
    # 문제 목록 표시
    st.subheader("문제 목록")
    
    # 문제 정렬
    sort_option = st.selectbox(
        "정렬 방식:",
        ["최신순", "난이도 쉬운순", "난이도 어려운순"]
    )
    
    if sort_option == "최신순":
        problem_list = sorted(problem_list, key=lambda x: x["created_at"], reverse=True)
    elif sort_option == "난이도 쉬운순":
        level_order = {"초급": 1, "중급": 2, "고급": 3, "기본": 2}
        problem_list = sorted(problem_list, key=lambda x: level_order.get(x["level"], 2))
    elif sort_option == "난이도 어려운순":
        level_order = {"초급": 1, "중급": 2, "고급": 3, "기본": 2}
        problem_list = sorted(problem_list, key=lambda x: level_order.get(x["level"], 2), reverse=True)
    
    # 표로 문제 목록 표시
    problems_df = pd.DataFrame([
        {
            "제목": p["title"],
            "난이도": p["level"],
            "출제자": p["created_by"],
            "problem_id": p["problem_id"]
        } for p in problem_list
    ])
    
    display_df = problems_df[["제목", "난이도", "출제자"]]
    
    st.dataframe(display_df, use_container_width=True)
    
    # 문제 선택 및 풀이
    selected_problem_idx = st.selectbox(
        "풀이할 문제를 선택하세요:",
        range(len(problem_list)),
        format_func=lambda x: f"{problem_list[x]['title']} ({problem_list[x]['level']})"
    )
    
    if selected_problem_idx is not None:
        selected_problem_id = problem_list[selected_problem_idx]["problem_id"]
        
        if st.button("선택한 문제 풀기"):
            # 학생 기록에서 이미 푼 문제인지 확인
            username = st.session_state.username
            student_record = st.session_state.student_records.get(username, {"solved_problems": []})
            
            # 기존에 푼 문제인지 확인
            already_solved = False
            for problem in student_record.get("solved_problems", []):
                if problem.get("problem_id") == selected_problem_id:
                    already_solved = True
                    break
            
            if already_solved:
                st.warning("이미 푼 문제입니다. 다른 문제를 선택하거나 내 기록에서 확인해보세요.")
            else:
                # 문제 풀이 페이지로 이동
                st.session_state.current_problem_id = selected_problem_id
                st.session_state.solving_mode = True
                st.rerun()

def display_and_solve_problem():
    problem_id = st.session_state.current_problem_id
    problem_data = st.session_state.teacher_problems.get(problem_id, {})
    
    # 문제가 없는 경우
    if not problem_data:
        st.error("선택한 문제를 찾을 수 없습니다.")
        if st.button("문제 목록으로 돌아가기"):
            st.session_state.solving_mode = False
            st.session_state.current_problem_id = None
            st.rerun()
        return
    
    # 문제 정보 표시
    st.title(problem_data.get("title", "제목 없음"))
    
    st.markdown("**난이도:** " + problem_data.get("level", "기본"))
    
    teacher_id = problem_data.get("created_by", "")
    teacher_name = st.session_state.users.get(teacher_id, {}).get("name", "알 수 없음")
    st.markdown(f"**출제자:** {teacher_name}")
    
    st.markdown("### 문제")
    st.write(problem_data.get("description", "문제 내용이 없습니다."))
    
    # 문제 풀이
    st.markdown("### 답변 작성")
    
    # 푸는 시간 측정 시작
    if "solve_start_time" not in st.session_state:
        st.session_state.solve_start_time = time.time()
    
    answer = st.text_area("답변을 작성하세요:", height=200)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("답변 제출"):
            if not answer.strip():
                st.error("답변을 입력해주세요.")
            else:
                # 푸는 시간 측정 종료
                solve_end_time = time.time()
                time_spent = int(solve_end_time - st.session_state.solve_start_time)
                
                # 학생 기록 업데이트
                username = st.session_state.username
                
                if username not in st.session_state.student_records:
                    st.session_state.student_records[username] = {"solved_problems": []}
                
                # 문제 풀이 기록 추가
                solved_problem = {
                    "problem_id": problem_id,
                    "answer": answer,
                    "solved_at": datetime.datetime.now().isoformat(),
                    "time_spent": time_spent
                }
                
                st.session_state.student_records[username]["solved_problems"].append(solved_problem)
                
                # 파일에 저장
                with open("student_records.json", "w") as f:
                    json.dump(st.session_state.student_records, f)
                
                # 상태 초기화
                del st.session_state.solve_start_time
                st.session_state.solving_mode = False
                st.session_state.current_problem_id = None
                
                st.success("답변이 제출되었습니다. 교사의 채점을 기다려주세요.")
                st.rerun()
    
    with col2:
        if st.button("취소"):
            # 상태 초기화
            if "solve_start_time" in st.session_state:
                del st.session_state.solve_start_time
            st.session_state.solving_mode = False
            st.session_state.current_problem_id = None
            st.rerun()

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
    
    tab1, tab2 = st.tabs(["로그인", "비밀번호 찾기"])
    
    with tab1:
        st.subheader("로그인")
        
        username = st.text_input("아이디:")
        password = st.text_input("비밀번호:", type="password")
        
        if st.button("로그인"):
            if not username or not password:
                st.error("아이디와 비밀번호를 모두 입력해주세요.")
            elif username not in st.session_state.users:
                st.error("존재하지 않는 아이디입니다.")
            elif st.session_state.users[username]["password"] != hash_password(password):
                st.error("비밀번호가 일치하지 않습니다.")
            else:
                st.session_state.username = username
                st.success(f"{st.session_state.users[username]['name']}님, 환영합니다!")
                st.rerun()
    
    with tab2:
        st.subheader("비밀번호 찾기")
        
        username = st.text_input("아이디:", key="reset_username")
        email = st.text_input("가입시 등록한 이메일:", key="reset_email")
        
        if st.button("비밀번호 재설정"):
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

# 앱 실행
if __name__ == "__main__":
    main() 
