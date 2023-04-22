import uuid
import shutil
import pytz
import os
import zipfile
import logging
import requests
import json
import datetime
import sqlite3
from bs4 import BeautifulSoup
#import html5lib
import langchain
from langchain.chat_models import ChatOpenAI
from langchain.cache import SQLiteCache
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.callbacks import get_openai_callback # TODO

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

#############################
### BEGIN EXTRACTING HTML ###
#############################

def extract_html(url, get_all):
    logger.info("extract_html - URL: {0} - Full Run: {1}".format(url, get_all))

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
        questions = p_elements.find_all("p", {"id": lambda x: x and x.startswith("q")})
        paragraphs = p_elements.find_all("p", {"id": lambda x: x and x.startswith("p")})

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

##########################
### BEGIN QUERY OPENAI ###
##########################
def query_openai(title, base_text, song, summary, q_map, qs_user):
    logger.info("query_openai  - Title: {0} - Base Text: {1} - Song: {2} - Summary: {3} - Questions Map: {4} - Questions User: {5}".format(title, base_text, song, summary, q_map, qs_user))
    langchain.llm_cache = SQLiteCache(database_path="dbs/langchain.db")

    questions = [f"{i}. {question}" for i, question in enumerate(qs_user, start=1) if question is not None]
    questions_text = "\n".join(questions)

    llm = ChatOpenAI(model_name="gpt-3.5-turbo")
    prompt = ChatPromptTemplate.from_messages([ # Make questions modifiable by user input
        SystemMessagePromptTemplate.from_template("""
Eres un asistente que únicamente usa jw.org y las publicaciones de los Testigos de Jehová para mejorar la preparación de reuniones.
Yo estoy preparándome la Atalaya, edición de estudio, de los Testigos de Jehová.
Proveerás información extra proveniente de la literatura disponible en cada uno de los párrafos que te voy a ir mandando en los sucesivos prompts.
La Atalaya de esta semana se titula {0}, se basa en el texto de {1}, cantaremos la '{2}', y el resumen es el siguiente: 
{3}
Para cada pregunta y párrafo o párrafos que te vaya enviando a partir de ahora, responderás en una lista lo siguiente:
{4}""".format(title, base_text, song, summary, questions_text)),
        MessagesPlaceholder(variable_name="history"),
        HumanMessagePromptTemplate.from_template("{input}")
    ])

    notes = {}
    i=0
    for q in q_map.values():
        conversation = ConversationChain(llm=llm, verbose=False, memory=ConversationBufferMemory(return_messages=True), prompt=prompt)
        flattened_paragraph = ""
        for p in q[1]:
            flattened_paragraph = flattened_paragraph + p.text
        notes[i] = conversation.predict(input="Pregunta: {0} -- Párrafo(s): {1}".format(q[0].text, flattened_paragraph))
        logger.info("query_openai(Note) - Note: {0}".format(notes[i])) # TODO: Reduce logs in the future when everything works stable
        i=i+1
    
    return notes


############################
### WRITE JWLIBRARY FILE ###
############################

def write_jwlibrary(documentId, articleId, title, questions, notes, telegram_user):

    logger.info("write_jwlibrary - Document ID: {0} - Article ID: {1} - Title: {2} - Questions: {3} - Notes: {4} - Telegram User: {5}".format(documentId, articleId, title, questions, notes, telegram_user))

    now = datetime.datetime.now(pytz.timezone('Europe/Madrid'))
    now_date = now.strftime("%Y-%m-%d")
    hour_minute_second = now.strftime("%H-%M-%S")
    now_iso = now.isoformat("T", "seconds")

    dbOriginal = "dbs/userData.db.original"
    dbFromUser = "dbs/userData-{0}-{1}_{2}.db".format(telegram_user, now_date, hour_minute_second)
    shutil.copyfile(src=dbOriginal, dst=dbFromUser)

    j = '{{"name":"jwlibrary-plus-backup_{0}","creationDate":"{1}","version":1,"type":0,"userDataBackup":{{"lastModifiedDate":"{2}","deviceName":"jwlibrary-plus","databaseName":"userData.db","schemaVersion":8}}}}'.format(now_date, now_date, now_iso)
    manifest = json.loads(j) #DELETED HASH value b87840c4b4ac4cd30f104b8effc2dd9cc047e135a16658f3814f97fa6b17e3f5 in "j"

    manifest_file = 'dbs/manifest-{0}-{1}.json'.format(telegram_user, now_date)
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f)

    connection = sqlite3.connect(dbFromUser)
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
        VALUES ('{0}', '{1}', '{2}', '1', '{3}', '{4}', '{5}', '1', '{6}');""".format(i+1, uuid_value2, i+1, questions[i].text, notes[i].replace("'", '"'), now_iso, questions[i].get("data-pid")))

        cursor.execute("INSERT INTO TagMap ('TagMapId', 'NoteId', 'TagId', 'Position') VALUES ('{0}', '{1}', '2', '{2}')".format(i+1,i+1,i))

    cursor.execute("UPDATE LastModified SET LastModified = '{0}'".format(now_iso))

    connection.commit()
    connection.close()

    fileName = "jwlibrary-plus-{0}-{1}.jwlibrary".format(documentId, now_date)
    zf = zipfile.ZipFile(fileName, "w")
    zf.write(dbFromUser, arcname= "userData.db")
    zf.write(manifest_file, arcname="manifest.json")
    zf.close()

    return fileName

def main(url, telegram_user, qs_user) -> None:

    title, base_text, song, summary, questions, documentId, articleId, q_map = extract_html(url, get_all=True)
    notes = query_openai(title, base_text, song, summary, q_map, qs_user)
    filename = write_jwlibrary(documentId, articleId, title, questions, notes, telegram_user)
    
    return filename

if __name__ == "__main__":
    main()

    