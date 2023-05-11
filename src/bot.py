import logging
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import requests
import gzip
import shutil
import pytz
import locale
import sqlite3
import validators
from urllib.parse import urlparse
import sys
import core_worker
from collections import Counter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

init_questions=["Una ilustración o ejemplo para explicar algún punto principal del párrafo",
                "Una experiencia en concreto, aportando referencias exactas de jw.org, que esté muy relacionada con el párrafo",
                "Una explicación sobre uno de los textos que aparezcan, que aplique al párrafo. Usa la Biblia de Estudio de los Testigos de Jehová"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("START - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))

    if user.is_bot:
        await update.message.reply_text("Los bots no están permitidos")
        return

    await update.message.reply_html(rf"""¡Bienvenido! 😊

Este bot le ayudará a prepararse las reuniones usando técnicas avanzadas de Inteligencia Artificial, aplicadas especialmente a la relación de datos en la literatura de la organización.

<u>El funcionamiento es el siguiente</u>:

  1. Introduzca la  fecha de la Atalaya que quiera preparar con el comando /date_select. Como alternativa, también existe la opción de proporcionar una URL de la propia Atalaya mediante /url_select [URL]

  2. Introduzca las preguntas que quiera hacer. Defina las preguntas y se aplicarán a <b>todos</b> los párrafos, con un máximo de 10. Por defecto, hay 3 preguntas incluidas. Se usa con /Q1 [PREGUNTA_1], /q2 [PREGUNTA_2].... Para consultar las preguntas configuradas, usa /q_show

  3. <b>Si no quiere perder datos</b>, envíe su archivo de copia de seguridad desde su aplicación de JW Library en formato <code>.jwlibrary</code> usando /backup_send y acto seguido enviando el archivo. Recomendamos que el artículo que quiera prepararse esté vacío para evitar problemas de posible corrupción de datos.
  
  4. Una vez haya elegido sus parámetros, ejecute /w_prepare y espere unos minutos a que se genere el archivo <code>.jwlibrary</code>
  
  5. Descárguelo y restaure esta copia en su app JW Library.

<u>Descargo de Responsabilidad:</u>
El software aquí presente se ofrece tal cual, sin ninguna garantía. Licencia MIT.
<u>Nota Importante:</u>
Cada vez que ejecute /start , sus preguntas guardadas se <b>borrarán</b> y comenzará con las que el software ofrece por defecto.""")
    
    
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("INSERT OR IGNORE INTO Main (UserId) VALUES ('{0}')".format(user.id))
    cursor.execute("UPDATE Main SET UserName = '{0}', FirstName = '{1}', LastName = '{2}', LangCodeTelegram = '{3}', IsBot = '{4}' WHERE UserId = '{5}'".format(user.username, user.first_name, user.last_name, user.language_code, user.is_bot, user.id)) # TODO: Delete line of code in a year or so, this was to not remove the already present db in production
    cursor.execute("UPDATE Main SET Q1 = '{0}', Q2 = '{1}', Q3 = '{2}', Q4 = null, Q5 = null, Q6 = null, Q7 = null, Q8 = null, Q9 = null, Q10 = null WHERE UserId = {3}".format(init_questions[0], init_questions[1], init_questions[2], user.id))
    connection.commit()
    connection.close()


async def select_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Testeando URL, espere por favor")
    url = context.args[0]
    user = update.effective_user
    logger.info("URL - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - URL: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, url))
    if(validators.url(url)):
        u = urlparse(url)
        if(u.netloc == "www.jw.org"):
            connection = sqlite3.connect("dbs/main.db")
            cursor = connection.cursor()
            cursor.execute("UPDATE Main SET Url = '{0}' WHERE UserId = {1}".format(url, user.id))
            connection.commit()
            connection.close()
            title, articleId, articleN = core_worker.w_extract_html(url, get_all=False)
            articleNformatted = articleN.lower().split(" ")[-1]
            await update.message.reply_html("URL guardada.\nEn esta URL se encuentra la revista del año <b>{0}</b>, número <b>{1}</b>, artículo de estudio <b>{2}</b>.\nEl título de la Atalaya es <b>{3}</b>".format(articleId[:4], articleId[4:-2], articleNformatted, title))
        else:
            await update.message.reply_text("No es un una URL de www.jw.org")
    else:
        await update.message.reply_text("No es un una URL válida")


async def q1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:]).replace('"', '').replace("'", "").replace(";", "").replace("(", "").replace(")", "") # TODO: Prevent user from messing with the input
    user = update.effective_user
    logger.info("Q1 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 200):
        function_name = sys._getframe().f_code.co_name.upper()
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(function_name, question, user.id))
        connection.commit()
        connection.close()
        await update.message.reply_text("Pregunta {0} guardada correctamente".format(function_name[1:]))
    else:
        await update.message.reply_text("La pregunta debe tener menos de 200 caracteres")



async def q2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q2 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 200):
        function_name = sys._getframe().f_code.co_name.upper()
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT Q{0} FROM Main WHERE UserId = {1}".format(int(function_name[1:])-1, user.id))
        prev_q = cursor.fetchall()
        if(prev_q == [(None,)] or prev_q == []):
            await update.message.reply_text("Rellene la pregunta anterior o anteriores antes de guardar la siguiente")
        else:
            cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(function_name, question, user.id))
            connection.commit()
            connection.close()
            await update.message.reply_text("Pregunta {0} guardada correctamente".format(function_name[1:]))
    else:
        await update.message.reply_text("La pregunta debe tener menos de 200 caracteres")
        

