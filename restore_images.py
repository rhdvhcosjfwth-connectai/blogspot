# -*- coding: utf-8 -*-
# 🩹 이미 발행된 블로그스팟 글들 중에서 깨진 이미지(loremflickr, 깃허브 엑스박스, base64 등)를
# 진짜 AI가 그린 이쁘고 다른 그림 주소(pollinations.ai 다이렉트 png 링크)로 싹 치유해주는 복구 도구!
import os
import re
import sys
import json
import urllib.parse
import urllib.request
import html
import random
import requests
import base64
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

sys.stdout.reconfigure(encoding='utf-8')

# 📁 블로그스팟 권한 범위
SCOPES = ['https://www.googleapis.com/auth/blogger']

# 📸 이미지 URL을 다운로드 받아서 Base64 데이터로 변환하는 함수
def get_image_as_base64(image_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(image_url, headers=headers, timeout=25)
        if response.status_code == 200:
            encoded_data = base64.b64encode(response.content).decode('utf-8')
            return f"data:image/jpeg;base64,{encoded_data}"
        else:
            print(f"⚠️ 이미지 다운로드 실패 (상태코드: {response.status_code})")
            return None
    except Exception as e:
        print(f"⚠️ 이미지 다운로드 중 오류 발생: {e}")
        return None

# 🔄 1순위 AI 이미지 다운로드 시도, 실패 시 2순위 백업 이미지 시도
def fetch_image_base64(prompt_url, seed):
    print("📸 이미지 생성 및 다운로드(Base64 인코딩) 시작...")
    # 1. 1순위 AI 이미지 시도
    base64_data = get_image_as_base64(prompt_url)
    if base64_data:
        print("✅ 1순위 AI 이미지 인코딩 성공!")
        return base64_data
        
    # 2. 실패 시 2순위 백업 이미지 시도
    print("🔄 1순위 AI 이미지 다운로드 실패! 백업 이미지(Picsum)로 시도합니다...")
    backup_url = f"https://picsum.photos/800/400?random={seed}"
    base64_data = get_image_as_base64(backup_url)
    if base64_data:
        print("✅ 백업 이미지 인코딩 성공!")
        return base64_data
        
    # 3. 둘 다 실패하면 땜빵으로 원래 주소 그대로 리턴
    print("⚠️ 모든 다운로드 실패! 다이렉트 이미지 주소로 연결합니다.")
    return prompt_url


# 🌐 한글을 영어로 번역해주는 함수 (MyMemory API 사용)
def translate_ko_to_en(text):
    try:
        # 한글, 영어, 숫자, 공백만 남기고 특수문자는 다 없애요
        clean_text = re.sub(r'[^a-zA-Z0-9가-힣\s]', ' ', text).strip()
        # 단어 최대 15개까지만 끊어서 번역 요청해요 (API 한도 방지)
        clean_text = " ".join(clean_text.split()[:15])
        
        if not clean_text:
            return ""
            
        url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode({
            "q": clean_text,
            "langpair": "ko|en"
        })
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            translated = data.get('responseData', {}).get('translatedText', '')
            translated = html.unescape(translated)
            # 영어, 숫자, 공백만 남기고 정리해요
            translated = re.sub(r'[^a-zA-Z0-9\s_]', '', translated).strip()
            # 공백을 언더바로 이어붙여요
            translated = "_".join(translated.split())
            return translated
    except Exception as e:
        print(f"⚠️ 번역 요청 중 살짝 문제가 생겼어요: {e}")
        return ""


# 🩹 한 개의 블로그 주소에 대해 깨진 이미지를 복구하는 함수
def restore_blog_posts(blog_dir, blog_url):
    print(f"\n📢 '{blog_url}' 블로그 복구 작업 시작!")
    
    token_path = 'token.json'
    if not os.path.exists(token_path):
        # 로컬 폴더에 있는 token.json 복사 시도
        local_token = os.path.join(blog_dir, 'token.json')
        if os.path.exists(local_token):
            import shutil
            shutil.copy(local_token, 'token.json')
            print("🔑 로컬 폴더에서 token.json을 복사해왔어요!")
        else:
            print(f"⚠️ 통행증(token.json)이 없어요!")
            return
        
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    service = build('blogger', 'v3', credentials=creds)
    
    # 블로그 ID 조회
    try:
        blog_info = service.blogs().getByUrl(url=f"http://{blog_url}").execute()
        blog_id = blog_info['id']
        print(f"🔑 블로그 ID: {blog_id}")
    except Exception as e:
        print(f"❌ 블로그 정보를 가져오지 못했어요: {e}")
        return

    # 최근 포스트 50개 긁어오기 (예약글+발행글 모두)
    try:
        posts_data = service.posts().list(
            blogId=blog_id, 
            status=['LIVE', 'SCHEDULED'], 
            maxResults=50
        ).execute()
        posts = posts_data.get('items', [])
        print(f"📝 복구할 글 개수: {len(posts)}개 발견")
    except Exception as e:
        print(f"❌ 글 목록 조회 실패: {e}")
        return

    recovered_count = 0

    for idx, post in enumerate(posts):
        post_id = post['id']
        title = post['title']
        content = post.get('content', '')
        
        # 이미지 태그 검색
        img_tags = re.findall(r'<img[^>]+src=["\'](.*?)["\']', content)
        
        need_update = False
        new_content = content
        
        for img_idx, img_src in enumerate(img_tags):
            clean_src = html.unescape(img_src)
            is_bad_image = False
            
            # 아래 조건 중 하나에 걸리면 치료 대상으로 삼음
            # 1. loremflickr (다 똑같은 사진첩 이미지)
            # 2. raw.githubusercontent.com (비공개 깃허브 엑스박스)
            # 3. pollinations.ai 주소 (다이렉트 링크 방식이라 관리 화면 등에서 엑스박스가 떴던 모든 주소들!)
            if "loremflickr.com" in clean_src or "raw.githubusercontent.com" in clean_src or "pollinations.ai" in clean_src:
                is_bad_image = True
                
            if is_bad_image:
                print(f"📸 [{idx+1}] '{title[:20]}' 글에서 치환 대상 이미지 발견! (URL: {clean_src[:50]}...)")
                
                # 번역 함수를 이용해 한글 제목을 영어로 바꿉니다
                translated_title = translate_ko_to_en(title)
                
                if not translated_title:
                    # 만약 번역이 실패하면, 한글 단어들을 인코딩하여 그대로 사용합니다 (Pollinations AI 한글 대응)
                    clean_ko = re.sub(r'[^a-zA-Z0-9가-힣\s]', ' ', title).strip()
                    words = clean_ko.split()[:8]
                    translated_title = "_".join(words)
                
                # 무작위 아트 스타일 결정
                image_styles = ["watercolor_painting", "3D_Pixar_animation_style", "oil_painting", "pencil_sketch", "pop_art", "minimalist_flat_vector", "cyberpunk_neon", "vintage_retro_comic_book", "cinematic_photography", "abstract_modern_art"]
                chosen_style = random.choice(image_styles)
                
                # 봇 분류에 맞게 프롬프트와 여분의 단어를 추가해 줍니다
                if "icinformation" in blog_url:
                    extra_keywords = ["artificial_intelligence", "robot_technology", "future_tech", "computer_science"]
                    keyword = random.choice(extra_keywords)
                    english_prompt = f"{chosen_style}_about_{translated_title}_{keyword}_masterpiece"
                else:
                    extra_keywords = ["korean_welfare", "government_helping_people", "social_service", "support_fund"]
                    keyword = random.choice(extra_keywords)
                    english_prompt = f"{chosen_style}_about_{translated_title}_{keyword}_masterpiece"
                
                encoded_prompt = urllib.parse.quote(english_prompt)
                
                # seed도 고유하게 post_id와 img_idx를 섞어 캐시를 깨뜨립니다.
                seed = int(post_id[-6:]) + img_idx if post_id.isdigit() else random.randint(1, 999999)
                new_img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}_{seed}.png?width=800&height=400&nologo=true&seed={seed}"
                
                # 📥 다운로드하여 base64 데이터로 인코딩한 이미지를 가져옵니다!
                embedded_img = fetch_image_base64(new_img_url, seed)
                
                new_content = new_content.replace(img_src, embedded_img)
                need_update = True

                    
        # 본문이 수정되었다면 블로그스팟에 업데이트 반영
        if need_update:
            try:
                service.posts().patch(
                    blogId=blog_id, 
                    postId=post_id, 
                    body={"content": new_content}
                ).execute()
                print(f"✅ [{idx+1}] '{title[:20]}' 글 이미지 진짜 AI로 복구 완료! 🥳")
                recovered_count += 1
            except Exception as e:
                print(f"❌ [{idx+1}] 블로그스팟 글 수정 업데이트 실패: {e}")
                
    print(f"🏁 '{blog_url}' 블로그 복구 완료! 총 {recovered_count}개 글 치료 성공!")

if __name__ == '__main__':
    print("🩹 옛날 글 깨진 그림 복구기 작동 시작!")
    
    # 봇1 복구
    restore_blog_posts(
        blog_dir=r"C:\후니\네이버자동화프로그램\나만의블로그스팟(완전자동)봇",
        blog_url="icinformationchannel.blogspot.com"
    )
    
    # 봇2 복구
    restore_blog_posts(
        blog_dir=r"C:\후니\네이버자동화프로그램\나만의블로그스팟(완전자동)봇2",
        blog_url="wgiinformationchannel.blogspot.com"
    )
    print("\n🎉 모든 블로그 복구 작업이 끝났습니다!")
