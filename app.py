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
# [설정] 신뢰할 수 없는 도메인 목록 (필터링용)
# ------------------------------------------------------------------
BLOCKED_DOMAINS = [
    "namu.wiki",        # 나무위키
    "blog.naver.com",   # 네이버 블로그
    "tistory.com",      # 티스토리
    "velog.io",         # 벨로그
    "brunch.co.kr",     # 브런치 (개인 에세이가 많음)
    "dcinside.com",     # 디시인사이드
    "fmkorea.com",      # 펨코 등 커뮤니티
    "instiz.net",
    "theqoo.net"
]

def is_trusted_url(url):
    """URL이 차단된 도메인을 포함하는지 확인합니다."""
    for blocked in BLOCKED_DOMAINS:
        if blocked in url:
            return False
    return True

# ------------------------------------------------------------------
# [기능 정의] 하이브리드 검색 함수 (신뢰성 필터 추가됨)
# ------------------------------------------------------------------
def search_web(query):
    """
    1순위: Tavily API (exclude_domains 옵션 사용)
    2순위: DuckDuckGo (Python 코드로 후처리 필터링)
    """
    results_text = ""
    
    # [1단계] Tavily 시도
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            tavily = TavilyClient(api_key=tavily_key)
            # Tavily는 자체적으로 도메인 제외 기능을 제공합니다.
            response = tavily.search(
                query=query, 
                search_depth="basic", 
                max_results=5,  # 필터링될 것을 대비해 넉넉히 5개 요청
                exclude_domains=BLOCKED_DOMAINS
            )
            
            valid_results = response['results'][:3] # 상위 3개만 사용
            
            if valid_results:
                results_text = "✅ [출처: Tavily (신뢰성 필터 적용됨)]\n"
                for result in valid_results:
                    results_text += f"- 제목: {result['title']}\n  링크: {result['url']}\n  내용: {result['content']}\n\n"
                return results_text
            
        except Exception as e:
            print(f"⚠️ Tavily 검색 실패 (DDG로 전환): {e}")
            pass 
    
    # [2단계] DuckDuckGo (Fallback)
    try:
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
        ]
        
        with DDGS(headers={"User-Agent": random.choice(user_agents)}) as ddgs:
            # 필터링을 위해 넉넉하게 10개를 가져옵니다.
            raw_results = list(ddgs.text(query, max_results=10, backend="html"))
            
        # Python 코드로 직접 필터링 수행
        valid_results = []
        for r in raw_results:
            if is_trusted_url(r['href']):
                valid_results.append(r)
                if len(valid_results) >= 3: # 3개 채워지면 중단
                    break
        
        if not valid_results:
            return "❌ 신뢰할 수 있는 출처의 검색 결과가 없습니다."

        results_text = "✅ [출처: DuckDuckGo (블로그/위키 제외됨)]\n"
        results_text += "\n".join([f"- 제목: {r['title']}\n  링크: {r['href']}\n  내용: {r['body']}" for r in valid_results])
        return results_text

    except Exception as e:
        return f"❌ 검색 시스템 오류 발생: {str(e)}"

# [도구 정의]
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
# [시스템 프롬프트] 검증되지 않은 소스 배제 지침 추가
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

3. 엄격한 팩트 체크 및 출처 표기 (Fact Checking with Sources):
   - 사용자의 주장이 사실 확인이 필요하다면 `search_web` 도구를 사용하세요.
   - 중요: 검색 결과 중 '나무위키', '블로그', '커뮤니티' 게시글은 신뢰할 수 없는 정보로 간주하고 인용하지 마세요.
   - 반드시 뉴스 기사, 학술 논문, 정부 기관 발표 등 공신력 있는 출처만 인용하여 주장을 뒷받침하세요.
   - 출처 표시 필수: 인용한 정보의 출처는 반드시 [제목](링크) 형식의 마크다운 링크로 답변 하단이나 관련 문장에 명시해야 합니다. 링크를 절대 누락하지 마세요.

4. 성장 질문 (Growth Question):
   - 사용자가 더 나은 논리를 펼치거나 깊게 생각할 수 있도록 '생각해볼 만한 질문(가이드)'을 하나 던지세요.

5. 말투 (Tone):
   - 정중하면서도 분석적이어야 하지만, 딱딱하지 않게 하세요.
   - 따뜻하고 친절한 '해요체'를 사용하세요.
"""

# 3. 대화기록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 4. 화면에 기존 대화 내용 출력
for message in st.session_state.messages:
    if message["role"] != "tool": 
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# 5. 사용자 입력 받기
if prompt := st.chat_input("주장이나 생각을 입력해보세요 (예: 모든 부자는 성격이 나빠)"):
    # (1) 사용자 메시지 표시 및 저장
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # (2) AI 응답 생성 과정
    with st.chat_message("assistant"):
        messages_payload = [{"role": "system", "content": system_prompt}] + st.session_state.messages
        
        # 1차 호출
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages_payload,
            tools=tools,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        
        # [분기 1] 도구 사용이 필요한 경우
        if response_message.tool_calls:
            messages_payload.append(response_message)
            
            for tool_call in response_message.tool_calls:
                if tool_call.function.name == "search_web":
                    args = json.loads(tool_call.function.arguments)
                    query = args["query"]
                    
                    with st.spinner(f"🕵️ 왓슨이 '{query}' 팩트 체크 중..."):
                        search_result = search_web(query)
                    
                    messages_payload.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": "search_web",
                        "content": search_result
                    })
            
            # 2차 호출
            final_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_payload
            )
            assistant_reply = final_response.choices[0].message.content
            
        # [분기 2] 도구 사용 필요 없음
        else:
            assistant_reply = response_message.content

        st.markdown(assistant_reply)

    # (3) AI 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