async def q3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q3 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 200):
        function_name = sys._getframe().f_code.co_name.upper()
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT Q{0} FROM Main WHERE UserId = {1}".format(int(function_name[1:])-1, user.id))
        prev_q = cursor.fetchall()
        if(prev_q == [(None,)] or prev_q == []):
            await update.message.reply_text("Rellene la pregunta anterior o anteriores antes de guardar la siguiente")
        else:
            cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(function_name, question, user.id))
            connection.commit()
            connection.close()
            await update.message.reply_text("Pregunta {0} guardada correctamente".format(function_name[1:]))
    else:
        await update.message.reply_text("La pregunta debe tener menos de 200 caracteres")
        
        
async def q4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q4 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 200):
        function_name = sys._getframe().f_code.co_name.upper()
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT Q{0} FROM Main WHERE UserId = {1}".format(int(function_name[1:])-1, user.id))
        prev_q = cursor.fetchall()
        if(prev_q == [(None,)] or prev_q == []):
            await update.message.reply_text("Rellene la pregunta anterior o anteriores antes de guardar la siguiente")
        else:
            cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(function_name, question, user.id))
            connection.commit()
            connection.close()
            await update.message.reply_text("Pregunta {0} guardada correctamente".format(function_name[1:]))
    else:
        await update.message.reply_text("La pregunta debe tener menos de 200 caracteres")
        

async def q5(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q5 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 200):
        function_name = sys._getframe().f_code.co_name.upper()
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT Q{0} FROM Main WHERE UserId = {1}".format(int(function_name[1:])-1, user.id))
        prev_q = cursor.fetchall()
        if(prev_q == [(None,)] or prev_q == []):
            await update.message.reply_text("Rellene la pregunta anterior o anteriores antes de guardar la siguiente")
        else:
            cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(function_name, question, user.id))
            connection.commit()
            connection.close()
            await update.message.reply_text("Pregunta {0} guardada correctamente".format(function_name[1:]))
    else:
        await update.message.reply_text("La pregunta debe tener menos de 200 caracteres")
        

async def q6(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q6 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 200):
        function_name = sys._getframe().f_code.co_name.upper()
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT Q{0} FROM Main WHERE UserId = {1}".format(int(function_name[1:])-1, user.id))
        prev_q = cursor.fetchall()
        if(prev_q == [(None,)] or prev_q == []):
            await update.message.reply_text("Rellene la pregunta anterior o anteriores antes de guardar la siguiente")
        else:
            cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(function_name, question, user.id))
            connection.commit()
            connection.close()
            await update.message.reply_text("Pregunta {0} guardada correctamente".format(function_name[1:]))
    else:
        await update.message.reply_text("La pregunta debe tener menos de 200 caracteres")
        

