"""Shared safeguards for relevant blog images and official destinations.

✅ 2026-07-22 대폭 업그레이드:
  - build_grounded_image_prompt: Gemini AI가 글 내용 분석 → 내용과 딱 맞는 이미지 설명 생성
  - select_official_destination: URL 추출 + 키워드 매칭 대폭 확장 → 정확한 공식 링크 버튼
"""

from __future__ import annotations

import re
import os
import urllib.parse
import requests
from urllib.parse import urlparse

# ──────────────────────────────────────────────
# 이미지 장면 키워드 매핑 (폴백용 - Gemini 실패 시)
# ──────────────────────────────────────────────
TITLE_SCENES = (
    # 복지/지원
    (("전세", "보증금", "보증료"), "a Korean rental guarantee consultation desk with apartment contract documents and a house key"),
    (("출산", "신생아", "아기", "출생"), "a newborn baby care package with baby clothes, diapers, milk bottle in a Korean welfare center"),
    (("평생교육", "교육이용권", "장애인 교육"), "an accessible adult learning classroom in Korea with welfare voucher card and study materials"),
    (("입학", "학습지원", "교육비"), "a Korean student desk with school books, stationery and education-support application documents"),
    (("청년", "청년지원", "청년수당"), "young Korean adults at a career center applying for government youth support programs"),
    (("일자리", "취업", "고용", "실업"), "Korean people at an employment center, job fair, career counseling desks and job listings"),
    (("의료", "건강보험", "병원", "치료"), "Korean medical facility with health insurance documents, doctor consulting a patient"),
    (("노인", "어르신", "장기요양"), "Korean elderly care facility with caring staff helping senior citizens"),
    (("장애인", "장애"), "accessible Korean public services for people with disabilities, supportive care workers"),
    (("육아", "보육", "어린이집"), "Korean childcare center with children playing, caring teachers, and childcare support documents"),
    (("주거", "월세", "임대"), "Korean affordable housing complex, apartment buildings with housing support information"),
    (("국민취업", "취업지원"), "Korean employment support center with counselors helping job seekers"),
    # 정부지원/정책
    (("보훈", "유공자"), "Korean veterans benefit center with official documents and national-service ribbons"),
    (("시민참여", "포인트"), "Korean municipal community center with citizens using smartphone public service app"),
    (("농업", "농민", "농촌"), "Korean agricultural field with farmers working, rural landscape and support programs"),
    (("소상공인", "자영업", "창업"), "Korean small business owner in a shop with business support documents and grants"),
    (("에너지", "전기요금", "가스"), "Korean household energy bill documents with energy subsidy support information"),
    # IT/기술
    (("AI", "인공지능", "artificial intelligence"), "a futuristic artificial intelligence neural network visualization with glowing circuits and digital data streams"),
    (("반도체", "chip", "칩"), "close-up of semiconductor chips on circuit board with high-tech manufacturing equipment"),
    (("로봇", "robot"), "advanced humanoid robot in a clean laboratory with technology equipment"),
    (("클라우드", "cloud computing"), "abstract cloud computing visualization with servers, data connections and digital infrastructure"),
    (("사이버", "해킹", "보안"), "cybersecurity concept with digital shield, code lines and network protection visualization"),
    (("전기차", "EV", "배터리"), "sleek electric vehicle charging at a modern charging station with battery technology"),
    (("메타버스", "VR", "AR"), "person using VR headset in a futuristic digital metaverse environment"),
    (("스타트업", "startup"), "modern startup office with young entrepreneurs working on technology products"),
    (("nvidia", "GPU"), "high-performance GPU graphics card with cooling fans and performance visualization"),
    (("openai", "chatgpt", "gpt"), "ChatGPT AI conversation interface on a computer screen with AI brain visualization"),
    (("삼성", "samsung"), "Samsung electronics product showcase in a modern tech presentation setting"),
    (("애플", "apple", "아이폰"), "Apple iPhone on a clean minimalist desk with tech accessories"),
    # 라이프스타일/리브미
    (("수박스무디", "스무디"), "a refreshing watermelon smoothie in a Korean convenience store refrigerator close-up"),
    (("샐러드", "salad"), "a fresh colorful salad bowl with vegetables, healthy meal in Korean cafe setting"),
    (("쿠폰", "할인", "적립"), "Korean retail discount coupon, sale promotion with product close-up"),
    (("편의점", "cu", "gs25", "세븐일레븐"), "Korean convenience store interior with product shelves, snacks and beverages"),
    (("카페", "커피", "스타벅스"), "cozy Korean cafe interior with coffee drinks, pastries and warm lighting"),
    (("헬스", "운동", "fitness"), "Korean fitness center with workout equipment, people exercising energetically"),
    (("여행", "관광", "vacation"), "beautiful Korean travel destination with tourists enjoying scenery"),
    (("맛집", "음식", "restaurant"), "delicious Korean food spread at a popular restaurant with beautiful presentation"),
)

