import streamlit as st
import os
import json
import random
from openai import AzureOpenAI
from dotenv import load_dotenv
from duckduckgo_search import DDGS 
from tavily import TavilyClient

# 1. 환경 변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(page_title="논리 코칭 봇 왓슨", page_icon="🦉")
st.title("🦉 논리 탐정 '왓슨'")
st.caption("당신의 주장에 숨어있는 논리적 오류를 찾고, 팩트까지 체크해드려요.")

# 2. Azure OpenAI 클라이언트 설정
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OAI_KEY"),
    api_version="2024-05-01-preview",
    azure_endpoint=os.getenv("AZURE_OAI_ENDPOINT")
)

# ------------------------------------------------------------------
# [기능 정의] 하이브리드 검색 함수 (Tavily -> DuckDuckGo 폴백)
# ------------------------------------------------------------------
def search_web(query):
    """
    1순위: Tavily API (고품질, 차단 없음)
    2순위: DuckDuckGo (무제한, 차단 위험 있음) - Tavily 실패 시 자동 실행
    """
    results_text = ""
    
    # [1단계] Tavily 시도
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            tavily = TavilyClient(api_key=tavily_key)
            response = tavily.search(query=query, search_depth="basic", max_results=3)
            
            results_text = "✅ [출처: Tavily]\n"
            for result in response['results']:
                results_text += f"- 제목: {result['title']}\n  링크: {result['url']}\n  내용: {result['content']}\n\n"
            return results_text
            
        except Exception as e:
            print(f"⚠️ Tavily 검색 실패 (DDG로 전환): {e}")
            pass # 실패하면 아래 DuckDuckGo 로직으로 넘어감
    
    # [2단계] DuckDuckGo (Fallback)
    try:
        # 차단 회피를 위한 랜덤 User-Agent 설정
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
        ]
        
        with DDGS(headers={"User-Agent": random.choice(user_agents)}) as ddgs:
            # backend='html' 사용 시 차단 확률 낮음
            results = list(ddgs.text(query, max_results=3, backend="html"))
            
        if not results:
            return "❌ 검색 결과가 없습니다 (접속 제한 또는 결과 없음)."

        results_text = "✅ [출처: DuckDuckGo]\n"
        results_text += "\n".join([f"- 제목: {r['title']}\n  링크: {r['href']}\n  내용: {r['body']}" for r in results])
        return results_text

    except Exception as e:
        return f"❌ 모든 검색 시스템 오류 발생: {str(e)}"

# [도구 정의] AI에게 검색 함수의 존재를 알림
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "사용자의 주장을 검증하거나 반박하기 위해 팩트(기사, 통계, 논문)가 필요할 때 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 키워드 (예: '혈액형 성격설 과학적 근거', '지구 평면설 반박 증거')"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# ------------------------------------------------------------------
# [시스템 프롬프트] 페르소나 + 논리 분석 지침 + 팩트 체크 지침 통합
# ------------------------------------------------------------------
system_prompt = """
당신은 '논리적 오류 탐지 전문가'이자 사용자의 성장을 돕는 '다정한 멘토, 왓슨'입니다.
사용자의 입력에서 논리적 비약, 성급한 일반화, 허수아비 공격 등의 오류가 있는지 분석하고, 필요한 경우 팩트 체크를 수행하세요.

다음 지침을 반드시 따르세요:

1. 공감 및 요약 (Empathetic Summary): 
   - 먼저 사용자의 주장을 잘 이해했다는 것을 보여주며 부드럽게 요약하세요. 
   - 적절한 이모지(🦉, 🤔 등)를 활용하여 친근감을 표현하세요.

2. 논리 분석 (Logical Analysis):
   - 발견된 논리적 오류가 있다면 명확한 용어(예: 확증 편향, 성급한 일반화)로 지적하고 이유를 설명하세요.
   - 오류가 없다면 논리적 구조가 얼마나 탄탄한지 칭찬해주세요.

3. 팩트 체크 (Fact Checking):
   - 사용자의 주장이 사실 확인이 필요하거나, 잘못된 정보를 전제로 하고 있다면 `search_web` 도구를 적극적으로 사용하세요.
   - 검색된 기사나 논문이 있다면 **반드시 링크와 제목을 인용**하여 주장을 뒷받침하거나 정중히 바로잡아 주세요.

4. 성장 질문 (Growth Question):
   - 사용자가 더 나은 논리를 펼치거나 깊게 생각할 수 있도록 '생각해볼 만한 질문(가이드)'을 하나 던지세요.

5. 말투 (Tone):
   - 정중하면서도 분석적이어야 하지만, 딱딱하지 않게 하세요.
   - 따뜻하고 친절한 '해요체'를 사용하세요. "지적"이 아닌 "조언"의 느낌을 주어야 합니다.
"""

# 3. 대화기록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 4. 화면에 기존 대화 내용 출력
for message in st.session_state.messages:
    if message["role"] != "tool": # tool 실행 결과 메시지는 화면에 굳이 표시 안 함
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# 5. 사용자 입력 받기
if prompt := st.chat_input("주장이나 생각을 입력해보세요 (예: 모든 부자는 성격이 나빠)"):
    # (1) 사용자 메시지 표시 및 저장
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # (2) AI 응답 생성 과정
    with st.chat_message("assistant"):
        # API에 보낼 전체 메시지 구성 (시스템 프롬프트 + 이전 대화)
        messages_payload = [{"role": "system", "content": system_prompt}] + st.session_state.messages
        
        # 1차 호출: AI가 도구(검색) 사용 여부 결정
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages_payload,
            tools=tools,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        
        # [분기 1] 도구 사용이 필요한 경우
        if response_message.tool_calls:
            # 1. AI가 "나 검색할래요"라고 한 기록을 메시지에 추가 (중요: 대화 맥락 유지)
            messages_payload.append(response_message)
            
            # 2. 실제 검색 함수 실행
            for tool_call in response_message.tool_calls:
                if tool_call.function.name == "search_web":
                    args = json.loads(tool_call.function.arguments)
                    query = args["query"]
                    
                    # 스피너로 진행 상태 표시
                    with st.spinner(f"🕵️ 왓슨이 '{query}' 팩트 체크 중..."):
                        search_result = search_web(query)
                    
                    # 3. 검색 결과를 messages_payload에 추가 (role: tool)
                    messages_payload.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": "search_web",
                        "content": search_result
                    })
            
            # 3. 2차 호출: 검색 결과를 포함하여 최종 답변 생성
            final_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_payload
            )
            assistant_reply = final_response.choices[0].message.content
            
        # [분기 2] 도구 사용이 필요 없는 경우 (일상 대화)
        else:
            assistant_reply = response_message.content

        # 최종 응답 출력
        st.markdown(assistant_reply)

    # (3) AI 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
