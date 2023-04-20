#os.chdir("jwlibrary-plus") 
import requests
import json
import datetime
import sqlite3
from bs4 import BeautifulSoup
import html5lib
import langchain
from langchain.llms import OpenAI
from langchain.cache import SQLiteCache
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import (
    ChatPromptTemplate, 
    MessagesPlaceholder, 
    SystemMessagePromptTemplate, 
    HumanMessagePromptTemplate
)
langchain.llm_cache = SQLiteCache(database_path="langchain.db")
import os


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

##########################
### BEGIN QUERY OPENAI ###
##########################

llm = OpenAI(model_name="gpt-3.5-turbo")
prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template("""
    Eres un asistente que únicamente usa jw.org y las publicaciones de los Testigos de Jehová para mejorar la preparación de reuniones.
    Yo estoy preparándome la Atalaya, edición de estudio, de los Testigos de Jehová.
    Proveerás información extra proveniente de la literatura disponible en cada uno de los párrafos que te voy a ir mandando en los sucesivos prompts.
    La Atalaya de esta semana se titula {0}, se basa en el texto de {1}, cantaremos la canción del cancionero número {2}, y el resumen es el siguiente: 
    {3}
    Para cada pregunta y párrafo o párrafos que te vaya enviando a partir de ahora, responderás en una lista lo siguiente:
    0. La respuesta directa, breve y concisa a la pregunta principal.
    1. Una ilustración o ejemplo para explicar algún punto principal del párrafo
    2. Una experiencia en concreto, aportando referencias exactas, que esté muy relacionada con el párrafo
    3. ¿Qué me enseña este párrafo sobre Jehová?
    4. Una explicación sobre uno de los textos que aparezcan, que aplique al párrafo
    5. ¿Cómo poner en práctica el contenido del párrafo?
    6. Algún comentario adicional que no responda la pregunta principal y que sea de utilidad""".format(title, base_text, song, summary)),
    MessagesPlaceholder(variable_name="history"),
    HumanMessagePromptTemplate.from_template("{input}")
])
conversation = ConversationChain(llm=llm, verbose=True, memory=ConversationBufferMemory(return_messages=True), prompt=prompt)

notes = {}
i=0
for q in q_map.values():
    flattened_paragraph = ""
    for p in q[1]:
        flattened_paragraph = flattened_paragraph + p.text
    notes[i] = conversation.predict(input="Pregunta: {0} -- Párrafo(s): {1}".format(q[0].text, flattened_paragraph))
    if i==1: break
    i=i+1

############################
### WRITE JWLIBRARY FILE ###
############################

now = datetime.datetime.now() #DELETED HASH value b87840c4b4ac4cd30f104b8effc2dd9cc047e135a16658f3814f97fa6b17e3f5
now_date = now.strftime("%Y-%m-%d")
now_iso = now.isoformat("T", "seconds")
j = '{{"name":"jwlibrary-plus-backup_{0}","creationDate":"{1}","version":1,"type":0,"userDataBackup":{{"lastModifiedDate":"{2}","deviceName":"jwlibrary-plus","databaseName":"userData.db","schemaVersion":8}}}}'.format(now_date, now_date, now_iso)
manifest = json.loads(j)

with open('manifest.json', 'w') as f:
    json.dump(manifest, f)


db_file = "userData.db"
connection = sqlite3.connect(db_file)
cursor = connection.cursor()
cursor.execute("""INSERT OR IGNORE INTO Location (LocationId, DocumentId, IssueTagNumber, KeySymbol, MepsLanguage, Type, Title)
VALUES (8, 2023281, 20230200, "w", 1, 0, "Saquémosle el jugo a la lectura de la Biblia");""".format())
cursor.execute("""INSERT OR IGNORE INTO Note ("NoteId", "Guid", "UserMarkId", "LocationId", "Title", "Content", "LastModified", "BlockType", "BlockIdentifier") 
VALUES ('4', 'aaabbbcc-dddd-eeee-ffff-ggghhhiiijjj', '6', '6', 'HOLA', 'Hola', '2023-04-16T19:08:08+00:00', '1', '5');""")

connection.commit()
connection.close()