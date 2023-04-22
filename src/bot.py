import logging
import os
import sqlite3
import validators
from urllib.parse import urlparse
import sys
import core_worker
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

init_questions=["Una ilustración o ejemplo para explicar algún punto principal del párrafo",
                "Una experiencia en concreto, aportando referencias exactas, que esté muy relacionada con el párrafo",
                "¿Qué me enseña este párrafo sobre Jehová?",
                "Una explicación sobre uno de los textos que aparezcan, que aplique al párrafo. Usa la Biblia de Estudio de los Testigos de Jehová.",
                "¿Cómo poner en práctica el contenido del párrafo?",
                "Algún comentario adicional que no responda la pregunta principal y que sea de utilidad"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("START - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))

    await update.message.reply_html(rf"""Bienvenido! 

Este bot le ayudará a prepararse las reuniones usando técnicas avanzadas de Inteligencia Artificial, aplicadas especialmente a la relación de datos en la literatura de la organización.

<u>El funcionamiento es el siguiente</u>:
  1. Introduzca la URL de jw.org de la Atalaya que quiera preparar con el comando /url [URL]
  2. Introduzca las preguntas que quiera hacer. Defina las preguntas y se aplicarán a <b>todos</b> los párrafos, con un máximo de 10. 
Por defecto, hay 6 preguntas incluidas. Se usa con /q1 [PREGUNTA_1], /q2 [PREGUNTA_2].... Para consultar las preguntas configuradas, usa /showq
  3. Una vez haya elegido sus parámetros, ejecute /begin y espere unos minutos a que se genere el archivo <code>.jwlibrary</code>
  4. Descárguelo y restaure esta copia en su app JW Library (Borrará los datos, si no quiere que eso suceda, use una app como Merge JWL)

Repositorio oficial: https://github.com/DrumSergio/jwlibrary-plus
Descargo de Responsabilidad: El software aquí presente se ofrece tal cual, sin ninguna garantía.""",
        reply_markup=ForceReply(selective=True),)
    
    user_id = update.effective_user.id
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("INSERT OR IGNORE INTO Main (UserId) VALUES ({0})".format(user_id))
    cursor.execute("UPDATE Main SET q1 = '{0}', q2 = '{1}', q3 = '{2}', q4 = '{3}', q5 = '{4}', q6 = '{5}' WHERE UserId = {6}".format(init_questions[0], init_questions[1], init_questions[2], init_questions[3], init_questions[4], init_questions[5], user_id))
    connection.commit()
    connection.close()


async def url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Testeando URL, espere por favor.")
    url = context.args[0]
    user = update.effective_user
    logger.info("URL - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - URL: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, url))
    if(validators.url(url)):
        u = urlparse(url)
        if(u.netloc == "www.jw.org"):
            user_id = update.effective_user.id
            connection = sqlite3.connect("dbs/main.db")
            cursor = connection.cursor()
            cursor.execute("UPDATE Main SET Url = '{0}' WHERE UserId = {1}".format(url, user_id))
            connection.commit()
            connection.close()
            title, articleId, articleN = core_worker.extract_html(url,get_all=False)
            await update.message.reply_html("URL guardada.\nEn esta URL se encuentra la revista del año <b>{0}</b>, número <b>{1}</b>, {2}. El título de la Atalaya es <b>{3}</b>.".format(articleId[:4], articleId[4:-2], articleN.lower(), title))
        else:
            await update.message.reply_text("No es un una URL de www.jw.org")
    else:
        await update.message.reply_text("No es un una URL válida.")

async def q1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q1 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 150):
        user_id = update.effective_user.id
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(sys._getframe().f_code.co_name, question, user_id))
        connection.commit()
        connection.close()
    else:
        await update.message.reply_text("La pregunta debe tener menos de 150 caracteres.")

async def q2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q2 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 150):
        user_id = update.effective_user.id
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(sys._getframe().f_code.co_name, question, user_id))
        connection.commit()
        connection.close()
    else:
        await update.message.reply_text("La pregunta debe tener menos de 150 caracteres.")
        