# ──────────────────────────────────────────────
# 공식 링크 버튼 규칙 (대폭 확장)
# ──────────────────────────────────────────────
OFFICIAL_COMMERCIAL_DOMAINS = {
    "7-eleven.co.kr", "cu.bgfretail.com", "costco.co.kr", "theventi.co.kr",
    "starbucks.co.kr", "emart24.co.kr", "lotteon.com", "homeplus.co.kr",
    "coupang.com", "gmarket.co.kr", "11st.co.kr", "auction.co.kr",
}

OFFICIAL_DESTINATION_RULES = (
    # ── 지역 자치단체 ──
    (("중랑구",), "https://www.jungnang.go.kr/"),
    (("노원구",), "https://www.nowon.go.kr/"),
    (("강남구",), "https://www.gangnam.go.kr/"),
    (("강서구", "서울 강서"), "https://www.gangseo.seoul.kr/"),
    (("부산 강서", "부산강서"), "https://www.bsgangseo.go.kr/"),
    (("서초구",), "https://www.seocho.go.kr/"),
    (("마포구",), "https://www.mapo.go.kr/"),
    (("은평구",), "https://www.ep.go.kr/"),
    (("서대문구",), "https://www.sdm.go.kr/"),
    (("성동구",), "https://www.sd.go.kr/"),
    (("광진구",), "https://www.gwangjin.go.kr/"),
    (("동대문구",), "https://www.ddm.go.kr/"),
    (("성북구",), "https://www.sb.go.kr/"),
    (("도봉구",), "https://www.dobong.go.kr/"),
    (("강북구",), "https://www.gangbuk.go.kr/"),
    (("송파구",), "https://www.songpa.go.kr/"),
    (("강동구",), "https://www.gangdong.go.kr/"),
    (("서울", "서울시", "서울특별시"), "https://www.seoul.go.kr/"),
    (("경기도", "경기"), "https://www.gg.go.kr/"),
    (("인천", "인천시"), "https://www.incheon.go.kr/"),
    (("부산", "부산시"), "https://www.busan.go.kr/"),
    (("대구", "대구시"), "https://www.daegu.go.kr/"),
    (("광주", "광주시"), "https://www.gwangju.go.kr/"),
    (("대전", "대전시"), "https://www.daejeon.go.kr/"),
    (("울산", "울산시"), "https://www.ulsan.go.kr/"),
    (("세종", "세종시"), "https://www.sejong.go.kr/"),
    (("경남", "경상남도"), "https://www.gyeongnam.go.kr/"),
    (("경북", "경상북도"), "https://www.gb.go.kr/"),
    (("전남", "전라남도"), "https://www.jeonnam.go.kr/"),
    (("전북", "전라북도"), "https://www.jeonbuk.go.kr/"),
    (("충남", "충청남도"), "https://www.chungnam.go.kr/"),
    (("충북", "충청북도"), "https://www.cb.go.kr/"),
    (("강원", "강원도"), "https://www.gangwon.go.kr/"),
    (("제주", "제주도"), "https://www.jeju.go.kr/"),
    # ── 정부 기관 ──
    (("복지로",), "https://www.bokjiro.go.kr/"),
    (("정부24", "정부 24"), "https://www.gov.kr/"),
    (("국민건강보험", "건강보험공단", "nhis"), "https://www.nhis.or.kr/"),
    (("국민연금", "nps"), "https://www.nps.or.kr/"),
    (("고용보험", "실업급여", "고용24"), "https://www.ei.go.kr/"),
    (("워크넷", "구인구직", "work.go.kr"), "https://www.work.go.kr/"),
    (("국민취업지원제도",), "https://www.kua.go.kr/"),
    (("청년내일저축계좌", "청년저축"), "https://www.bokjiro.go.kr/"),
    (("주민등록", "전입신고"), "https://www.gov.kr/"),
    (("병무청", "병역", "입영"), "https://www.mma.go.kr/"),
    (("교육부", "교육청"), "https://www.moe.go.kr/"),
    (("보건복지부", "복지부", "mohw"), "https://www.mohw.go.kr/"),
    (("행정안전부", "행안부"), "https://www.mois.go.kr/"),
    (("국토교통부", "국토부"), "https://www.molit.go.kr/"),
    (("중소벤처기업부", "중기부", "소상공인"), "https://www.mss.go.kr/"),
    (("소상공인시장진흥공단", "소진공"), "https://www.semas.or.kr/"),
    (("한국장학재단", "국가장학금"), "https://www.kosaf.go.kr/"),
    (("한국주택금융공사", "주택금융"), "https://www.hf.go.kr/"),
    (("LH", "한국토지주택공사"), "https://www.lh.or.kr/"),
    (("SH", "서울주택도시공사"), "https://www.i-sh.co.kr/"),
    (("농림축산식품부", "농식품부"), "https://www.mafra.go.kr/"),
    (("농협", "농협은행"), "https://www.nonghyup.com/"),
    # ── IT/기업 ──
    (("nvidia", "엔비디아"), "https://www.nvidia.com/"),
    (("삼성전자", "samsung electronics"), "https://www.samsung.com/kr/"),
    (("애플", "apple", "아이폰", "iphone", "맥북"), "https://www.apple.com/kr/"),
    (("구글", "google", "안드로이드"), "https://www.google.com/"),
    (("마이크로소프트", "microsoft", "윈도우", "azure"), "https://www.microsoft.com/ko-kr/"),
    (("openai", "챗gpt", "chatgpt", "gpt-4", "gpt-5"), "https://openai.com/"),
    (("메타", "meta", "페이스북", "인스타그램"), "https://about.meta.com/"),
    (("아마존", "amazon", "aws"), "https://aws.amazon.com/ko/"),
    (("카카오", "kakao", "카카오톡"), "https://www.kakao.com/"),
    (("네이버", "naver", "클로바"), "https://www.naver.com/"),
    (("쿠팡", "coupang", "로켓배송"), "https://www.coupang.com/"),
    (("sk텔레콤", "skt", "t맵"), "https://www.sktelecom.com/"),
    (("kt", "케이티", "olleh"), "https://www.kt.com/"),
    (("lg유플러스", "lgu+"), "https://www.lguplus.com/"),
    (("현대자동차", "hyundai", "현대차"), "https://www.hyundai.com/kr/"),
    (("기아", "kia"), "https://www.kia.com/kr/"),
    # ── 편의점/유통 ──
    (("세븐일레븐", "7-eleven"), "https://www.7-eleven.co.kr/"),
    (("cu편의점", "씨유", "cu 편의점"), "https://cu.bgfretail.com/"),
    (("gs25",), "https://www.gs25.com/"),
    (("이마트24", "emart24"), "https://www.emart24.co.kr/"),
    (("코스트코", "costco"), "https://www.costco.co.kr/"),
    (("더벤티", "theventi"), "https://theventi.co.kr/"),
    (("스타벅스", "starbucks"), "https://www.starbucks.co.kr/"),
    (("투썸플레이스", "twosome"), "https://www.twosome.co.kr/"),
    (("맥도날드", "mcdonald"), "https://www.mcdonalds.co.kr/"),
    (("롯데마트", "롯데"), "https://company.lotte.com/"),
)


