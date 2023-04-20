import requests
from bs4 import BeautifulSoup
import html5lib
from langchain.llms import OpenAI
import langchain
from langchain.cache import InMemoryCache
langchain.llm_cache = SQLiteCache(database_path="langchain.db")

url = "https://www.jw.org/es/biblioteca/revistas/atalaya-estudio-febrero-2023/Mantengan-su-buen-juicio-y-est%C3%A9n-vigilantes/"

html = requests.get(url).text
soup = BeautifulSoup(html, features="html5lib")

title = soup.find("h1").text
base_text = soup.find("p", {"id":"p3"}).text
song = soup.find("p",{"id":"p4"}).text
summary = soup.find("div", {"id": "footnote1"}).find("p").text
p_elements = soup.find("div", {"class":"bodyTxt"})
questions = p_elements.find_all("p", {"id": lambda x: x and x.startswith("q")})
paragraphs = p_elements.find_all("p", {"id": lambda x: x and x.startswith("p")})

# Example q_map = {0 : [q1, [p1]], 1 : [q2&3, [p2, p3]]}
q_map = {}
i = 0
for q in questions:
    q_map[i] = [q]
    q_map[i].append([p for p in paragraphs if p.has_attr('data-rel-pid') if p.get('data-rel-pid').strip('[]') in q.get('data-pid')])
    i = i+1

llm = OpenAI(model_name="gpt-3.5-turbo", n=2, best_of=2)

for q in q_map.values():
    llm(q)
    print(q)


