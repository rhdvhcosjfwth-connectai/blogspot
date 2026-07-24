# -*- coding: utf-8 -*-
"""
repair_images_all.py - 완전 재작성 버전
- 봇별로 환경변수 하나씩 받아서 처리 (BLOG_URL, TOKEN_JSON_BASE64, BLOG_NAMESPACE, BLOG_THEME)
- Gemini AI로 글 내용 분석 → 딱 맞는 이미지 설명 생성
- 429/타임아웃 → 자동 재시도
- 이미지 없는 글, 깨진 이미지 글 모두 복구
"""
import os
import re
import sys
import json
import random
import hashlib
import urllib.parse
import base64
import requests
import time
import tempfile

from io import BytesIO
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')

# ──────────────────────────────────────────────
# 환경변수
# ──────────────────────────────────────────────
ASSET_TOKEN    = os.environ.get('ASSET_GITHUB_TOKEN', '')
ASSET_REPO     = os.environ.get('ASSET_REPO', 'b847994-a11y/blog-assets')
BLOG_URL       = os.environ.get('BLOG_URL', '')
TOKEN_B64      = os.environ.get('TOKEN_JSON_BASE64', '')
NAMESPACE      = os.environ.get('BLOG_NAMESPACE', 'blog')
THEME          = os.environ.get('BLOG_THEME', 'Korean blog post')
GEMINI_KEY     = os.environ.get('GEMINI_API_KEY', '')
MAX_POSTS      = 40   # 한 번에 복구할 최대 글 수

# ──────────────────────────────────────────────
# 깨진 이미지 판단
# ──────────────────────────────────────────────
BAD_PATTERNS = [
    "loremflickr.com", "picsum.photos", "data:image/",
    "earthdaizer", "placeholder",
]

def is_broken_image(src: str) -> bool:
    s = src.lower()
    for p in BAD_PATTERNS:
        if p in s:
            return True
    # blog-assets 아닌 githubusercontent 링크
    if "raw.githubusercontent.com" in s and "blog-assets" not in s:
        return True
    # Pollinations 직접 URL (blog-assets에 저장 안 된 것) - 불안정함
    if "image.pollinations.ai" in s:
        return True
    return False

def has_no_image(content: str) -> bool:
    return '<img' not in content

# ──────────────────────────────────────────────
# Gemini로 이미지 프롬프트 생성
# ──────────────────────────────────────────────
def make_image_prompt_with_gemini(title: str, content_snippet: str) -> str:
    """글 제목+내용으로 Gemini가 딱 맞는 이미지 설명 생성"""
    if not GEMINI_KEY:
        return make_fallback_prompt(title)

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_KEY)

        prompt = f"""Create ONE specific Pollinations AI image prompt in English (max 80 words) for this blog post:

Title: {title}
Content preview: {content_snippet[:300] if content_snippet else 'N/A'}
Blog theme: {THEME}

Rules:
- Show ONLY what this specific article is about
- Be visually specific (real objects, real scenes)
- NO fashion models, NO random people portraits, NO sunsets, NO beaches, NO skylines unrelated to topic
- Style: polished editorial illustration, 16:9 landscape
- Do NOT include any watermark, logo, or text in the image

Reply with ONLY the image prompt text, nothing else."""

        for model in ['gemini-2.0-flash-lite', 'gemini-flash-lite-latest', 'gemini-flash-latest']:
            try:
                resp = genai.GenerativeModel(model).generate_content(prompt)
                if resp and resp.text and len(resp.text.strip()) > 20:
                    result = resp.text.strip().strip('"\'')
                    print(f"  ✅ Gemini 이미지 프롬프트 [{model}]: {result[:80]}...")
                    return result
            except Exception as e:
                print(f"  ⚠️ Gemini [{model}] 실패: {e}")
                continue
    except Exception as e:
        print(f"  ⚠️ Gemini 전체 실패: {e}")

    return make_fallback_prompt(title)