# ──────────────────────────────────────────────
# Gemini AI로 이미지 설명 생성 (핵심 업그레이드!)
# ──────────────────────────────────────────────
def build_grounded_image_prompt_with_gemini(title: str, summary: str, channel: str, api_keys: list) -> str:
    """Gemini AI가 글 내용을 분석해서 딱 맞는 이미지 설명을 영어로 생성합니다."""

    channel_hints = {
        'it':      'IT technology, artificial intelligence, software, hardware, digital innovation',
        'welfare': 'Korean social welfare, government support, public service, citizens receiving help',
        'libme':   'Korean lifestyle, daily life, product review, food, convenience store',
        'gov':     'Korean government policy, public service, citizen support, official announcement',
    }
    hint = channel_hints.get(channel, 'Korean blog post')

    gemini_prompt = f"""You are an expert at creating Pollinations AI image prompts.

Blog article info:
- Title: {title}
- Summary: {summary[:300] if summary else 'No summary'}
- Channel theme: {hint}

Create ONE specific image prompt in English (max 80 words) that:
1. Directly depicts the main subject of this article
2. Is visually specific (show actual objects/scenes related to the topic)
3. NO generic people portraits, NO unrelated landscapes, NO random scenes
4. Style: polished editorial illustration, 16:9 landscape
5. Must NOT contain: fashion model, sunset, beach, skyline, watermark, logo, text

Reply with ONLY the image prompt, nothing else."""

    import google.generativeai as genai
    for api_key in (api_keys or []):
        try:
            genai.configure(api_key=api_key)
            for model in ['gemini-flash-lite-latest', 'gemini-flash-latest', 'gemini-2.5-flash']:
                try:
                    resp = genai.GenerativeModel(model).generate_content(gemini_prompt)
                    if resp and resp.text and len(resp.text.strip()) > 20:
                        result = resp.text.strip()
                        # 불필요한 따옴표 제거
                        result = result.strip('"\'')
                        print(f"  ✅ Gemini 이미지 프롬프트 생성 성공 [{model}]: {result[:80]}...")
                        return result
                except Exception:
                    continue
        except Exception:
            continue

    # Gemini 실패 시 키워드 기반 폴백
    return build_grounded_image_prompt(title, summary, channel)


