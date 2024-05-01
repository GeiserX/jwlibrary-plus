
from bs4 import BeautifulSoup
import requests

def w_extract_html(url, get_all):
    html = requests.get(url).text
    soup = BeautifulSoup(html, features="html5lib")
    title = soup.find("h1").text
    classArticleId = soup.find("article", {"id" : "article"}).get("class")
    articleId = next(x for x in classArticleId if x.startswith("iss"))[4:] + "00"
    articleN = soup.find("p", {"id":"p1"}).text

    if get_all:
        base_text = soup.find("p", {"id":"p3"}).text
        song = soup.find("p",{"id":"p4"}).text
        summary = soup.find("div", {"id": "footnote1"}).find("p").text
        documentId = soup.find("input", {"name": "docid"}).get("value")
        p_elements = soup.find("div", {"class":"bodyTxt"})
        questions = p_elements.find_all("p", {"class": lambda x: x and x.startswith("qu")})
        paragraphs = p_elements.find_all("p", {"class": lambda x: x and x.startswith("p")})

        # Example q_map = {0 : [q1, [p1]], 1 : [q2&3, [p2, p3]]}
        q_map = {}
        i = 0
        for q in questions:
            q_map[i] = [q]
            q_map[i].append([p for p in paragraphs if p.has_attr('data-rel-pid') if p.get('data-rel-pid').strip('[]') in q.get('data-pid')])
            i = i+1
        
        return title, base_text, song, summary, questions, documentId, articleId, q_map
    else:
        return title, articleId, articleN

if __name__ == "__main__":
    w_extract_html("https://www.jw.org/es/biblioteca/revistas/atalaya-estudio-noviembre-2023/C%C3%B3mo-mantener-fuerte-el-amor-que-nos-tenemos/", True)