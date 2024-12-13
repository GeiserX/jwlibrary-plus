import logging
import gettext
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
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
    CallbackQueryHandler, ConversationHandler
)
from telegram.error import Forbidden

# Define conversation states
(
    LANG_SELECT,
    RECEIVE_BACKUP_FILE,
    RECEIVE_DATE_OR_URL_CHOICE,
    RECEIVE_URL,
    RECEIVE_DATE_SELECTION,
    CUSTOMIZE_QUESTIONS_YES_NO,
    RECEIVE_QUESTION_NUMBER,
    RECEIVE_QUESTION_TEXT,
    ASK_FOR_MORE_QUESTIONS,
    W_PREPARE,
    AFTER_PREPARATION
) = range(11)

logger = logging.getLogger('mylogger')
logger.setLevel(logging.INFO)
logFormatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

init_questions = [
    "Una ilustración o ejemplo para explicar algún punto principal del párrafo",
    "Una experiencia en concreto, aportando referencias exactas de jw.org, que esté muy relacionada con el párrafo",
    "Una explicación sobre uno de los textos que aparezcan, que aplique al párrafo. Usa la Biblia de Estudio de los Testigos de Jehová"
]

def get_translation_function(context):
    lang_code = context.user_data.get('language', 'es')  # Default to 'es' if not set
    domain = "jwlibraryplus"
    locale_dir = "../locales"
    translation = gettext.translation(domain, localedir=locale_dir, languages=[lang_code], fallback=True)
    return translation.gettext

