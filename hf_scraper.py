import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

base_url = 'https://huggingface.co'

class Article:
    def __init__(self, title, arxiv_link, abstract):
        self.title = title
        self.arxiv_link = arxiv_link
        self.abstract = abstract


def en_content(article: Article):
    return f"""
## {article.title}
[{article.title}]({article.arxiv_link})
{article.abstract}
"""

def retrieve_article_list(url):
    response = requests.get(url)
    html_content = response.text

    # 解析HTML内容
    soup = BeautifulSoup(html_content, 'html.parser')

    articles = soup.find_all('article')

    article_list = []
    for article in articles:
        title = article.find('h3').get_text(strip=True)
        link = article.find('a')['href']
        leading_nones = article.find_all('div', class_='leading-none')
        likes_div = None
        for item in leading_nones:
            if item.get('class') == ['leading-none']:
                likes_div = item
                break
        likes = int(likes_div.get_text(strip=True))
        if likes < 25:
            break
        print(f"Title: {title}")
        print(f"Link: {link}")
        print(f"Likes: {likes}")
        print("------")
        one = {'title': title, 'link': base_url + link, 'likes': likes}
        article_list.append(one)
    return article_list

def parse_article(url, title):
    response = requests.get(url)
    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')

    article_abstract = soup.find('p', class_='text-gray-700 dark:text-gray-400')
    abstract = article_abstract.get_text(strip=True)
    arxiv_link = soup.find('a', class_='btn inline-flex h-9 items-center')['href']

    return Article(title, arxiv_link, abstract)

def get_past_month_dates():
    # 获取今天的日期
    today = datetime.today()
    # 计算一个月前的日期
    one_month_ago = today - timedelta(days=15)
    
    # 创建日期列表
    date_list = []
    current_date = today
    while current_date > one_month_ago:
        date_list.append(current_date.strftime('%Y-%m-%d'))
        current_date -= timedelta(days=1)
    
    return date_list

def main():
  output_path = "test"
  days = get_past_month_dates()

  final_results = []
  for day in days:
    print(f"current day: {day}")
    url = base_url + '/papers?date=' + day
    article_list = retrieve_article_list(url)

    for item in article_list:
      article: Article = parse_article(item["link"], item["title"])

      final_results.append(article)
  
  for article in final_results:
    print(f"title: {article.title}, abstract: {article.abstract}")

main()