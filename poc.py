import uuid
import pytz
import os
import zipfile
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
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.callbacks import get_openai_callback # TODO


langchain.llm_cache = SQLiteCache(database_path="langchain.db")

# Current variables which will not be variables
url = "https://www.jw.org/es/biblioteca/revistas/atalaya-estudio-febrero-2023/Mantengan-su-buen-juicio-y-est%C3%A9n-vigilantes/"
telegram_user = "850003"

html = requests.get(url).text
soup = BeautifulSoup(html, features="html5lib")

title = soup.find("h1").text
base_text = soup.find("p", {"id":"p3"}).text
song = soup.find("p",{"id":"p4"}).text
summary = soup.find("div", {"id": "footnote1"}).find("p").text
documentId = soup.find("input", {"name": "docid"}).get("value")
classArticleId = soup.find("article", {"id" : "article"}).get("class")
articleId = next(x for x in classArticleId if x.startswith("iss"))[4:] + "00"
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

questions = """
    0. La respuesta directa, breve y concisa a la pregunta principal.
    1. Una ilustración o ejemplo para explicar algún punto principal del párrafo
    2. Una experiencia en concreto, aportando referencias exactas, que esté muy relacionada con el párrafo
    3. ¿Qué me enseña este párrafo sobre Jehová?
    4. Una explicación sobre uno de los textos que aparezcan, que aplique al párrafo. Usa la Biblia de Estudio de los Testigos de Jehová.
    5. ¿Cómo poner en práctica el contenido del párrafo?
    6. Algún comentario adicional que no responda la pregunta principal y que sea de utilidad"""
llm = OpenAI(model_name="gpt-3.5-turbo")
prompt = ChatPromptTemplate.from_messages([ # Make questions modifiable by user input
    SystemMessagePromptTemplate.from_template("""
    Eres un asistente que únicamente usa jw.org y las publicaciones de los Testigos de Jehová para mejorar la preparación de reuniones.
    Yo estoy preparándome la Atalaya, edición de estudio, de los Testigos de Jehová.
    Proveerás información extra proveniente de la literatura disponible en cada uno de los párrafos que te voy a ir mandando en los sucesivos prompts.
    La Atalaya de esta semana se titula {0}, se basa en el texto de {1}, cantaremos la '{2}', y el resumen es el siguiente: 
    {3}
    Para cada pregunta y párrafo o párrafos que te vaya enviando a partir de ahora, responderás en una lista lo siguiente:
    {4}""".format(title, base_text, song, summary, questions)),
    MessagesPlaceholder(variable_name="history"),
    HumanMessagePromptTemplate.from_template("{input}")
])

notes = {}
i=0
for q in q_map.values():
    conversation = ConversationChain(llm=llm, verbose=True, memory=ConversationBufferMemory(return_messages=True), prompt=prompt)
    flattened_paragraph = ""
    for p in q[1]:
        flattened_paragraph = flattened_paragraph + p.text
    notes[i] = conversation.predict(input="Pregunta: {0} -- Párrafo(s): {1}".format(q[0].text, flattened_paragraph))
    #if i==0: break # DELETE, TODO
    i=i+1


############################
### WRITE JWLIBRARY FILE ###
############################

now = datetime.datetime.now(pytz.timezone('Europe/Madrid'))
now_date = now.strftime("%Y-%m-%d")
now_iso = now.isoformat("T", "seconds")
j = '{{"name":"jwlibrary-plus-backup_{0}","creationDate":"{1}","version":1,"type":0,"userDataBackup":{{"lastModifiedDate":"{2}","deviceName":"jwlibrary-plus","databaseName":"userData.db","schemaVersion":8}}}}'.format(now_date, now_date, now_iso)
manifest = json.loads(j) #DELETED HASH value b87840c4b4ac4cd30f104b8effc2dd9cc047e135a16658f3814f97fa6b17e3f5 in "j"

with open('manifest.json', 'w') as f:
    json.dump(manifest, f)


db_file = "userData.db"
connection = sqlite3.connect(db_file)
cursor = connection.cursor()

cursor.execute("""INSERT INTO Location (LocationId, DocumentId, IssueTagNumber, KeySymbol, MepsLanguage, Type, Title)
VALUES (1, {0}, {1}, "w", 1, 0, "{2}");""".format(documentId, articleId, title))

cursor.execute("INSERT INTO Tag ('TagId', 'Type', 'Name') VALUES ('2', '1', 'jwlibrary-plus')")

for i in notes:
    uuid_value = str(uuid.uuid4())
    uuid_value2 = str(uuid.uuid4())

    cursor.execute("""INSERT INTO UserMark ('UserMarkId', 'ColorIndex', 'LocationId', 'StyleIndex', 'UserMarkGuid', 'Version')
    VALUES ('{0}', '2', '1', '0', '{1}', '1');""".format(i+1,uuid_value))

    cursor.execute ("""INSERT INTO "BlockRange" ("BlockRangeId", "BlockType", "Identifier", "StartToken", "EndToken", "UserMarkId")
    VALUES ('{0}', '1', '{1}', '0', '100', '{2}');""".format(i+1, questions[i].get("data-pid"), i+1))

    cursor.execute("""INSERT INTO Note ("NoteId", "Guid", "UserMarkId", "LocationId", "Title", "Content", "LastModified", "BlockType", "BlockIdentifier") 
    VALUES ('{0}', '{1}', '{2}', '1', '{3}', '{4}', '{5}', '1', '{6}');""".format(i+1, uuid_value2, i+1, questions[i].text, notes[i], now_iso, questions[i].get("data-pid")))

    cursor.execute("INSERT INTO TagMap ('TagMapId', 'NoteId', 'TagId', 'Position') VALUES ('{0}', '{1}', '2', '{2}')".format(i+1,i+1,i))

cursor.execute("UPDATE LastModified SET LastModified = '{0}'".format(now_iso))

connection.commit()
connection.close()

zf = zipfile.ZipFile("jwlibrary-plus-{0}.jwlibrary".format(documentId), "w")
zf.write("userData.db")
zf.write("manifest.json")
zf.close()