from datetime import datetime, timedelta
import time

from apscheduler.schedulers.background import BackgroundScheduler
from bson import ObjectId, Binary
from bs4 import BeautifulSoup
from dateutil import parser
import requests
from requests.exceptions import RequestException, Timeout
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.common.by import By
from readability import Document
import base64

client = MongoClient('mongodb://abc1:abc1@54.180.249.140', 27017)
db = client.JungleCom

driver = webdriver.Chrome() # requests의 처음에 내려주는 순수 html만 crawl 하는것이 아닌, 실제 렌더링된 데이터를 crawl을 하기 위해 selenium을 사용

crawl_delay = timedelta(minutes=30) # 크롤링한 job에 딜레이 추가할 시간


# 스케줄러로 작동시킬 크롤링 함수
def rss_crawling():
    try:
        job = find_job()    # crawl_jobs 에서 크롤링이 가능한 job을 찾아보기
        if job is not None:
            print("Crawl job found")
            soup = crawl_from_job(job)
            if soup is not None:
                insert_new_post(soup, job)
        else:
            print("No crawl job found")
    except Exception as e:
        print(f"job crawl error : {e}")
    finally:
        if job is not None:
            release_job(job)    # 크롤링한 job에 crawl_delay와 lock 풀기

# 현재 crawl_jobs 에서 크롤링이 가능한 job을 찾아보는 함수
def find_job():
    result = db.crawl_jobs.find_one_and_update(
        {
            "check_date": {"$lt": datetime.now()},  # check_date가 현재시간보다 과거이면서, 다른 크롤러가 작업하고 있지 않은 job을 찾기 위한 locked : false
            "locked": False
        },
        {
            "$set": {"locked": True}    # 크롤 하는동안 다른 크롤러가 크롤링을 하는 동시성 중복을 방지하기 위해 locked을 true
        }
    )
    if result is None:
        return None
    else:
        return result

# 작업 완료한 job을 정리하는 함수수
def release_job(job):
    db.crawl_jobs.update_one(
        {
            "_id" : ObjectId(job["_id"])
        },
        {
            "$set" : {
                "check_date" : datetime.now() + crawl_delay,    # check_date에 현재시간 + crawl_delay로 job에 딜레이 부여
                "locked" : False    # lock한 필드를 false
            }
        }
    )
    return

# job의 데이터로 크롤을 시도하는 함수
def crawl_from_job(job):
    user = db.users.find_one({"_id": ObjectId(job["blog_id"])})
    url = user["blog"]
    
    # url request가 실패할 수도 있기 때문에 예외처리
    try:
        response = requests.get(url, timeout=10)    # url 요청이 10초동안 응답이 없을 경우 throw
    except Timeout:
        print(f"[TIMEOUT] rss url request timeout : {url}")
        return None
    except RequestException as e:
        print(f"[REQUEST ERROR] {e}: {url}")
        return None
    
    soup = BeautifulSoup(response.text, "xml")
    if soup.find("rss") or soup.find("feed"):
        print("RSS data load success")
        return soup
    else:
        print("RSS data load failed")
        return None

# item으로 posts 컬렉션을 find해서 없을 경우, insert 하는 함수
def insert_new_post(soup, job):
    for item in soup.find_all("item"):
        if db.posts.find_one({"guid": item.find("guid").text}) is None:            
            html_combined = get_all_frame_sources(item.find("guid").text)
            
            userId = ObjectId(job["blog_id"])
            viewToggle = True
            title = item.find("title").text
            guid = item.find("guid").text
            pubDate = parser.parse(item.find('pubDate').text)
            try:
                page_soup = BeautifulSoup(html_combined, "html5lib")
                ogImage_url = page_soup.select_one('meta[property="og:image"]').get("content")
                ogImage_get = requests.get(ogImage_url)
                #ogImage = Binary(ogImage_get.content)
                ogImage = base64.b64encode(ogImage_get.content).decode('utf-8')
            except:
                ogImage = None
            try:
                doc = Document(html_combined)
                body_text = BeautifulSoup(doc.summary(), "lxml").get_text(" ", strip=True)
                description = " ".join(body_text.split())   # 글 본문을 추출출
            except:
                description = None

            db.posts.insert_one(
                {
                    "userId": userId,
                    "viewToggle": viewToggle,
                    "title": title,
                    "guid": guid,
                    "pubDate": pubDate,
                    "ogImage": ogImage,
                    "description": description,
                }
            )
        # else:
        #     break

def get_all_frame_sources(guid):
    driver.get(guid)
    sources = []

    def recurse(ctx):
        sources.append(ctx.page_source)
        for iframe in ctx.find_elements(By.CSS_SELECTOR, "iframe, frame"):
            try:
                ctx.switch_to.frame(iframe)
                recurse(ctx)
                ctx.switch_to.parent_frame()
            except Exception:
                ctx.switch_to.parent_frame()
    recurse(driver)
    return "\n".join(sources)

if __name__ == '__main__':
    sched = BackgroundScheduler()   # 스케쥴러를 백그라운드로 동작하게
    sched.add_job(rss_crawling, 'interval', seconds=5, id="crawling_1") # 스케쥴러의 작업을 등록
    sched.start()
    print("Scheduler started.")
    while True:
        time.sleep(1000)    # 메인 스레드가 종료되면 백그라운드도 중료되기 때문에 while
        
        
        
# ------------------------ lock true 일 떄 리미트 타임 추가하기
# ------------------------ 메인스레드 while true는 불안정 하니까 생각해보기