async def q3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q3 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 150):
        user_id = update.effective_user.id
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(sys._getframe().f_code.co_name, question, user_id))
        connection.commit()
        connection.close()
    else:
        await update.message.reply_text("La pregunta debe tener menos de 150 caracteres.")
        
async def q4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q4 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 150):
        user_id = update.effective_user.id
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(sys._getframe().f_code.co_name, question, user_id))
        connection.commit()
        connection.close()
    else:
        await update.message.reply_text("La pregunta debe tener menos de 150 caracteres.")
        
async def q5(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q5 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 150):
        user_id = update.effective_user.id
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(sys._getframe().f_code.co_name, question, user_id))
        connection.commit()
        connection.close()
    else:
        await update.message.reply_text("La pregunta debe tener menos de 150 caracteres.")
        
async def q6(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q6 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 150):
        user_id = update.effective_user.id
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(sys._getframe().f_code.co_name, question, user_id))
        connection.commit()
        connection.close()
    else:
        await update.message.reply_text("La pregunta debe tener menos de 150 caracteres.")
        
async def q7(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q7 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 150):
        user_id = update.effective_user.id
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(sys._getframe().f_code.co_name, question, user_id))
        connection.commit()
        connection.close()
    else:
        await update.message.reply_text("La pregunta debe tener menos de 150 caracteres.")
        
async def q8(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q8 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 150):
        user_id = update.effective_user.id
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(sys._getframe().f_code.co_name, question, user_id))
        connection.commit()
        connection.close()
    else:
        await update.message.reply_text("La pregunta debe tener menos de 150 caracteres.")
        
async def q9(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q9 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 150):
        user_id = update.effective_user.id
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(sys._getframe().f_code.co_name, question, user_id))
        connection.commit()
        connection.close()
    else:
        await update.message.reply_text("La pregunta debe tener menos de 150 caracteres.")

async def q10(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = ' '.join(context.args[:])
    user = update.effective_user
    logger.info("Q10 - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4} - Question: {5}".format(user.id, user.first_name, user.last_name, user.username, user.language_code, question))
    if(len(question) < 150):
        user_id = update.effective_user.id
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("UPDATE Main SET {0} = '{1}' WHERE UserId = {2}".format(sys._getframe().f_code.co_name, question, user_id))
        connection.commit()
        connection.close()
    else:
        await update.message.reply_text("La pregunta debe tener menos de 150 caracteres.")

async def showq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("SHOWQ - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))
    
    user_id = update.effective_user.id
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 FROM Main WHERE UserId = {0} LIMIT 1".format(user_id))
    data = cursor.fetchall()[0]
    connection.close()
    await update.message.reply_text("""Tus preguntas actuales:
1. {0}
2. {1}
3. {2}
4. {3}
5. {4}
6. {5}
7. {6}
8. {7}
9. {8}
10. {9}""". format(data[0],data[1],data[2],data[3],data[4],data[5],data[6],data[7],data[8],data[9]))

async def begin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info("BEGIN - User ID: {0} - First Name: {1} - Last Name: {2} - Username: {3} - Language Code: {4}".format(user.id, user.first_name, user.last_name, user.username, user.language_code))
 
    await update.message.reply_text("Comenzando. Podría tardar incluso más de 10 minutos dependiendo del número de preguntas y de la velocidad de respuesta de ChatGPT.")
    user_id = update.effective_user.id
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Main WHERE UserId = {0} LIMIT 1".format(user_id))
    data = cursor.fetchall()[0]
    connection.close()

    url = data[1]
    qs = data[2:]

    if bool(url) & any(qs): # If URL is in place and there is any question set
        filename = core_worker.main(url, update.effective_user.id, qs)
        await update.message.reply_text("Aquí tiene su fichero, impórtelo a JW Library.")
        await update.message.reply_document(document=open(filename, "rb"))
        os.remove(filename)
    else:
        await update.message.reply_text("No ha introducido la URL o todas las preguntas están vacías.")

def main() -> None:

    application = Application.builder().token(os.environ["TOKEN"]).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("url", url))
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
    application.add_handler(CommandHandler("showq", showq))
    application.add_handler(CommandHandler("begin", begin))

    application.run_polling()

if __name__ == "__main__":
    main()