def make_fallback_prompt(title: str) -> str:
    """Gemini 실패 시 폴백 프롬프트"""
    clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', title).strip()
    words = clean.split()[:8]
    topic = ' '.join(words) if words else 'blog post'
    styles = ["editorial illustration", "cinematic photography", "polished digital art"]
    return (f"A {random.choice(styles)} depicting {topic}, "
            f"related to {THEME}, highly detailed, 16:9 landscape, "
            "no text, no watermark, no logo, no fashion model, no unrelated person")

# ──────────────────────────────────────────────
# Pollinations 이미지 다운로드 (재시도 포함)
# ──────────────────────────────────────────────
def download_image(prompt_text: str, max_retries: int = 3) -> bytes | None:
    encoded = urllib.parse.quote(prompt_text)
    seed = random.randint(1, 9999999)
    url = (f"https://image.pollinations.ai/prompt/{encoded}.png"
           f"?width=800&height=400&nologo=true&seed={seed}")

    for attempt in range(max_retries):
        try:
            print(f"  📸 이미지 다운로드 중... (시도 {attempt+1}/{max_retries})")
            resp = requests.get(url, timeout=50,
                                headers={"User-Agent": "Mozilla/5.0 Chrome/120 Safari/537.36"})
            if resp.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f"  ⚠️ 429 → {wait}초 대기 후 재시도")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            ct = resp.headers.get("Content-Type", "")
            if not ct.startswith("image/"):
                raise ValueError(f"이미지 아님: {ct}")
            return resp.content
        except requests.exceptions.Timeout:
            wait = 15 * (attempt + 1)
            print(f"  ⚠️ 타임아웃 → {wait}초 후 재시도")
            time.sleep(wait)
        except Exception as e:
            print(f"  ❌ 다운로드 실패 (시도 {attempt+1}): {e}")
            time.sleep(10)
    return None

