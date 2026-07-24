import os
import sys
import re
import json
import time
import base64
import requests
import importlib.util

sys.stdout.reconfigure(encoding='utf-8')

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

def get_blogger_service_from_json(token_json_str):
    try:
        creds_data = json.loads(token_json_str)
        creds = Credentials.from_authorized_user_info(creds_data)
        return build('blogger', 'v3', credentials=creds)
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None

def get_blog_id(service, blog_url):
    try:
        blog = service.blogs().getByUrl(url=blog_url).execute()
        return blog['id']
    except Exception as e:
        print(f"Error getting blog ID for {blog_url}: {e}")
        return None

def repair_post_links_only(bot_module_name, blog_url, token_json_str, namespace):
    print(f"\n=======================================================")
    print(f"🔗 Repairing Links ONLY (Preserving Images) for: {blog_url}")
    print(f"=======================================================")
    
    spec = importlib.util.spec_from_file_location("current_bot", bot_module_name)
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    
    service = get_blogger_service_from_json(token_json_str)
    if not service:
        print(f"❌ Failed to get Blogger service for {blog_url}")
        return
        
    blog_id = get_blog_id(service, blog_url)
    if not blog_id:
        print(f"❌ Failed to get Blog ID for {blog_url}")
        return
        
    posts_res = service.posts().list(blogId=blog_id, maxResults=50).execute()
    posts = posts_res.get('items', [])
    print(f"📚 Found {len(posts)} posts. Fixing download bugs & inserting missing official link buttons...")
    
    success_count = 0
    for i, post in enumerate(posts):
        title = post.get('title', '')
        content = post.get('content', '')
        post_id = post.get('id')
        
        # 1. Clean ONLY old button containers and earthdaizer links (Keep images intact!)
        clean_content = re.sub(r'<a[^>]*class="[^"]*btn[^"]*"[^>]*>.*?</a>', '', content, flags=re.DOTALL)
        clean_content = clean_content.replace("https://earthdaizer.com/", "https://www.gov.kr/")
        clean_content = clean_content.replace("https://earthdaizer.com", "https://www.gov.kr")
        
        text_only = re.sub(r'<[^>]+>', ' ', clean_content).strip()
        
        # 2. Extract Official Target Link (Blocking .do file downloads!)
        target_url = None
        if hasattr(bot, 'get_actual_application_link'):
            target_url = bot.get_actual_application_link(title, text_only)
        elif hasattr(bot, 'get_actual_ai_trial_link'):
            target_url = bot.get_actual_ai_trial_link(title, text_only)
            
        if target_url:
            print(f"  [{i+1}/{len(posts)}] {title[:30]}... ➡️ 🔗 {target_url}")
            clean_content = bot.insert_buttons_to_content(clean_content, target_url)
        else:
            fallback = "https://www.gov.kr"
            print(f"  [{i+1}/{len(posts)}] {title[:30]}... ➡️ 🔗 Fallback {fallback}")
            clean_content = bot.insert_buttons_to_content(clean_content, fallback)
            
        post['content'] = clean_content
        
        # Update Post via Blogger API
        updated = None
        for attempt in range(3):
            try:
                updated = service.posts().update(blogId=blog_id, postId=post_id, body=post).execute()
                if updated:
                    break
            except Exception as err:
                print(f"  ⚠️ Update attempt {attempt+1} error: {err}. Retrying in 3s...")
                time.sleep(3)
                
        if updated:
            success_count += 1
            
        time.sleep(2.5)

    print(f"\n🎉 Bulletproof link repair finished for {blog_url}: {success_count}/{len(posts)} updated.")

if __name__ == "__main__":
    blog_url = os.environ.get('BLOG_URL')
    token_b64 = os.environ.get('TOKEN_JSON_BASE64')
    namespace = os.environ.get('BLOG_IMAGE_NAMESPACE', 'welfare')
    bot_script = "libme_bot.py"
    
    if blog_url and token_b64:
        try:
            token_json_str = base64.b64decode(token_b64).decode('utf-8')
            repair_post_links_only(bot_script, blog_url, token_json_str, namespace)
        except Exception as e:
            print(f"Error executing link repair: {e}")
