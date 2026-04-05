import asyncio
import json
from job_assist_skill.scraper import BrowserManager, HiringPostSearcher
from job_assist_skill import keywords as kw as kw

async def quick_search():
    async with BrowserManager(headless=False, stealth=True) as browser:
        await browser.load_session('linkedin_session.json')
        await asyncio.sleep(2)
        
        searcher = HiringPostSearcher(browser.page)
        
        posts = await searcher.search_for_hiring(
            roles=['software engineer'],
            locations=['Remote', 'Saudi Arabia'],
            max_hours_age=24,
            posts_per_query=5,
            min_posts=3,
            max_time_per_query=45,
        )
        
        print(f'Found {len(posts)} posts')
        print()
        
        for i, post in enumerate(posts):
            print(f'{i+1}. Author: {post.author_name}')
            print(f'   Company: {post.company_name}')
            print(f'   Locations: {post.locations}')
            print(f'   URL: {post.linkedin_url}')
            text_preview = (post.text or '')[:100]
            print(f'   Text: {text_preview}...')
            print()
        
        return posts

if __name__ == '__main__':
    posts = asyncio.run(quick_search())
    
    if posts:
        print('=== Summary ===')
        for p in posts:
            print(f"- {p.author_name} | {p.company_name} | {p.locations}")