def build_grounded_image_prompt(title: str, summary: str, channel: str) -> str:
    """폴백: 키워드 기반 이미지 프롬프트 (Gemini 실패 시 사용)."""
    source = f"{title} {summary}".lower()
    scene = next((scene for words, scene in TITLE_SCENES
                  if any(word.lower() in source for word in words)), None)
    if not scene:
        subject = re.sub(r"[^0-9A-Za-z가-힣\s]", " ", title)
        subject = " ".join(subject.split()[:12])

        channel_default = {
            'it':      f"a futuristic technology concept about {subject}, digital innovation visualization",
            'welfare': f"Korean public welfare service about {subject}, government support center with helpful staff",
            'libme':   f"Korean lifestyle scene about {subject}, daily life product review",
            'gov':     f"Korean government official service about {subject}, public administration building",
        }
        scene = channel_default.get(channel,
            f"a Korean public-service information setting about {subject}, relevant documents and people")

    return (
        f"Editorial cover image for a Korean article about: {title}. "
        f"Depict: {scene}. "
        "Show only this subject. No fashion model, no sunset, no skyline, no beach, "
        "no unrelated person, no collage, no logo, no watermark, no readable text. "
        "16:9 landscape, polished editorial illustration, highly detailed."
    )


# ──────────────────────────────────────────────
# 공식 링크 버튼 URL 탐지 (대폭 업그레이드!)
# ──────────────────────────────────────────────
def is_official_destination(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":")[0]
    return parsed.scheme in ("http", "https") and (
        host.endswith(".go.kr")
        or host.endswith(".or.kr")
        or host.endswith(".re.kr")
        or host in OFFICIAL_COMMERCIAL_DOMAINS
    )


def extract_urls_from_content(content: str) -> list[str]:
    """글 본문에서 URL을 추출합니다."""
    urls = re.findall(r'https?://[^\s\'"<>)]+', content)
    # 단축 URL, 이미지 URL, JS URL 제외
    clean = []
    for u in urls:
        u = u.rstrip('.,;)')
        if any(skip in u for skip in ['pollinations', 'githubusercontent', 'gstatic', 'facebook.com/sharer', 'twitter.com/intent', 'javascript:']):
            continue
        clean.append(u)
    return clean


def select_official_destination(source_url: str | None, title: str, summary: str = "") -> str | None:
    """
    우선순위:
    1. 원본 기사 URL이 공식 도메인이면 그대로 사용
    2. 글 내용에서 공식 도메인 URL 추출
    3. 제목/내용 키워드 매칭으로 공식 URL 반환
    4. None 반환 (호출부에서 기본값 처리)
    """
    # 1. 원본 기사 URL 자체가 공식이면 바로 사용
    if is_official_destination(source_url):
        return source_url

    text = f"{title} {summary}".lower()

    # 2. 본문 내 공식 URL 추출 (go.kr, or.kr 도메인)
    all_urls = extract_urls_from_content(summary or "")
    for url in all_urls:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.endswith(".go.kr") or host.endswith(".or.kr"):
            return url

    # 3. 키워드 매칭 규칙
    for words, url in OFFICIAL_DESTINATION_RULES:
        if any(word.lower() in text for word in words):
            return url

    return None