async def q7(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q7 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 200):
        function_name = sys._getframe().f_code.co_name.upper()
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT Q{0} FROM Main WHERE UserId = {1}".format(int(function_name[1:])-1, user.id))
        prev_q = cursor.fetchall()
        if(prev_q == [(None,)] or prev_q == []):
            await update.message.reply_text("Rellene la pregunta anterior o anteriores antes de guardar la siguiente")
        else:
            cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(function_name, question, user.id))
            connection.commit()
            connection.close()
            await update.message.reply_text("Pregunta {0} guardada correctamente".format(function_name[1:]))
    else:
        await update.message.reply_text("La pregunta debe tener menos de 200 caracteres")
        

async def q8(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q8 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 200):
        function_name = sys._getframe().f_code.co_name.upper()
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT Q{0} FROM Main WHERE UserId = {1}".format(int(function_name[1:])-1, user.id))
        prev_q = cursor.fetchall()
        if(prev_q == [(None,)] or prev_q == []):
            await update.message.reply_text("Rellene la pregunta anterior o anteriores antes de guardar la siguiente")
        else:
            cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(function_name, question, user.id))
            connection.commit()
            connection.close()
            await update.message.reply_text("Pregunta {0} guardada correctamente".format(function_name[1:]))
    else:
        await update.message.reply_text("La pregunta debe tener menos de 200 caracteres")


async def q9(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q9 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 200):
        function_name = sys._getframe().f_code.co_name.upper()
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT Q{0} FROM Main WHERE UserId = {1}".format(int(function_name[1:])-1, user.id))
        prev_q = cursor.fetchall()
        if(prev_q == [(None,)] or prev_q == []):
            await update.message.reply_text("Rellene la pregunta anterior o anteriores antes de guardar la siguiente")
        else:
            cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(function_name, question, user.id))
            connection.commit()
            connection.close()
            await update.message.reply_text("Pregunta {0} guardada correctamente".format(function_name[1:]))
    else:
        await update.message.reply_text("La pregunta debe tener menos de 200 caracteres")


async def q10(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q10 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 200):
        function_name = sys._getframe().f_code.co_name.upper()
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT Q{0} FROM Main WHERE UserId = {1}".format(int(function_name[1:])-1, user.id))
        prev_q = cursor.fetchall()
        if(prev_q == [(None,)] or prev_q == []):
            await update.message.reply_text("Rellene la pregunta anterior o anteriores antes de guardar la siguiente")
        else:
            cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(function_name, question, user.id))
            connection.commit()
            connection.close()
            await update.message.reply_text("Pregunta {0} guardada correctamente".format(function_name[1:]))
    else:
        await update.message.reply_text("La pregunta debe tener menos de 200 caracteres")