async def check_if_user_exists(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM Main WHERE UserId = ?", (user.id,))
    count = cursor.fetchone()[0]
    if count == 0:
        # Insert new user
        cursor.execute(
            "INSERT INTO Main (UserId, UserName, FirstName, LastName, LangCodeTelegram, IsBot) VALUES (?, ?, ?, ?, ?, ?)",
            (user.id, user.username, user.first_name, user.last_name, user.language_code, user.is_bot)
        )
    else:
        # Update existing user
        cursor.execute(
            "UPDATE Main SET UserName = ?, FirstName = ?, LastName = ?, LangCodeTelegram = ?, IsBot = ? WHERE UserId = ?",
            (user.username, user.first_name, user.last_name, user.language_code, user.is_bot, user.id)
        )
    connection.commit()
    connection.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info("START - User ID: {0} - Username: {1}".format(user.id, user.username))
    await check_if_user_exists(update, context)
    
    # Check if LangSelected is set
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT LangSelected FROM Main WHERE UserId = ?", (user.id,))
    result = cursor.fetchone()
    connection.close()
    
    if result and result[0]:
        # User has selected language previously
        # Set the user's selected language in context
        context.user_data['language'] = result[0]
        # Proceed to next step
        return await ask_backup(update, context)
    else:
        # Ask user to select language
        return await language_select(update, context)

async def language_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info("LANGUAGE_SELECT - User ID: {0}".format(user.id))
    
    languages = [("English", "en"), ("Español", "es"), ("Italiano", "it"), ("Français", "fr"), ("Português", "pt"), ("Deutsch", "de"), ("Български", "bg")]
    
    keyboard = []
    for name, code in languages:
        keyboard.append([InlineKeyboardButton(name, callback_data=code)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text('Please select your language / Por favor selecciona tu idioma', reply_markup=reply_markup)
    return LANG_SELECT

async def language_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    lang_code = query.data
    logger.info("LANGUAGE_SELECTED - User ID: {0} - Language Code: {1}".format(user.id, lang_code))
    
    context.user_data['language'] = lang_code
    
    # Save to database
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("UPDATE Main SET LangSelected = ? WHERE UserId = ?", (lang_code, user.id))
    connection.commit()
    connection.close()
    
    # Acknowledge the selection
    await query.edit_message_text("Language selected: {0}".format(lang_code))
    
    # Proceed to next step: ask_backup
    return await ask_backup(update, context)

async def ask_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = get_translation_function(context)
    await update.message.reply_text(_("¿Deseas proporcionar tu archivo de respaldo .jwlibrary? Por favor envíalo ahora. Si prefieres no hacerlo, escribe 'no' u 'omitir'."))
    return RECEIVE_BACKUP_FILE

async def receive_backup_file_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    _ = get_translation_function(context)
    file = await context.bot.get_file(update.message.document)
    logger.info("RECEIVE_BACKUP_FILE_DOCUMENT - User ID: {0} - File ID: {1} - File Path: {2}".format(user.id, file.file_id, file.file_path))
    
    if(file.file_path.endswith(".jwlibrary")):
        # Save the file
        await file.download_to_drive('userBackups/{0}.jwlibrary'.format(user.id))
        # Run describe_jwlibrary and post output
        notesN, inputN, tagMaptN, tagN, bookmarkN, lastModified, userMarkN = core_worker.describe_jwlibrary(user.id)
        await update.message.reply_html(_("""Estado de tu archivo <code>.jwlibrary</code>:
<u>Notas:</u> {0}
<u>Tags individuales:</u> {1}
<u>Notas con tags:</u> {2}
<u>Escritos en cuadros de texto:</u> {3}
<u>Favoritos:</u> {4}
<u>Frases subrayadas:</u> {5}
<u>Última vez modificado:</u> {6}""").format(notesN, tagN, tagMaptN, inputN, bookmarkN, userMarkN, lastModified))
    else:
        await update.message.reply_text(_("Formato de archivo erróneo."))
    # Proceed to next step
    return await ask_date_or_url(update, context)

async def receive_backup_file_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.lower()
    logger.info("RECEIVE_BACKUP_FILE_TEXT - User ID: {0} - Input: {1}".format(update.effective_user.id, user_input))
    _ = get_translation_function(context)
    if user_input in ['no', 'omit', 'omitir']:
        # User chooses not to provide backup
        await update.message.reply_text(_("De acuerdo, continuamos sin el archivo de respaldo."))
    else:
        await update.message.reply_text(_("Por favor, envía tu archivo de respaldo .jwlibrary, o escribe 'no' u 'omitir' para continuar sin él."))
        # Stay in the same state
        return RECEIVE_BACKUP_FILE
    # Proceed to next step
    return await ask_date_or_url(update, context)

async def ask_date_or_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = get_translation_function(context)
    keyboard = [
        [InlineKeyboardButton(_("Seleccionar fecha"), callback_data='date')],
        [InlineKeyboardButton(_("Proporcionar URL"), callback_data='url')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(_("¿Deseas seleccionar una fecha o proporcionar una URL específica?"), reply_markup=reply_markup)
    return RECEIVE_DATE_OR_URL_CHOICE

async def receive_date_or_url_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    logger.info("RECEIVE_DATE_OR_URL_CHOICE - User ID: {0} - Choice: {1}".format(update.effective_user.id, user_choice))
    _ = get_translation_function(context)
    if user_choice == 'date':
        # Proceed to select date
        return await select_date(update, context)
    elif user_choice == 'url':
        await query.edit_message_text(_("Por favor, envía la URL del artículo de La Atalaya que deseas preparar."))
        return RECEIVE_URL

async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = get_translation_function(context)
    user = update.effective_user
    now = datetime.now(pytz.timezone('Europe/Madrid'))
    start = now - timedelta(days=now.weekday())
    week_ranges = []

    for week in range(4):
        end = start + timedelta(days=6)
        if start.month == end.month:
            week_ranges.append(f"{start.strftime('%-d')}-{end.strftime('%-d de %B')}")
        else:
            week_ranges.append(f"{start.strftime('%-d de %B')}-{end.strftime('%-d de %B').strip()}")
        start = end + timedelta(days=1)

    keyboard = []
    for i, button in enumerate(week_ranges):
        keyboard.append([InlineKeyboardButton(button, callback_data=str(i))])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(_('Por favor, elige una fecha:'), reply_markup=reply_markup)
    return RECEIVE_DATE_SELECTION

async def receive_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date_selection = int(query.data)
    logger.info("RECEIVE_DATE_SELECTION - User ID: {0} - Selection: {1}".format(update.effective_user.id, date_selection))
    _ = get_translation_function(context)
    # Save date selection in context
    context.user_data['date_selection'] = date_selection
    # Save to database
    user = update.effective_user
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("UPDATE Main SET WeekDelta = ? WHERE UserId = ?", (date_selection, user.id))
    connection.commit()
    connection.close()
    await query.edit_message_text(_("Fecha seleccionada."))
    # Proceed to next step
    return await show_questions(update, context)

async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = update.message.text.strip()
    logger.info("RECEIVE_URL - User ID: {0} - URL: {1}".format(update.effective_user.id, url))
    _ = get_translation_function(context)
    if(validators.url(url)):
        u = urlparse(url)
        if(u.netloc == "www.jw.org"):
            # Save URL in database
            user = update.effective_user
            connection = sqlite3.connect("dbs/main.db")
            cursor = connection.cursor()
            cursor.execute("UPDATE Main SET Url = ? WHERE UserId = ?", (url, user.id))
            connection.commit()
            connection.close()
            await update.message.reply_text(_("URL guardada."))
            # Proceed to next step
            return await show_questions(update, context)
        else:
            await update.message.reply_text(_("La URL no es un enlace válido de www.jw.org. Por favor, envía una URL válida."))
            return RECEIVE_URL
    else:
        await update.message.reply_text(_("Esta no es una URL válida. Por favor, envía una URL válida."))
        return RECEIVE_URL

async def show_questions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = get_translation_function(context)
    # Display current questions (q_show)
    user = update.effective_user
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,Q9,Q10 FROM Main WHERE UserId = ?", (user.id,))
    data = cursor.fetchone()
    connection.close()

    num_questions = 10
    questions_text = _("<u>Tus preguntas actuales:</u>\n")
    for i in range(num_questions):
        if data[i]:
            questions_text += "{0}. {1}\n".format(i+1, data[i])

    await update.message.reply_html(questions_text)
    # Ask if user wants to customize the questions
    keyboard = [
        [InlineKeyboardButton(_("Sí"), callback_data='yes')],
        [InlineKeyboardButton(_("No"), callback_data='no')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(_("¿Deseas personalizar las preguntas o estás de acuerdo con las predeterminadas?"), reply_markup=reply_markup)
    return CUSTOMIZE_QUESTIONS_YES_NO

async def customize_questions_yes_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    logger.info("CUSTOMIZE_QUESTIONS_YES_NO - User ID: {0} - Choice: {1}".format(update.effective_user.id, user_choice))
    _ = get_translation_function(context)
    if user_choice == 'yes':
        # Proceed to ask for question to edit
        return await ask_for_question_edit(update, context)
    else:
        # Proceed to preparation
        return await w_prepare(update, context)

async def ask_for_question_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = get_translation_function(context)
    # Display options to select question to edit
    keyboard = []
    for i in range(1, 11):
        keyboard.append([InlineKeyboardButton(f"Q{i}", callback_data=str(i))])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(_("Por favor, selecciona el número de la pregunta que deseas editar:"), reply_markup=reply_markup)
    return RECEIVE_QUESTION_NUMBER

async def receive_question_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    question_number = int(query.data)
    logger.info("RECEIVE_QUESTION_NUMBER - User ID: {0} - Question Number: {1}".format(update.effective_user.id, question_number))
    _ = get_translation_function(context)
    # Save question number in context
    context.user_data['question_number'] = question_number
    await query.edit_message_text(_("Por favor, ingresa el texto para la pregunta {0}:").format(question_number))
    return RECEIVE_QUESTION_TEXT

async def receive_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    question_text = update.message.text.strip()
    user = update.effective_user
    question_number = context.user_data['question_number']
    logger.info("RECEIVE_QUESTION_TEXT - User ID: {0} - Question Number: {1} - Text: {2}".format(user.id, question_number, question_text))
    _ = get_translation_function(context)
    # Save the question to the database
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("UPDATE Main SET Q{0} = ? WHERE UserId = ?".format(question_number), (question_text, user.id))
    connection.commit()
    connection.close()
    await update.message.reply_text(_("Pregunta {0} guardada correctamente.").format(question_number))
    # Ask if user wants to edit another question
    keyboard = [
        [InlineKeyboardButton(_("Sí"), callback_data='yes')],
        [InlineKeyboardButton(_("No"), callback_data='no')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(_("¿Deseas editar otra pregunta?"), reply_markup=reply_markup)
    return ASK_FOR_MORE_QUESTIONS

async def ask_for_more_questions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    logger.info("ASK_FOR_MORE_QUESTIONS - User ID: {0} - Choice: {1}".format(update.effective_user.id, user_choice))
    _ = get_translation_function(context)
    if user_choice == 'yes':
        # Proceed to ask for another question to edit
        return await ask_for_question_edit(update, context)
    else:
        # Proceed to preparation
        return await w_prepare(update, context)

async def w_prepare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    _ = get_translation_function(context)
    await update.message.reply_text(_("Comenzando la preparación. Por favor, espera..."))
    await update.message.reply_chat_action(action=telegram.constants.ChatAction.TYPING)
    # Call core_worker.main with appropriate parameters
    # Extract data from context.user_data and possibly from database
    # For example, get qs (questions), date/url, etc.
    # Then, proceed as in your original w_prepare function

    # Fetch necessary data from the database
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT Url FROM Main WHERE UserId = ?", (user.id,))
    url_result = cursor.fetchone()
    cursor.execute("SELECT WeekDelta FROM Main WHERE UserId = ?", (user.id,))
    date_result = cursor.fetchone()
    cursor.execute("SELECT Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,Q9,Q10 FROM Main WHERE UserId = ?", (user.id,))
    qs = cursor.fetchone()
    cursor.execute("SELECT LastRun FROM Main WHERE UserId = ?", (user.id,))
    lastRun_result = cursor.fetchone()
    cursor.execute("SELECT LangSelected FROM Main WHERE UserId = ?", (user.id,))
    langSelected_result = cursor.fetchone()
    connection.close()

    url = url_result[0] if url_result else None
    date = date_result[0] if date_result else None
    lastRun = lastRun_result[0] if lastRun_result else None
    langSelected = langSelected_result[0] if langSelected_result else None

    now = datetime.now(pytz.timezone('Europe/Madrid'))  # Adjust timezone as needed
    now_iso = now.isoformat("T", "seconds")
    now_utc = now.astimezone(pytz.UTC)
    now_utc_iso = now_utc.isoformat("T", "seconds").replace('+00:00', 'Z')

    # Update LastRun in the database
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("UPDATE Main SET LastRun = ? WHERE UserId = ?", (now_iso, user.id))
    connection.commit()
    connection.close()

    logger.info("BEGIN W_PREPARE - User ID: {0} - URL: {1} - WeekDelta: {2} - Questions: {3} - LastRun: {4}".format(user.id, url, date, qs, lastRun))

    if any(qs):
        if (url is not None) and (date is not None):
            await update.message.reply_text(_("Tienes guardados una fecha y una URL. Se está tomando la fecha como valor predeterminado. Si quieres usar la URL, borra la fecha con /date_delete"))
        if date is not None and (url is None):
            # Logic to fetch URL based on date
            # Similar to your original w_prepare function
            await update.message.reply_text(_("Obteniendo el URL basado en la fecha seleccionada. Por favor, espera..."))
            # Implement the logic to get the URL from the date
            # Save the URL in the database and set url variable
            # For this example, we assume url is obtained and set
            # url = ...

        if (url is not None) or (date is not None):
            await update.message.reply_text(_("Comenzando peticiones a ChatGPT. Podría tardar incluso más de 10 minutos dependiendo del número de preguntas que hayas configurado."))
            filenamejw, filenamedoc, filenamepdf = core_worker.main(url, user.id, qs)
            if(os.path.isfile('userBackups/{0}.jwlibrary'.format(user.id))):
                await update.message.reply_text(_("Aquí tienes tu fichero, impórtalo en JW Library. Recuerda hacer una copia de seguridad para no perder los datos, ya que proporcionaste tu archivo .jwlibrary"))
            else:
                await update.message.reply_text(_("Aquí tienes tu fichero, impórtalo en JW Library. Al no haber proporcionado tu copia de seguridad, hazlo con precaución."))
            await update.message.reply_document(document=open(filenamejw, "rb"))
            os.remove(filenamejw)

            await update.message.reply_text(_("Aquí también encontrarás los archivos en formato Word y PDF"))
            await update.message.reply_document(document=open(filenamedoc, "rb"))
            await update.message.reply_document(document=open(filenamepdf, "rb"))
            os.remove(filenamedoc)
            os.remove(filenamepdf)
        else:
            await update.message.reply_text(_("No has seleccionado ninguna fecha o URL"))
    else:
        await update.message.reply_text(_("Todas las preguntas están vacías"))

    # After preparation, ask the user if they want to prepare another article
    keyboard = [
        [InlineKeyboardButton(_("Sí"), callback_data='yes')],
        [InlineKeyboardButton(_("No"), callback_data='no')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(_("¿Deseas preparar con otras preguntas u otro artículo de La Atalaya?\nNota: Las preguntas ahora se eliminan."), reply_markup=reply_markup)
    return AFTER_PREPARATION

async def after_preparation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    user = update.effective_user
    logger.info("AFTER_PREPARATION - User ID: {0} - Choice: {1}".format(user.id, user_choice))
    _ = get_translation_function(context)
    # Delete questions in database
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE Main SET Q1 = null, Q2 = null, Q3 = null, Q4 = null, Q5 = null, Q6 = null, Q7 = null, Q8 = null, Q9 = null, Q10 = null WHERE UserId = ?",
        (user.id,)
    )
    connection.commit()
    connection.close()
    if user_choice == 'yes':
        # Restart the process from ask_backup
        await query.edit_message_text(_("Comenzando de nuevo..."))
        return await ask_backup(update, context)
    else:
        await query.edit_message_text(_("Las preguntas ahora están eliminadas. Para ejecutar el bot nuevamente, por favor escribe /start"))
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info("User %s canceled the conversation.", user.first_name)
    _ = get_translation_function(context)
    await update.message.reply_text(_("Operación cancelada."))
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token(os.environ["TOKEN"]).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LANG_SELECT: [
                CallbackQueryHandler(language_selected)
            ],
            RECEIVE_BACKUP_FILE: [
                MessageHandler(filters.Document.ALL, receive_backup_file_document),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_backup_file_text),
            ],
            RECEIVE_DATE_OR_URL_CHOICE: [
                CallbackQueryHandler(receive_date_or_url_choice)
            ],
            RECEIVE_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url)
            ],
            RECEIVE_DATE_SELECTION: [
                CallbackQueryHandler(receive_date_selection)
            ],
            CUSTOMIZE_QUESTIONS_YES_NO: [
                CallbackQueryHandler(customize_questions_yes_no)
            ],
            RECEIVE_QUESTION_NUMBER: [
                CallbackQueryHandler(receive_question_number)
            ],
            RECEIVE_QUESTION_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_question_text)
            ],
            ASK_FOR_MORE_QUESTIONS: [
                CallbackQueryHandler(ask_for_more_questions)
            ],
            AFTER_PREPARATION: [
                CallbackQueryHandler(after_preparation)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)

    # You can add other handlers here if needed
    # e.g., for /change_language command to allow users to change language later

    application.run_polling()

if __name__ == "__main__":
    main()