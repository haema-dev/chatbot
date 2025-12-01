import streamlit as st
import os
import json
from openai import AzureOpenAI
from dotenv import load_dotenv
from duckduckgo_search import DDGS  # 무료 검색 라이브러리 추가

# 1. 환경 변수 로드
load_dotenv()

st.set_page_config(page_title="논리 코칭 봇 (with Evidence)", page_icon="🦉")
st.title("🦉 논리 탐정 '왓슨' + 🔎 팩트 체크")
st.caption("논리적 오류 분석과 함께 관련 기사/자료를 찾아 근거를 보강합니다.")

# 2. Azure OpenAI 클라이언트 설정
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OAI_KEY"),
    api_version="2024-05-01-preview",
    azure_endpoint=os.getenv("AZURE_OAI_ENDPOINT")
)

# [기능 추가] 검색 함수 (AI가 실행할 도구)
def search_web(query):
    """웹에서 정보를 검색하여 결과를 반환합니다."""
    try:
        with DDGS() as ddgs:
            # 검색 결과 상위 3개만 가져옴
            results = list(ddgs.text(query, max_results=3))
        
        if not results:
            return "검색 결과가 없습니다."
            
        # AI가 읽기 좋게 포맷팅
        evidence = "\n".join([f"- 제목: {r['title']}\n  링크: {r['href']}\n  내용: {r['body']}" for r in results])
        return evidence
    except Exception as e:
        return f"검색 중 오류 발생: {str(e)}"

# [도구 정의] AI에게 이 함수의 존재와 사용법을 알려줌
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "사용자의 주장을 검증하거나 반박하기 위해 팩트(기사, 논문)가 필요할 때 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 키워드 (예: '부자 성격 연구 결과', '지구 평면설 반박 논문')"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# 시스템 프롬프트: 검색 도구를 적극 활용하도록 지시
system_prompt = """
당신은 '논리적 오류 탐지 전문가'이자 사용자의 성장을 돕는 '다정한 멘토, 왓슨'입니다.
사용자의 주장을 듣고 논리적 허점을 분석하되, 언제나 격려하는 태도를 잃지 마세요.
또한, 주장의 사실 여부가 의심될 때는 'search_web' 도구를 적극적으로 사용하여 팩트를 체크해주세요.

[행동 지침]
1. 공감 및 요약: 먼저 사용자의 주장을 잘 이해했다는 것을 보여주며 부드럽게 요약하세요. (이모지 활용 추천 🦉)
2. 논리 분석:
   - 논리적 오류(성급한 일반화, 허수아비 공격 등)가 있다면 명확한 용어로 짚어주세요.
   - 오류가 없다면 논리적 구조가 훌륭하다고 칭찬해주세요.
3. 팩트 체크 (필요시):
   - 사용자의 주장에 통계, 과학적 사실, 뉴스 등의 근거가 필요하다면 `search_web` 도구를 사용하여 검색하세요.
   - 검색된 기사나 논문이 있다면 링크와 제목을 인용하여 주장을 뒷받침하거나 정중히 반박하세요.
4. 성장 질문: 사용자가 한 단계 더 깊게 생각할 수 있도록 '생각해볼 만한 질문'을 하나 던지세요.
5. 말투: 
   - 딱딱한 기계적인 말투가 아닌, 따뜻하고 정중한 '해요체'를 사용하세요.
   - "지적"이 아닌 "조언"의 느낌을 주세요.

[예시]
사용자: "B형 남자는 다 바람둥이야."
왓슨: "아, B형 남자분들에 대해 안 좋은 기억이 있으신가 보군요. 😢 주장을 요약하면 혈액형과 성격 사이에 인과관계가 있다는 말씀이시네요.
하지만 이는 논리적으로 '성급한 일반화의 오류'에 해당해요. 제가 관련 연구를 찾아보니(검색 결과 인용), 혈액형과 성격의 연관성은 과학적 근거가 없다는 기사가 많네요! [기사 링크]
대신 사람의 성격을 판단할 때 더 좋은 기준은 무엇이 있을지 생각해보면 어떨까요?"
"""

if "messages" not in st.session_state:
    st.session_state.messages = []

# 대화 기록 표시
for message in st.session_state.messages:
    if message["role"] != "tool": # tool 메시지는 숨김
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

if prompt := st.chat_input("주장을 입력하세요 (예: 커피를 마시면 머리가 나빠져)"):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        messages_payload = [{"role": "system", "content": system_prompt}] + st.session_state.messages
        
        # 1차 호출: AI가 도구 사용 여부 결정
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages_payload,
            tools=tools,
            tool_choice="auto" 
        )
        
        response_message = response.choices[0].message
        
        # AI가 도구를 쓰겠다고 했는지 확인
        if response_message.tool_calls:
            messages_payload.append(response_message) # 대화 흐름 유지용
            
            for tool_call in response_message.tool_calls:
                if tool_call.function.name == "search_web":
                    args = json.loads(tool_call.function.arguments)
                    query = args["query"]
                    
                    with st.spinner(f"🕵️ '{query}' 팩트 체크 중..."):
                        search_result = search_web(query)
                    
                    # 검색 결과를 대화에 추가 (role: tool)
                    messages_payload.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": "search_web",
                        "content": search_result
                    })
            
            # 2차 호출: 검색 결과를 포함해 최종 답변 생성
            final_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_payload
            )
            assistant_reply = final_response.choices[0].message.content
            
        else:
            # 검색이 필요 없는 일상 대화
            assistant_reply = response_message.content

        st.markdown(assistant_reply)

    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
