import re
import gov_bot as bot
IMAGES = {
 "4217510444514950464": "https://raw.githubusercontent.com/b847994-a11y/blog-assets/main/gov/jungnang-birth-gift-4217510444514950464.png",
 "7156853982828390247": "https://raw.githubusercontent.com/b847994-a11y/blog-assets/main/gov/seoul-disability-lifelong-learning-7156853982828390247.png",
}
service=bot.get_blogger_service()
blog_url=bot.BLOG_URL if bot.BLOG_URL.startswith(("http://","https://")) else "https://"+bot.BLOG_URL
blog_id=service.blogs().getByUrl(url=blog_url).execute()["id"]
for post_id,image in IMAGES.items():
 post=service.posts().get(blogId=blog_id,postId=post_id).execute()
 content=re.sub(r"<img\b[^>]*>", '<img src="'+image+'" alt="Article cover image" style="max-width:100%;height:auto;" />',post.get("content",""),count=1,flags=re.I)
 service.posts().update(blogId=blog_id,postId=post_id,body={"title":post["title"],"content":content}).execute()
 print("updated",post_id)