# ──────────────────────────────────────────────
# blog-assets 저장
# ──────────────────────────────────────────────
def upload_to_assets(image_bytes: bytes, title: str) -> str | None:
    if not ASSET_TOKEN:
        print("  ⚠️ ASSET_GITHUB_TOKEN 없음")
        return None
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=88, optimize=True)
        payload = buf.getvalue()
        if len(payload) < 1024:
            raise ValueError("이미지 너무 작음")
    except Exception as e:
        print(f"  ❌ 이미지 처리 실패: {e}")
        return None

    digest = hashlib.sha256(payload).hexdigest()[:20]
    safe_ns = re.sub(r'[^a-z0-9-]+', '-', NAMESPACE.lower()).strip('-') or 'blog'
    path = f"images/{safe_ns}/{digest}.jpg"
    api_url = f"https://api.github.com/repos/{ASSET_REPO}/contents/{path}"
    gh_h = {
        "Authorization": f"Bearer {ASSET_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    existing = requests.get(api_url, headers=gh_h, timeout=20)
    if existing.status_code == 404:
        up = requests.put(api_url, headers=gh_h, json={
            "message": f"Repair image: {title[:60]}",
            "content": base64.b64encode(payload).decode("ascii"),
            "branch": "main",
        }, timeout=45)
        up.raise_for_status()
    elif existing.status_code not in (200, 201):
        print(f"  ❌ 저장소 확인 실패: {existing.status_code}")
        return None

    public_url = f"https://raw.githubusercontent.com/{ASSET_REPO}/main/{path}"
    verify = requests.get(public_url, timeout=30,
                          headers={"User-Agent": "Mozilla/5.0 Chrome/120"})
    if verify.status_code != 200:
        print(f"  ❌ 검증 실패: {verify.status_code}")
        return None

    print(f"  ✅ 이미지 저장: {public_url}")
    return public_url

# ──────────────────────────────────────────────
# 글 하나 복구
# ──────────────────────────────────────────────
def repair_post_image(service, blog_id: str, post: dict) -> bool:
    post_id  = post['id']
    title    = post.get('title', '')
    content  = post.get('content', '')

    # 본문에서 텍스트만 추출 (이미지 프롬프트용)
    text_only = re.sub(r'<[^>]+>', ' ', content)[:400]

    # 이미지 프롬프트 생성 (Gemini)
    img_prompt = make_image_prompt_with_gemini(title, text_only)

    # Pollinations 다운로드
    img_bytes = download_image(img_prompt)
    if not img_bytes:
        print(f"  ❌ '{title[:30]}' - 이미지 다운로드 실패, 건너뜀")
        return False

    # blog-assets 저장
    new_url = upload_to_assets(img_bytes, title)
    if not new_url:
        print(f"  ❌ '{title[:30]}' - 저장소 업로드 실패, 건너뜀")
        return False

    # 본문 교체
    new_content = content
    img_tag = f'<img src="{new_url}" alt="{title}" style="width:100%;max-width:800px;border-radius:12px;margin:20px 0 16px;">'

    if has_no_image(content):
        new_content = img_tag + "\n" + content
    else:
        # 기존 img src 교체
        new_content = re.sub(
            r'(<img[^>]+src=["\'])([^"\']+)(["\'])',
            lambda m: m.group(1) + new_url + m.group(3),
            content,
            count=1
        )

    try:
        service.posts().patch(
            blogId=blog_id, postId=post_id,
            body={"content": new_content}
        ).execute()
        print(f"  ✅ '{title[:30]}' 복구 완료!")
        return True
    except Exception as e:
        print(f"  ❌ 글 수정 실패: {e}")
        return False

# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
def main():
    if not BLOG_URL or not TOKEN_B64:
        print(f"  ⚠️ [{NAMESPACE}] BLOG_URL 또는 TOKEN_JSON_BASE64 없음, 건너뜀")
        return

    print(f"\n{'='*60}")
    print(f"🩹 [{NAMESPACE}] {BLOG_URL} 복구 시작")
    print(f"{'='*60}")

    # 인증
    try:
        token_json = base64.b64decode(TOKEN_B64).decode("utf-8")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json',
                                         delete=False, encoding='utf-8') as tf:
            tf.write(token_json)
            token_file = tf.name
        creds = Credentials.from_authorized_user_file(
            token_file, ['https://www.googleapis.com/auth/blogger'])
        service = build('blogger', 'v3', credentials=creds)
        blog_id = service.blogs().getByUrl(
            url=f"http://{BLOG_URL}").execute()['id']
        print(f"  ✅ 블로그 연결 성공! ID: {blog_id}")
    except Exception as e:
        print(f"  ❌ 연결 실패: {e}")
        return

    # 글 목록
    try:
        result = service.posts().list(
            blogId=blog_id, status=['LIVE', 'SCHEDULED'],
            maxResults=MAX_POSTS, fetchBodies=True
        ).execute()
        posts = result.get('items', [])
        print(f"  📚 {len(posts)}개 글 확인 중...")
    except Exception as e:
        print(f"  ❌ 글 목록 조회 실패: {e}")
        return

    repaired = 0
    skipped  = 0

    for i, post in enumerate(posts):
        title   = post.get('title', '')
        content = post.get('content', '')

        # 복구 필요 여부 판단
        needs_repair = False

        if has_no_image(content):
            print(f"\n  🔧 [{i+1}/{len(posts)}] 이미지 없음: '{title[:35]}'")
            needs_repair = True
        else:
            img_srcs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content)
            for src in img_srcs:
                if is_broken_image(src):
                    print(f"\n  🔧 [{i+1}/{len(posts)}] 깨진 이미지: '{title[:35]}'")
                    print(f"      현재 이미지: {src[:70]}")
                    needs_repair = True
                    break

        if not needs_repair:
            print(f"  ✅ [{i+1}/{len(posts)}] 정상: '{title[:35]}'")
            time.sleep(1)
            continue

        success = repair_post_image(service, blog_id, post)
        if success:
            repaired += 1
        else:
            skipped += 1

        # 글마다 8초 대기 (Pollinations 과부하 방지)
        time.sleep(8)

    print(f"\n{'='*60}")
    print(f"🏁 [{NAMESPACE}] 완료! 복구: {repaired}개 / 실패: {skipped}개 / 전체: {len(posts)}개")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