async def show_q(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("SHOW_Q - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))
    
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,Q9,Q10 FROM Main WHERE UserId = {0} LIMIT 1".format(user.id))
    data = cursor.fetchall()[0]
    connection.close()

    num_questions = 10
    questions_text = "<u>Tus preguntas actuales:</u>\n"
    for i in range(num_questions):
        if i < len(data) and data[i] != None:
            questions_text += "{0}. {1}\n".format(i+1, data[i])

    await update.message.reply_html(questions_text)


async def delete_q(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("DELETE_Q - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))
    
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    
    cursor.execute("UPDATE Main SET Q1 = null, Q2 = null, Q3 = null, Q4 = null, Q5 = null, Q6 = null, Q7 = null, Q8 = null, Q9 = null, Q10 = null WHERE UserId = '{0}'".format(user.id))
    connection.commit()
    connection.close()

    await update.message.reply_html("Todas las preguntas que estaban guardadas han sido eliminadas")

async def bulk_q(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: # Not working because there is no \n in input
    logger.info(context.args)
    user = update.effective_user
    questions_user = update.effective_message.text.removeprefix("/q_bulk").removeprefix("@jwlibrary_plus_dev_bot").removeprefix("@jwlibrary_plus_bot").replace('"', '').replace("'", "").replace(";", "").replace("(", "").replace(")", "") # TODO: Prevent user from messing with the input
    logger.info("BULK_Q - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Questions from User: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, questions_user))
    
    await delete_q(update, context)
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()

    i=1
    for q in questions_user.split("\n"):
        if i < 11:
            cursor.execute("UPDATE Main SET Q{0} = '{1}' WHERE UserId = {2}".format(i, q, user.id))
            i+=1
    
    connection.commit()
    connection.close()

    await update.message.reply_text("La serie de preguntas introducida ha sido guardada con éxito")

async def send_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("SEND_BACKUP - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))
    await update.message.reply_html("Envíe su archivo <code>.jwlibrary</code> cuando desee, siempre será tomado en cuenta el último archivo que suba")


async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    file = await context.bot.get_file(update.message.document)
    logger.info("SENDBACKUP - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - File ID: {5} - File Path: {6}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, file.file_id, file.file_path))

    if(file.file_path.endswith(".jwlibrary")):
        await file.download_to_drive('/app/userBackups/{0}.jwlibrary'.format(user.id))
        await update.message.reply_text("Archivo correctamente subido y listo para utilizar")
    else:
        await update.message.reply_text("Formato de archivo erróneo")


async def delete_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("DELETE_BACKUP - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))
    
    os.remove('/app/userBackups/{0}.jwlibrary'.format(user.id))
    await update.message.reply_html("Archivo <code>.jwlibrary</code> eliminado del servidor")


async def describe_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("DESCRIBE_BACKUP - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))
    
    jwfile = "userBackups/{0}.jwlibrary".format(user.id)
    if os.path.isfile(jwfile):
        notesN, inputN, tagMaptN, tagN, bookmarkN, lastModified, userMarkN = core_worker.describe_jwlibrary(user.id)
        await update.message.reply_html("""Estado de su archivo <code>.jwlibrary</code>:
<u>Notas:</u> {0}
<u>Tags individuales:</u> {1}
<u>Notas con tags:</u> {2}
<u>Escritos en cuadros de texto:</u> {3}
<u>Favoritos:</u> {4}
<u>Frases subrayadas:</u> {5}
<u>Última vez modificado:</u> {6}""".format(notesN, tagN, tagMaptN, inputN, bookmarkN, userMarkN, lastModified))
    else:
        await update.message.reply_text("No se ha encontrado su archivo. El fichero se borra tras computar el resultado, envíelo de nuevo actualizado")


async def show_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("SHOW_URL - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT Url FROM Main WHERE UserId = {0} LIMIT 1".format(user.id))
    url = cursor.fetchall()[0][0]
    connection.close()

    logger.info(url)
    if url:
        await update.message.reply_html("La URL configurada es {0}".format(url))
    else:
        await update.message.reply_text("No hay URL configurada")


async def delete_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("DELETE_URL - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))

    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT Url FROM Main WHERE UserId = {0} LIMIT 1".format(user.id))
    url = cursor.fetchall()[0][0]

    if url:
        cursor.execute("UPDATE Main SET Url = null WHERE UserId = '{0}'".format(user.id))
        await update.message.reply_text("URL eliminada")
    #TODO: else condicional. Si proviene de /delete_url , ejecutar else, si proviene de /select_date, no ejecutar else.
    connection.commit()
    connection.close()


async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("SELECT_DATE - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))

    locale.setlocale(locale.LC_ALL, "es_ES") # TODO: Not working in Linux (but it does in Windows), asked in StackOverflow. locale.setlocale(locale.LC_ALL, user.language_code)
    now = datetime.now(pytz.timezone('Europe/Madrid')) # TODO: Check if UTC better
    start = now - timedelta(days=now.weekday())
    week_ranges = []

    for week in range(4):
        end = start + timedelta(days=6)
        if start.month == end.month:
            week_ranges.append(f"{start.strftime('%e')}-{end.strftime('%e de %B')}")
        else:
            week_ranges.append(f"{start.strftime('%e de %B')}-{end.strftime('%e de %B').strip()}")
        start = end + timedelta(days=1)

    keyboard = []
    for i, button in enumerate(week_ranges):
        keyboard.append([InlineKeyboardButton(button, callback_data=i)])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text('Elija fecha:', reply_markup=reply_markup)


async def select_date_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("SELECT_DATE_BUTTON - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))

    query = update.callback_query
    await query.answer()

    if query.data == "0":
        msg = "Semana actual"
    elif query.data == "1":
        msg = "Semana próxima"
    elif query.data == "2":
        msg = "Dentro de 2 semanas"
    elif query.data == "3":
        msg = "Dentro de 3 semanas" 

    await query.edit_message_text(text="Opción seleccionada: {0}".format(msg))

    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("UPDATE Main SET WeekDelta = {0} WHERE UserId = {1} LIMIT 1".format(query.data, user.id)) 
    connection.commit()
    connection.close()


async def show_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("SHOW_DATE - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))
    
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT WeekDelta FROM Main WHERE UserId = {0}".format(user.id))
    date = cursor.fetchall()[0][0]
    connection.close()

    if str(date):
        if date == 0:
            msg = "Semana actual"
        elif date == 1:
            msg = "Semana próxima"
        elif date == 2:
            msg = "Dentro de 2 semanas"
        elif date == 3:
            msg = "Dentro de 3 semanas" 

        await update.message.reply_html("Semana configurada: <b>{0}</b>".format(msg))
    else:
        await update.message.reply_text("No hay semana configurada")


async def delete_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("DELETE_DATE - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))
    
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT WeekDelta FROM Main WHERE UserId = {0}".format(user.id))
    date = cursor.fetchall()[0][0]
    if str(date):
        cursor.execute("UPDATE Main SET WeekDelta = null WHERE UserId = '{0}'".format(user.id))
        await update.message.reply_text("Semana eliminada")
    else:
        await update.message.reply_text("Semana no encontrada")
    connection.commit()
    connection.close()


async def select_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("SELECT_COLOR - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))
    
    colors = ["Sin Color", "Amarillo", "Verde", "Azul", "Rosa", "Naranja", "Violeta"]

    keyboard = []
    for i, button in enumerate(colors):
        keyboard.append([InlineKeyboardButton(button, callback_data=i)])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text('Elija fecha:', reply_markup=reply_markup)

async def select_color_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=f"Selected option: {query.data}")
    # TODO

async def admin_broadcast_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.message.text.removeprefix("/admin_broadcast_msg ").removeprefix("@jwlibrary_plus_dev_bot").removeprefix("@jwlibrary_plus_bot")
    logger.info("ADMIN_BROADCAST_MSG - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Message: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, msg))
    
    if(user.id in [5978895313, 835003]): # Admin IDs
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT UserId FROM Main".format(user.id))
        data = cursor.fetchall()
        for user in data:
            await context.bot.send_message(chat_id=user[0], text=msg)

async def default_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("DEFAULT_MESSAGE - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))

    await update.message.reply_text("Este bot solo funciona a través de comandos. Por ejemplo, para introducir la pregunta 1, mande un mensaje con /q1 [PREGUNTA], sin los corchetes, e incluya su propia pregunta")

async def default_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("DEFAULT_COMMAND - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))

    await update.message.reply_text("Ha introducido un comando erróneo. Revise por favor la lista de comandos admitidos enviando el mensaje /start o haga click en el botón azul a la izquierda del cuadro de texto llamado 'Menú'")

async def language_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("LANGUAGE_SELECT - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))

    # TODO: Add language selection
    

async def w_prepare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("W_PREPARE - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))

    await update.message.reply_text("Inicializando. Por favor, espere")
    
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT Url FROM Main WHERE UserId = {0} LIMIT 1".format(user.id))
    url = cursor.fetchall()[0][0]
    cursor.execute("SELECT WeekDelta FROM Main WHERE UserId = {0} LIMIT 1".format(user.id))
    date = cursor.fetchall()[0][0]
    cursor.execute("SELECT Q1, Q2, Q3, Q4, Q5, Q6, Q7, Q8, Q9, Q10 FROM Main WHERE UserId = {0} LIMIT 1".format(user.id))
    qs = cursor.fetchall()[0]
    cursor.execute("SELECT LastRun FROM Main WHERE UserId = {0} LIMIT 1".format(user.id))
    lastRun = cursor.fetchall()[0][0]
    cursor.execute("SELECT LangSelected FROM Main WHERE UserId = {0} LIMIT 1".format(user.id))
    langSelected = cursor.fetchall()[0][0]

    now = datetime.now(pytz.timezone('Europe/Madrid')) # TODO: Check if UTC better
    now_iso = now.isoformat("T", "seconds")
    
    if lastRun is not None:
        if str(datetime.fromisoformat(lastRun).date()) == str(now.date()) and (user.id not in [5978895313, 835003]): # My test accounts
            await update.message.reply_text("Ya se ha preparado la reunión hoy. Por favor, vuelva a intentarlo mañana. El servicio tiene un coste. Si cree que hay un error, contacte con @geiserdrums")
            return
        else:
            cursor.execute("UPDATE Main SET LastRun = '{0}' WHERE UserId = '{1}'".format(now_iso, user.id))
    else:
        cursor.execute("UPDATE Main SET LastRun = '{0}' WHERE UserId = '{1}'".format(now_iso, user.id))
    connection.commit()
    connection.close()

    logger.info("BEGIN W_PREPARE - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - URL: {5} - WeekDelta: {6} - Questions: {7} - LastRun: {8}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, url, date, qs, lastRun))

    if any(qs):
        if (url is not None) and (date is not None):
            await update.message.reply_text("Tiene guardados una fecha y una URL. Se está tomando la fecha como valor predeterminado. Si quiere usar la URL, borre la fecha con /date_delete")
        if date is not None:
            start_date = now - timedelta(days=now.weekday()) + timedelta(int(date)*7)
            dates = []
            for i in range(5):
                dates.append((start_date - timedelta(7*i)).strftime("%Y-%m-%d"))

            jsonurl = requests.get("https://app.jw-cdn.org/catalogs/publications/v4/manifest.json") # TODO: If not updated in a month, update.
            manifest_id = jsonurl.json()['current']
            catalog = requests.get("https://app.jw-cdn.org/catalogs/publications/v4/" + manifest_id + "/catalog.db.gz")
            open('catalog.db.gz', 'wb').write(catalog.content)
            with gzip.open("catalog.db.gz", "rb") as f:
                with open('dbs/catalog.db', 'wb') as f_out:
                    shutil.copyfileobj(f, f_out)
            os.remove("catalog.db.gz")
            connection = sqlite3.connect("dbs/catalog.db")
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM DatedText WHERE Class = 68 AND (Start = '{0}' OR Start = '{1}' OR Start = '{2}' OR Start = '{3}' OR Start = '{4}')".format(dates[0], dates[1], dates[2], dates[3], dates[4]))
            dates_catalog = cursor.fetchall()

            list_of_dates = [datetime.strptime(x[1],"%Y-%m-%d") for x in dates_catalog] 
            date_count = Counter(list_of_dates)
            selected_dates = [date for date in list_of_dates if date_count[date] > 100] # There are some PublicationIds with the Start date wrong, so only select the ones that appear more than 100 times
            
            newest_date = max(selected_dates).strftime("%Y-%m-%d")
            delta_start_week_found = dates.index(newest_date)
            possiblePubId = [str(x[3]) for x in dates_catalog if x[1] == newest_date]

            cursor.execute("SELECT PublicationRootKeyId, IssueTagNumber, Symbol, Title, IssueTitle, Year, Id FROM Publication WHERE MepsLanguageId = 1 AND Id IN ({0})".format(', '.join(possiblePubId)))
            publication = cursor.fetchall()
            cursor.close() # No need to commit anything

            lang = "S" # TODO: Get language list
            year = publication[0][5]
            symbol = publication[0][2]
            month = str(publication[0][1])[4:6]
            magazine = requests.get("https://www.jw.org/finder?wtlocale={0}&issue={1}-{2}&pub={3}".format(lang, year, month, symbol)).text
            soup = BeautifulSoup(magazine, features="html.parser")
            div_study_articles = soup.find_all("div", {"class":"docClass-40"})

            url = "https://www.jw.org" + div_study_articles[delta_start_week_found].find("a").get("href")
            
            context.args = []
            context.args.append(url)
            await select_url(update, context)

        if (url is not None) or (date is not None):
            await update.message.reply_text("Comenzando peticiones a ChatGPT. Podría tardar incluso más de 10 minutos dependiendo del número de preguntas que haya configurado y su velocidad de respuesta")
            filenamejw, filenamedoc, filenamepdf = core_worker.main(url, user.id, qs)
            if(os.path.isfile('userBackups/{0}.jwlibrary'.format(user.id))):
                await update.message.reply_text("Aquí tiene su fichero, impórtelo a JW Library. Recuerde hacer una <b>copia de seguridad</b> para no perder los datos, ya que no ha proporcionado su archivo .jwlibrary")
            else:
                await update.message.reply_text("Aquí tiene su fichero, impórtelo a JW Library. Al haber proporcionado su copia de seguridad, puede estar seguro de que no perderá datos aun si se corrompiera su app, ya que dispone de cómo restaurarla")
            await update.message.reply_document(document=open(filenamejw, "rb"))
            os.remove(filenamejw)

            await update.message.reply_text("Aquí también encontrará los archivos en formato Word y PDF")
            await update.message.reply_document(document=open(filenamedoc, "rb"))
            await update.message.reply_document(document=open(filenamepdf, "rb"))
            os.remove(filenamedoc)
            os.remove(filenamepdf)

        else:
            await update.message.reply_text("No ha seleccionado ninguna fecha o URL")
    else:
        await update.message.reply_text("Todas las preguntas están vacías")


def main() -> None:

    application = Application.builder().token(os.environ["TOKEN"]).concurrent_updates(True).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("q_show", show_q))
    application.add_handler(CommandHandler("q_delete", delete_q))
    application.add_handler(CommandHandler("q_bulk", bulk_q))
    application.add_handler(CommandHandler("backup_send", send_backup))
    application.add_handler(MessageHandler(filters.Document.ALL, downloader))
    application.add_handler(CommandHandler("backup_describe", describe_backup))
    application.add_handler(CommandHandler("backup_delete", delete_backup))
    application.add_handler(CommandHandler("url_select", select_url, block = False))
    application.add_handler(CommandHandler("url_show", show_url))
    application.add_handler(CommandHandler("url_delete", delete_url))
    application.add_handler(CommandHandler("date_select", select_date))
    application.add_handler(CallbackQueryHandler(select_date_button)) #pattern="select_date"
    application.add_handler(CommandHandler("date_show", show_date))
    application.add_handler(CommandHandler("date_delete", delete_date))
    # application.add_handler(CommandHandler("color_select", select_color)) # TODO - not working
    # application.add_handler(CallbackQueryHandler(select_color_button))
    application.add_handler(CommandHandler("language_select", language_select))
    application.add_handler(CommandHandler("w_prepare", w_prepare, block = False))

    application.add_handler(CommandHandler("q1", q1))
    application.add_handler(CommandHandler("q2", q2))
    application.add_handler(CommandHandler("q3", q3))
    application.add_handler(CommandHandler("q4", q4))
    application.add_handler(CommandHandler("q5", q5))
    application.add_handler(CommandHandler("q6", q6))
    application.add_handler(CommandHandler("q7", q7))
    application.add_handler(CommandHandler("q8", q8))
    application.add_handler(CommandHandler("q9", q9))
    application.add_handler(CommandHandler("q10", q10))

    application.add_handler(CommandHandler("admin_broadcast_msg", admin_broadcast_msg))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, default_message))
    application.add_handler(MessageHandler(filters.COMMAND, default_command))

    application.run_polling()

if __name__ == "__main__":
    main()