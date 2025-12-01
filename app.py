import streamlit as st
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

# 1. 환경 변수 로드
load_dotenv()

# [변경 포인트 1] 챗봇 이름과 아이콘 변경
st.set_page_config(page_title="논리 코칭 봇", page_icon="🦉")
st.title("🦉 논리 탐정 '왓슨'")
st.caption("당신의 주장에 숨어있는 논리적 오류를 찾아드려요.")

# 2. Azure OpenAI 클라이언트 설정
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OAI_KEY"),
    api_version="2024-05-01-preview",
    azure_endpoint=os.getenv("AZURE_OAI_ENDPOINT")
)

# [변경 포인트 2] 시스템 프롬프트 정의 (AI의 페르소나 설정)
system_prompt = """
당신은 '논리적 오류 탐지 전문가'이자 '친절한 코치'입니다. 
사용자의 입력에서 논리적 비약, 성급한 일반화, 허수아비 공격 등의 오류가 있는지 분석하세요.

다음 지침을 따르세요:
1. 사용자의 주장을 요약합니다.
2. 발견된 논리적 오류가 있다면 명확한 용어(예: 확증 편향)로 지적하고 이유를 설명하세요.
3. 오류가 없다면 논리가 얼마나 탄탄한지 칭찬하세요.
4. 사용자가 더 나은 논리를 펼칠 수 있도록 '생각해볼 만한 질문(가이드)'을 하나 던지세요.
5. 말투는 정중하면서도 분석적이어야 합니다.
"""

# 3. 대화기록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 4. 화면에 기존 대화 내용 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. 사용자 입력 받기
if prompt := st.chat_input("주장이나 생각을 입력해보세요 (예: 모든 부자는 성격이 나빠)"):
    # (1) 사용자 메시지 화면 표시 & 저장
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # (2) AI 응답 생성
    with st.chat_message("assistant"):
        # [변경 포인트 3] API 호출 시 시스템 프롬프트를 맨 앞에 끼워넣기
        # 대화 기록에는 저장하지 않고, 이번 호출에만 '설정'으로 전달합니다.
        messages_payload = [{"role": "system", "content": system_prompt}] + st.session_state.messages
        
        response = client.chat.completions.create(
            model="gpt-4o-mini", # 사용하시는 배포명 확인 필요
            messages=messages_payload
        )
        assistant_reply = response.choices[0].message.content
        st.markdown(assistant_reply)

    # (3) AI 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
