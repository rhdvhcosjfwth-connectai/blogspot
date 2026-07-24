# -*- coding: utf-8 -*-
import re
import libme_bot

OFFICIAL = [
    (('cu', '??'), 'https://cu.bgfretail.com/'),
    (('?????', '7-eleven', '????'), 'https://www.7-eleven.co.kr/'),
    (('?????',), 'https://www.coffeebeankorea.com/'),
    (('????',), 'https://www.mcdonalds.co.kr/'),
    (('???24',), 'https://www.emart24.co.kr/'),
    (('gs25',), 'https://gs25.gsretail.com/'),
]
def official(title):
    low=title.lower()
    for keys,url in OFFICIAL:
        if any(k.lower() in low for k in keys): return url
    return None
service=libme_bot.get_blogger_service()
url = libme_bot.BLOG_URL if libme_bot.BLOG_URL.startswith(('http://', 'https://')) else 'https://' + libme_bot.BLOG_URL
blog_id=service.blogs().getByUrl(url=url).execute()['id']
token=None
while True:
    page=service.posts().list(blogId=blog_id, maxResults=100, pageToken=token).execute()
    for post in page.get('items',[]):
        content=post.get('content',''); title=post.get('title',''); target=official(title)
        changed=re.sub(r'<img\b[^>]*>', '', content, flags=re.I)
        if target:
            changed=re.sub(r'(<a\b[^>]*style=["\'][^"\']*display\s*:\s*inline-block[^"\']*["\'][^>]*href=["\'])[^"\']*(["\'][^>]*>)', r'\g<1>'+target+r'\2', changed, flags=re.I)
        else:
            changed=re.sub(r'<a\b[^>]*style=["\'][^"\']*display\s*:\s*inline-block[^"\']*["\'][^>]*>.*?</a>', '', changed, flags=re.I|re.S)
        if changed != content:
            service.posts().update(blogId=blog_id, postId=post['id'], body={'title':title,'content':changed}).execute()
            print('repaired',post['id'],title)
    token=page.get('nextPageToken')
    if not token: break
