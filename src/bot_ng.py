import logging
import gettext
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import requests
import gzip
import shutil
import pytz
import sqlite3
import validators
from urllib.parse import urlparse
import sys
import core_worker
from collections import Counter
from babel.dates import format_date
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
    CallbackQueryHandler, ConversationHandler
)
from telegram.error import Forbidden

# Define the global translation function
import gettext
_ = gettext.gettext  # Global definition

# Define conversation states
(
    LANG_SELECT,
    RECEIVE_BACKUP_FILE,
    RECEIVE_DATE_OR_URL_CHOICE,
    RECEIVE_URL,
    RECEIVE_DATE_SELECTION,
    CUSTOMIZE_QUESTIONS_YES_NO,
    CHOOSE_EDIT_OR_DELETE,
    RECEIVE_QUESTION_NUMBER,
    RECEIVE_QUESTION_TEXT,
    ASK_FOR_MORE_ACTIONS,
    W_PREPARE,
    AFTER_PREPARATION,
    RECEIVE_KEEP_QUESTIONS_RESPONSE
) = range(13)

logger = logging.getLogger('mylogger')
logger.setLevel(logging.INFO)
logFormatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

# Cache for translation objects
translations_cache = {}

def get_translation(context):
    lang_code = context.user_data.get('language', 'es')  # Default to 'es' if not set
    domain = 'jwlibraryplus'
    localedir = os.path.join(os.path.dirname(__file__), '../locales')

    if lang_code in translations_cache:
        return translations_cache[lang_code]

    try:
        translation = gettext.translation(domain=domain, localedir=localedir, languages=[lang_code])
        translations_cache[lang_code] = translation
    except FileNotFoundError:
        logger.error(f"Translation file not found for language '{lang_code}'. Falling back to default 'es'.")
        translation = gettext.translation(domain=domain, localedir=localedir, languages=['es'])
        translations_cache['es'] = translation

    return translation

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
    await check_if_user_exists(update, context)

    # Define welcome_message
    welcome_message = _("¡Bienvenido!\n\nEste bot le ayudará a mejorar y profundizar en la preparación de <b>La Atalaya</b> usando <b>Inteligencia Artificial</b>. El modelo está personalizado por mí en OpenAI para intentar apegarse lo más posible a la realidad, pero es imposible que todas las respuestas sean correctas y sin alucinaciones.\n\nEl bot funciona respondiendo a las preguntas que le dictes. Es decir: si en la pregunta 1 le solicitas que te explique algún punto del párrafo con una ilustración, lo que hará será contestar a la pregunta del/los párrafo(s) de La Atalaya e introducirla en el recuadro de texto habilitado para ello.\n\nMás adelante <b>se te sugerirá enviar tu archivo de respaldo de .jwlibrary para no perder ninguna información en tu dispositivo</b>. Esto es particularmente importante ya que al restaurar el archivo .jwlibrary que se genera, tus notas y marcas que tenías anteriormente en la aplicación se perderán. Recomendamos, además, que el artículo de estudio que quieras prepararte esté vacío en tu dispositivo para evitar incongruencias.\n\nEsta aplicación no es oficial ni está afiliada de ningún modo con JW.ORG.\n\nSi el bot tarda en responder, espera unos minutos y contacta con @geiserdrums. El bot sirve a cada usuario individualmente de manera secuencial, con lo que quizá lo esté usando otra persona en este mismo instante. Sé paciente.")

    logger.info("START - User ID: {0} - Username: {1}".format(user.id, user.username))
    # Reset the conversation_active flag
    context.user_data['conversation_active'] = True

    context.user_data['command'] = 'start'  # Indicate that the entry point is /start

    if user.is_bot:
        await update.message.reply_text(_("Los bots no están permitidos"))
        return ConversationHandler.END

    # Check LastRun timestamp unless user is admin
    if user.id not in [835003, 5978895313]:
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT LastRun, LangSelected FROM Main WHERE UserId = ?", (user.id,))
        result = cursor.fetchone()
        connection.close()

        if result:
            last_run_str = result[0]
            lang_selected = result[1]
        else:
            last_run_str = None
            lang_selected = None

        now = datetime.now(pytz.timezone('Europe/Madrid'))
        if last_run_str:
            last_run = datetime.fromisoformat(last_run_str)
            time_since_last_run = now - last_run
            if time_since_last_run < timedelta(hours=1):
                remaining_time = timedelta(hours=1) - time_since_last_run
                minutes = int(remaining_time.total_seconds() // 60)
                translation = get_translation(context)
                trans = translation.gettext
                await update.message.reply_text(
                    trans("Por favor, inténtelo de nuevo dentro de {} minutos. Así puedo controlar mejor los gastos, ya que es gratuito. Si tiene algún problema, contacte con @geiserdrums").format(minutes)
                )
                return ConversationHandler.END  # End the conversation

    else:
        # Admin user bypasses the last run check
        last_run_str = None
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT LangSelected FROM Main WHERE UserId = ?", (user.id,))
        result = cursor.fetchone()
        connection.close()
        lang_selected = result[0] if result else None

    # Set the user's selected language in context
    if lang_selected:
        context.user_data['language'] = lang_selected
        context.user_data['translation'] = get_translation(context)
    else:
        context.user_data['language'] = None

    if context.user_data['language']:
        # Language is already set; proceed
        translation = context.user_data['translation']
        trans = translation.gettext
    else:
        # Prompt user to select language
        return await language_select(update, context)

    # Ensure default questions are initialized if needed
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,Q9,Q10 FROM Main WHERE UserId = ?", (user.id,))
    data = cursor.fetchone()
    connection.close()
    if not any(data):
        # User has no questions, initialize them
        init_questions, translated_questions = get_default_questions(trans)
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE Main SET Q1 = ?, Q2 = ?, Q3 = ? WHERE UserId = ?",
            (*init_questions, user.id)
        )
        connection.commit()
        connection.close()

    # Send the welcome message
    await update.message.reply_text(trans(welcome_message), parse_mode=telegram.constants.ParseMode.HTML)
    return await ask_backup(update, context)

async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info("CHANGE_LANGUAGE - User ID: {0}".format(user.id))

    context.user_data['command'] = 'change_language'  # Indicate that the entry point is /change_language

    return await language_select(update, context)

async def language_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info("LANGUAGE_SELECT - User ID: {0}".format(user.id))

    languages = [
        ("English", "en"),
        ("Español", "es"),
        ("Italiano", "it"),
        ("Français", "fr"),
        ("Português (Portugal)", "pt-PT"),
        ("Português (Brasil)", "pt-BR"),
        ("Deutsch", "de"),
        ("Nederlands", "nl"),
        ("Български", "bg"),
        ("Македонски", "mk")
    ]
    keyboard = []
    for name, code in languages:
        keyboard.append([InlineKeyboardButton(name, callback_data='lang_' + code)])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text('Please select your language / Por favor selecciona tu idioma', reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text('Please select your language / Por favor selecciona tu idioma', reply_markup=reply_markup)
    return LANG_SELECT

async def language_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    lang_code = query.data.replace('lang_', '')
    logger.info("LANGUAGE_SELECTED - User ID: {0} - Language Code: {1}".format(user.id, lang_code))

    # Fetch previous LangSelected from the database
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT LangSelected FROM Main WHERE UserId = ?", (user.id,))
    old_lang_result = cursor.fetchone()
    old_lang_selected = old_lang_result[0] if old_lang_result else None

    # Update the LangSelected to the new language
    cursor.execute("UPDATE Main SET LangSelected = ? WHERE UserId = ?", (lang_code, user.id))
    connection.commit()
    connection.close()

    context.user_data['language'] = lang_code
    context.user_data['translation'] = get_translation(context)
    translation = context.user_data['translation']
    trans = translation.gettext

    if old_lang_selected and old_lang_selected != lang_code:
        # Languages are different, ask the user if they want to keep their old questions
        await query.edit_message_text(
            trans("Has cambiado el idioma de '{0}' a '{1}'. ¿Quieres conservar tus preguntas anteriores (en el antiguo idioma) o reiniciar a las preguntas predeterminadas en el nuevo idioma?").format(old_lang_selected, lang_code)
        )
        # Store the old language code in context
        context.user_data['previous_language'] = old_lang_selected
        # Present options: Keep questions / Reset questions
        keyboard = [
            [InlineKeyboardButton(trans("Conservar preguntas anteriores"), callback_data='keep_questions')],
            [InlineKeyboardButton(trans("Reiniciar preguntas predeterminadas"), callback_data='reset_questions')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(trans("Selecciona una opción:"), reply_markup=reply_markup)
        return RECEIVE_KEEP_QUESTIONS_RESPONSE
    else:
        # Languages are the same, or no previous language set
        # No need to ask, proceed
        await query.edit_message_text(trans("Idioma seleccionado: {0}").format(lang_code))

        welcome_message = _("¡Bienvenido!\n\nEste bot le ayudará a mejorar y profundizar en la preparación de <b>La Atalaya</b> usando <b>Inteligencia Artificial</b>. El modelo está personalizado por mí en OpenAI para intentar apegarse lo más posible a la realidad, pero es imposible que todas las respuestas sean correctas y sin alucinaciones.\n\nEl bot funciona respondiendo a las preguntas que le dictes. Es decir: si en la pregunta 1, le solicitas que te explique algún punto del párrafo con una ilustración, lo que hará será contestar a la pregunta de el/los párrafo(s) de la Atalaya, e introducirla en el recuadro de texto habilitado para ello.\n\nMás adelante <b>se le sugerirá enviar su archivo de respaldo de .jwlibrary para no perder ninguna información en su dispositivo</b>. Esto es particularmente importante, ya que al restaurar el archivo .jwlibrary que se genera, sus notas y marcas que tenía anteriormente en la aplicación, se perderán. Recomendamos, además, que el artículo de estudio que quiera prepararse esté vacío en su dispositivo, para evitar incongruencias.\n\nEsta aplicación no es oficial ni está afiliada de ningún modo con JW.ORG\n\nSi el bot tardara en responder, espere unos minutos y contacte con @geiserdrums. El bot sirve a cada usuario individualmente de manera secuencial, con lo que quizá lo esté usando otra persona en este mismo instante, sea paciente")
        await update.effective_chat.send_message(trans(welcome_message), parse_mode=telegram.constants.ParseMode.HTML)

        return await ask_backup(update, context)

async def receive_keep_questions_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    user = update.effective_user
    lang_code = context.user_data['language']
    previous_language = context.user_data.get('previous_language')

    logger.info("RECEIVE_KEEP_QUESTIONS_RESPONSE - User ID: {0} - Choice: {1}".format(user.id, user_choice))
    translation = context.user_data['translation']
    trans = translation.gettext

    if user_choice == 'keep_questions':
        # User wants to keep their questions
        await query.edit_message_text(trans("Se conservarán tus preguntas anteriores."))
    elif user_choice == 'reset_questions':
        # User wants to reset questions
        # Reset the default questions in the database
        init_questions, translated_questions = get_default_questions(trans)
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE Main SET Q1 = ?, Q2 = ?, Q3 = ?, Q4 = NULL, Q5 = NULL, Q6 = NULL, Q7 = NULL, Q8 = NULL, Q9 = NULL, Q10 = NULL WHERE UserId = ?",
            (*init_questions, user.id)
        )
        connection.commit()
        connection.close()
        await query.edit_message_text(trans("Tus preguntas han sido reiniciadas a las predeterminadas en el nuevo idioma."))

    # Proceed to next step
    # Send the welcome message
    if context.user_data.get('command') == 'start':
        welcome_message = _("¡Bienvenido!\n\nEste bot le ayudará a mejorar y profundizar en la preparación de <b>La Atalaya</b> usando <b>Inteligencia Artificial</b>. El modelo está personalizado por mí en OpenAI para intentar apegarse lo más posible a la realidad, pero es imposible que todas las respuestas sean correctas y sin alucinaciones.\n\nEl bot funciona respondiendo a las preguntas que le dictes. Es decir: si en la pregunta 1, le solicitas que te explique algún punto del párrafo con una ilustración, lo que hará será contestar a la pregunta de el/los párrafo(s) de la Atalaya, e introducirla en el recuadro de texto habilitado para ello.\n\nMás adelante <b>se le sugerirá enviar su archivo de respaldo de .jwlibrary para no perder ninguna información en su dispositivo</b>. Esto es particularmente importante, ya que al restaurar el archivo .jwlibrary que se genera, sus notas y marcas que tenía anteriormente en la aplicación, se perderán. Recomendamos, además, que el artículo de estudio que quiera prepararse esté vacío en su dispositivo, para evitar incongruencias.\n\nEsta aplicación no es oficial ni está afiliada de ningún modo con JW.ORG\n\nSi el bot tardara en responder, espere unos minutos y contacte con @geiserdrums. El bot sirve a cada usuario individualmente de manera secuencial, con lo que quizá lo esté usando otra persona en este mismo instante, sea paciente")
        await update.effective_chat.send_message(trans(welcome_message), parse_mode=telegram.constants.ParseMode.HTML)

    return await ask_backup(update, context)

async def ask_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    translation = context.user_data['translation']
    trans = translation.gettext
    context.user_data['conversation_active'] = True  # Set flag indicating conversation is active
    if update.message:
        await update.message.reply_text(trans("¿Deseas proporcionar tu archivo de respaldo .jwlibrary? Por favor envíalo ahora. Si prefieres no hacerlo, escribe 'no'."))
    elif update.callback_query:
        await update.callback_query.message.reply_text(trans("¿Deseas proporcionar tu archivo de respaldo .jwlibrary? Por favor envíalo ahora. Si prefieres no hacerlo, escribe 'no'."))
    return RECEIVE_BACKUP_FILE

async def receive_backup_file_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    translation = context.user_data['translation']
    trans = translation.gettext
    file = update.message.document
    file_path = file.file_name
    logger.info("RECEIVE_BACKUP_FILE_DOCUMENT - User ID: {0} - File ID: {1} - File Name: {2}".format(user.id, file.file_id, file_path))

    if file_path.endswith(".jwlibrary"):
        # Save the file
        file = await context.bot.get_file(file.file_id)
        await file.download_to_drive('userBackups/{0}.jwlibrary'.format(user.id))
        # Run describe_jwlibrary and post output
        try:
            notesN, inputN, tagMaptN, tagN, bookmarkN, lastModified, userMarkN = core_worker.describe_jwlibrary(user.id)
            await update.message.reply_html(trans("""Estado de tu archivo <code>.jwlibrary</code>:
<u>Notas:</u> {0}
<u>Tags individuales:</u> {1}
<u>Notas con tags:</u> {2}
<u>Escritos en cuadros de texto:</u> {3}
<u>Favoritos:</u> {4}
<u>Frases subrayadas:</u> {5}
<u>Última vez modificado:</u> {6}""").format(notesN, tagN, tagMaptN, inputN, bookmarkN, userMarkN, lastModified))
        except Exception as e:
            logger.error("Error in describe_jwlibrary: %s", e)
            await update.message.reply_text(trans("Ocurrió un error al analizar tu archivo. Continuaremos sin él."))
        # Proceed to next step
        return await ask_date_or_url(update, context)
    else:
        await update.message.reply_text(trans("Formato de archivo erróneo. Por favor, envía un archivo .jwlibrary válido."))
        # Ask again
        return RECEIVE_BACKUP_FILE

async def receive_backup_file_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.lower()
    logger.info("RECEIVE_BACKUP_FILE_TEXT - User ID: {0} - Input: {1}".format(update.effective_user.id, user_input))
    translation = context.user_data['translation']
    trans = translation.gettext
    # Catch all input
    await update.message.reply_text(trans("De acuerdo, continuamos sin el archivo de respaldo."))
    # Proceed to next step
    return await ask_date_or_url(update, context)

async def ask_date_or_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    translation = context.user_data['translation']
    trans = translation.gettext
    keyboard = [
        [InlineKeyboardButton(trans("Seleccionar fecha"), callback_data='date')],
        [InlineKeyboardButton(trans("Proporcionar URL"), callback_data='url')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(trans("¿Deseas seleccionar una fecha o proporcionar una URL específica?"), reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(trans("¿Deseas seleccionar una fecha o proporcionar una URL específica?"), reply_markup=reply_markup)
    return RECEIVE_DATE_OR_URL_CHOICE

def fetch_url_from_date(date_selection, langSelected):
    try:
        now = datetime.now(pytz.timezone('Europe/Madrid'))
        start_date = now - timedelta(days=now.weekday()) + timedelta(int(date_selection)*7)
        dates = []
        for i in range(5):
            dates.append((start_date - timedelta(7*i)).strftime("%Y-%m-%d"))

        jsonurl = requests.get("https://app.jw-cdn.org/catalogs/publications/v4/manifest.json")
        manifest_id = jsonurl.json()['current']
        catalog = requests.get("https://app.jw-cdn.org/catalogs/publications/v4/" + manifest_id + "/catalog.db.gz")
        os.makedirs('dbs', exist_ok=True)
        open('catalog.db.gz', 'wb').write(catalog.content)
        with gzip.open("catalog.db.gz", "rb") as f:
            with open('dbs/catalog.db', 'wb') as f_out:
                shutil.copyfileobj(f, f_out)
        os.remove("catalog.db.gz")
        connection = sqlite3.connect("dbs/catalog.db")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM DatedText WHERE Class = 68 AND (Start = ? OR Start = ? OR Start = ? OR Start = ? OR Start = ?)", (dates[0], dates[1], dates[2], dates[3], dates[4]))
        dates_catalog = cursor.fetchall()

        list_of_dates = [datetime.strptime(x[1],"%Y-%m-%d") for x in dates_catalog]
        date_count = Counter(list_of_dates)
        selected_dates = [date for date in list_of_dates if date_count[date] > 100]

        if not selected_dates:
            raise ValueError("No dates found in catalog")

        newest_date = max(selected_dates).strftime("%Y-%m-%d")
        delta_start_week_found = dates.index(newest_date)
        possiblePubId = [str(x[3]) for x in dates_catalog if x[1] == newest_date]

        cursor.execute("SELECT PublicationRootKeyId, IssueTagNumber, Symbol, Title, IssueTitle, Year, Id FROM Publication WHERE MepsLanguageId = 1 AND Id IN ({0})".format(', '.join(possiblePubId)))
        publication = cursor.fetchall()
        cursor.close()
        connection.close()

        lang_codes = {
            'es': 'S',          # Español
            'en': 'E',          # English
            'fr': 'F',          # Français
            'pt-PT': 'TPO',       # Português (Portugal)
            'pt-BR': 'T',      # Português (Brasil)
            'de': 'X',          # Deutsch
            'bg': 'BL',          # Български
            'it': 'I',          # Italiano
            'nl': 'O',          # Nederlands
            'mk': 'MC'           # Македонски
        }
        lang = lang_codes.get(langSelected, 'E')

        year = publication[0][5]
        symbol = publication[0][2]
        month = str(publication[0][1])[4:6]
        magazine_url = f"https://www.jw.org/finder?wtlocale={lang}&issue={year}-{month}&pub={symbol}"
        magazine = requests.get(magazine_url).text
        soup = BeautifulSoup(magazine, features="html.parser")
        div_study_articles = soup.find_all("div", {"class":"docClass-40"})

        url = "https://www.jw.org" + div_study_articles[delta_start_week_found].find("a").get("href")

        return url
    except Exception as e:
        logger.error("Error fetching URL based on date: %s", e)
        return None
    
async def receive_date_or_url_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    logger.info("RECEIVE_DATE_OR_URL_CHOICE - User ID: {0} - Choice: {1}".format(update.effective_user.id, user_choice))
    translation = context.user_data['translation']
    trans = translation.gettext
    if user_choice == 'date':
        # Proceed to select date
        return await select_date(update, context)
    elif user_choice == 'url':
        await query.edit_message_text(trans("Por favor, envía la URL del artículo de La Atalaya que deseas preparar."))
        return RECEIVE_URL

async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = update.message.text.strip()
    logger.info("RECEIVE_URL - User ID: {0} - URL: {1}".format(update.effective_user.id, url))
    translation = context.user_data['translation']
    trans = translation.gettext
    if validators.url(url):
        u = urlparse(url)
        if u.netloc == "www.jw.org":
            # Save URL in database
            user = update.effective_user
            connection = sqlite3.connect("dbs/main.db")
            cursor = connection.cursor()
            cursor.execute("UPDATE Main SET Url = ?, WeekDelta = null WHERE UserId = ?", (url, user.id))
            connection.commit()
            connection.close()
            await update.message.reply_text(trans("URL guardada: {0}").format(url))

            # Proceed to next step
            return await show_questions(update, context)

async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    translation = context.user_data['translation']
    trans = translation.gettext
    user = update.effective_user
    now = datetime.now(pytz.timezone('Europe/Madrid'))
    start = now - timedelta(days=now.weekday())
    week_ranges = []
    # Get the language code
    lang_code = context.user_data.get('language', 'es')  # Default to 'es' if not set
    babel_locale = lang_code.replace('-', '_')  # Adjust for Babel locale format

    for week in range(4):
        end = start + timedelta(days=6)
        if start.month == end.month:
            start_str = format_date(start, format='d', locale=babel_locale)
            end_str = format_date(end, format='d MMMM', locale=babel_locale)
            week_ranges.append(f"{start_str}-{end_str}")
        else:
            start_str = format_date(start, format='d MMMM', locale=babel_locale)
            end_str = format_date(end, format='d MMMM', locale=babel_locale)
            week_ranges.append(f"{start_str}-{end_str}")

        start = end + timedelta(days=1)

    # Save the week_ranges in context.user_data
    context.user_data['week_ranges'] = week_ranges

    keyboard = []
    for i, button in enumerate(week_ranges):
        keyboard.append([InlineKeyboardButton(button, callback_data=str(i))])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(trans('Por favor, elige una fecha:'), reply_markup=reply_markup)
    return RECEIVE_DATE_SELECTION

async def receive_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date_selection = int(query.data)
    logger.info("RECEIVE_DATE_SELECTION - User ID: {0} - Selection: {1}".format(update.effective_user.id, date_selection))
    translation = context.user_data['translation']
    trans = translation.gettext

    # Retrieve week_ranges from context.user_data
    week_ranges = context.user_data.get('week_ranges', [])
    if week_ranges and 0 <= date_selection < len(week_ranges):
        selected_week = week_ranges[date_selection]
    else:
        selected_week = trans("Fecha desconocida")

    # Save date selection in context
    context.user_data['date_selection'] = date_selection
    # Save to database
    user = update.effective_user
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("UPDATE Main SET WeekDelta = ?, Url = null WHERE UserId = ?", (date_selection, user.id))
    connection.commit()
    connection.close()
    await query.edit_message_text(trans("Fecha seleccionada: {0}").format(selected_week))

    # Fetch URL based on date using helper function
    langSelected = context.user_data.get('language', 'es')

    await query.message.reply_text(trans("Obteniendo el URL basado en la fecha seleccionada. Por favor, espera..."))
    url = fetch_url_from_date(date_selection, langSelected)
    if url:
        # Save URL to database
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("UPDATE Main SET Url = ? WHERE UserId = ?", (url, user.id))
        connection.commit()
        connection.close()
        await query.message.reply_text(trans("URL obtenido a partir de la fecha seleccionada: {0}").format(url))
    else:
        await query.message.reply_text(trans("No se pudo obtener el URL basado en la fecha seleccionada."))

    # Proceed to next step
    return await show_questions(update, context)

def get_default_questions(trans):
    init_question_1 = trans("Una ilustración o ejemplo para explicar algún punto principal del párrafo")
    init_question_2 = trans("Una experiencia en concreto, aportando referencias exactas de jw.org, que esté muy relacionada con el párrafo")
    init_question_3 = trans("Una explicación sobre uno de los textos que aparezcan, que aplique al párrafo. Usa la Biblia de Estudio de los Testigos de Jehová")
    init_questions = [init_question_1, init_question_2, init_question_3]
    # Translate the questions at runtime
    translated_questions = [trans(q) for q in init_questions]
    return init_questions, translated_questions

async def show_questions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    translation = context.user_data['translation']
    trans = translation.gettext
    # Display current questions (q_show)
    user = update.effective_user
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,Q9,Q10 FROM Main WHERE UserId = ?", (user.id,))
    data = cursor.fetchone()
    connection.close()

    num_questions = 10
    questions_text = trans("<u>Tus preguntas actuales:</u>\n")
    has_questions = False
    for i in range(num_questions):
        if data[i]:
            has_questions = True
            questions_text += "{0}. {1}\n".format(i+1, data[i])

    if not has_questions:
        init_questions, translated_questions = get_default_questions(trans)
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE Main SET Q1 = ?, Q2 = ?, Q3 = ? WHERE UserId = ?",
            (*init_questions, user.id)
        )
        connection.commit()
        connection.close()
        questions_text += "\n".join(f"{i}. {q}" for i, q in enumerate(translated_questions, start=1))

    # Reworded question and buttons
    question_text = trans("¿Quieres personalizar las preguntas?")
    keyboard = [
        [InlineKeyboardButton(trans("Sí, quiero personalizar"), callback_data='yes')],
        [InlineKeyboardButton(trans("No, usar predeterminadas"), callback_data='no')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send the messages directly to the chat
    await update.effective_chat.send_message(questions_text, parse_mode=telegram.constants.ParseMode.HTML)
    await update.effective_chat.send_message(question_text, reply_markup=reply_markup)
    return CUSTOMIZE_QUESTIONS_YES_NO

async def customize_questions_yes_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    logger.info("CUSTOMIZE_QUESTIONS_YES_NO - User ID: {0} - Choice: {1}".format(update.effective_user.id, user_choice))
    translation = context.user_data['translation']
    trans = translation.gettext
    if user_choice == 'yes':
        # Proceed to ask whether to edit or delete questions
        return await ask_edit_or_delete(update, context)
    else:
        # Proceed to preparation
        return await w_prepare(update, context)

async def ask_edit_or_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    translation = context.user_data['translation']
    trans = translation.gettext
    # Ask user if they want to edit or delete questions
    keyboard = [
        [InlineKeyboardButton(trans("Editar preguntas"), callback_data='edit')],
        [InlineKeyboardButton(trans("Eliminar preguntas"), callback_data='delete')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(trans("¿Deseas editar o eliminar preguntas?"), reply_markup=reply_markup)
    return CHOOSE_EDIT_OR_DELETE

async def choose_edit_or_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data  # 'edit' or 'delete'
    context.user_data['action'] = action
    logger.info("CHOOSE_EDIT_OR_DELETE - User ID: {0} - Action: {1}".format(update.effective_user.id, action))
    translation = context.user_data['translation']
    trans = translation.gettext
    # Proceed to select question to edit or delete
    return await ask_for_question_number(update, context)

async def ask_for_question_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    translation = context.user_data['translation']
    trans = translation.gettext
    action = context.user_data['action']  # 'edit' or 'delete'
    keyboard = []
    user = update.effective_user
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("SELECT Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,Q9,Q10 FROM Main WHERE UserId = ?", (user.id,))
    data = cursor.fetchone()
    connection.close()
    if action == 'edit':
        # Show all question numbers from Q1 to Q10
        for i in range(1, 11):
            keyboard.append([InlineKeyboardButton(f"Q{i}", callback_data=str(i))])
        text = trans("Por favor, selecciona el número de la pregunta que deseas editar:")
    else:
        # For 'delete', show only questions that have content
        for i in range(1, 11):
            if data[i-1]:
                keyboard.append([InlineKeyboardButton(f"Q{i}", callback_data=str(i))])
        text = trans("Por favor, selecciona el número de la pregunta que deseas eliminar:")
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    return RECEIVE_QUESTION_NUMBER

async def receive_question_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    question_number = int(query.data)
    action = context.user_data['action']  # 'edit' or 'delete'
    logger.info("RECEIVE_QUESTION_NUMBER - User ID: {0} - Question Number: {1} - Action: {2}".format(update.effective_user.id, question_number, action))
    translation = context.user_data['translation']
    trans = translation.gettext
    # Save question number in context
    context.user_data['question_number'] = question_number

    if action == 'edit':
        await query.edit_message_text(trans("Por favor, ingresa el texto para la pregunta {0}:").format(question_number))
        return RECEIVE_QUESTION_TEXT
    elif action == 'delete':
        # Check if more than one question exists
        user = update.effective_user
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT Q1,Q2,Q3,Q4,Q5,Q6,Q7,Q8,Q9,Q10 FROM Main WHERE UserId = ?", (user.id,))
        data = cursor.fetchone()
        non_empty_questions = [q for q in data if q]
        if len(non_empty_questions) <= 1:
            await query.message.reply_text(trans("No puedes eliminar la última pregunta. Debe haber al menos una pregunta."))
            # Return to ask whether to edit or delete
            return await ask_edit_or_delete(update, context)
        else:
            # Delete the question
            cursor.execute(f"UPDATE Main SET Q{question_number} = NULL WHERE UserId = ?", (user.id,))
            connection.commit()
            connection.close()
            await query.message.reply_text(trans("Pregunta {0} eliminada correctamente.").format(question_number))
            # Ask if user wants to perform another action
            return await ask_for_more_actions(update, context)

async def receive_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    question_text = update.message.text.strip()
    user = update.effective_user
    question_number = context.user_data['question_number']
    logger.info("RECEIVE_QUESTION_TEXT - User ID: {0} - Question Number: {1} - Text: {2}".format(user.id, question_number, question_text))
    translation = context.user_data['translation']
    trans = translation.gettext
    # Save the question to the database
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("UPDATE Main SET Q{0} = ? WHERE UserId = ?".format(question_number), (question_text, user.id))
    connection.commit()
    connection.close()
    await update.message.reply_text(trans("Pregunta {0} guardada correctamente.").format(question_number))
    # Ask if user wants to perform another action
    return await ask_for_more_actions(update, context)

async def ask_for_more_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    translation = context.user_data['translation']
    trans = translation.gettext
    keyboard = [
        [InlineKeyboardButton(trans("Sí"), callback_data='yes')],
        [InlineKeyboardButton(trans("No"), callback_data='no')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(trans("¿Deseas realizar otra acción sobre las preguntas?"), reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(trans("¿Deseas realizar otra acción sobre las preguntas?"), reply_markup=reply_markup)
    return ASK_FOR_MORE_ACTIONS

async def handle_more_actions_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    logger.info("HANDLE_MORE_ACTIONS_RESPONSE - User ID: {0} - Choice: {1}".format(update.effective_user.id, user_choice))
    translation = context.user_data['translation']
    trans = translation.gettext
    if user_choice == 'yes':
        # Ask whether to edit or delete again
        return await ask_edit_or_delete(update, context)
    else:
        # Proceed to preparation
        return await w_prepare(update, context)

async def w_prepare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    translation = context.user_data['translation']
    trans = translation.gettext

    # Determine the message object
    if update.message:
        message = update.message
        await message.reply_text(trans("Comenzando la preparación. Por favor, espera..."))
        await message.reply_chat_action(action=telegram.constants.ChatAction.TYPING)
    elif update.callback_query:
        message = update.callback_query.message
        await message.reply_text(trans("Comenzando la preparación. Por favor, espera..."))
        await context.bot.send_chat_action(chat_id=message.chat_id, action=telegram.constants.ChatAction.TYPING)
    else:
        # Handle unexpected cases
        logger.error("No message or callback_query in update.")
        return ConversationHandler.END

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
    # Fetch additional user info
    cursor.execute("SELECT UserName, FirstName, LastName, LangCodeTelegram FROM Main WHERE UserId = ?", (user.id,))
    user_info = cursor.fetchone()
    connection.close()

    url = url_result[0] if url_result else None
    date = date_result[0] if date_result else None
    lastRun = lastRun_result[0] if lastRun_result else None
    langSelected = langSelected_result[0] if langSelected_result else 'es'

    username = user_info[0] if user_info else ''
    firstname = user_info[1] if user_info else ''
    lastname = user_info[2] if user_info else ''
    langcodetelegram = user_info[3] if user_info else ''

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

    # New code to send notification
    try:
        # Get the TOKEN_NOTIFY from environment variable
        TOKEN_NOTIFY = os.environ["TOKEN_NOTIFY"]
        notify_bot = telegram.Bot(token=TOKEN_NOTIFY)
        # Prepare the message
        message_text = (
            f"User Started Preparation:\n"
            f"UserId: {user.id}\n"
            f"UserName: {username}\n"
            f"FirstName: {firstname}\n"
            f"LastName: {lastname}\n"
            f"LangCodeTelegram: {langcodetelegram}\n"
            f"LangSelected: {langSelected}\n"
            f"Url: {url}\n"
            f"WeekDelta: {date}\n"
            f"Questions:\n"
        )
        for i, q in enumerate(qs, start=1):
            message_text += f"q{i}: {q}\n"
        # Send the message to user ID 835003
        await notify_bot.send_message(chat_id=835003, text=message_text)
    except Exception as e:
        logger.error("Error sending notification: %s", e)

    if any(qs):
        if (url is not None) and (date is not None):
            await message.reply_text(trans("Tienes guardados una fecha y una URL. Se está tomando la fecha como valor predeterminado."))
        if date is not None:
            # Fetch URL based on date if URL is None using helper function
            if url is None:
                await message.reply_text(trans("Obteniendo el URL basado en la fecha seleccionada. Por favor, espera..."))
                url = fetch_url_from_date(date, langSelected)
                if url:
                    # Save URL to database
                    connection = sqlite3.connect("dbs/main.db")
                    cursor = connection.cursor()
                    cursor.execute("UPDATE Main SET Url = ? WHERE UserId = ?", (url, user.id))
                    connection.commit()
                    connection.close()
                    await message.reply_text(trans("URL obtenido a partir de la fecha seleccionada: {0}").format(url))
                else:
                    await message.reply_text(trans("No se pudo obtener el URL basado en la fecha seleccionada."))
                    return ConversationHandler.END

        if (url is not None):
            await message.reply_text(trans("Comenzando peticiones a ChatGPT. Podría tardar varios minutos dependiendo del número de preguntas que hayas configurado."))

            try:
                # Call the core_worker.main function
                filenamejw, filenamedoc, filenamepdf = core_worker.main(url, user.id, qs, langSelected)

                if os.path.isfile('userBackups/{0}.jwlibrary'.format(user.id)):
                    await message.reply_text(trans("Aquí tienes tu fichero, impórtalo en JW Library."))
                else:
                    await message.reply_text(trans("Aquí tienes tu fichero, impórtalo en JW Library.\nNota: Al no haber proporcionado tu copia de seguridad, hazlo con precaución, puedes perder tus datos de la app."))

                # Send the JW Library file
                await message.reply_document(document=open(filenamejw, "rb"))
                os.remove(filenamejw)

                await message.reply_text(trans("Aquí también encontrarás los archivos en formato Word y PDF"))
                await message.reply_document(document=open(filenamedoc, "rb"))
                os.remove(filenamedoc)

                await message.reply_document(document=open(filenamepdf, "rb"))
                os.remove(filenamepdf)

            except Exception as e:
                logger.error("Error in core_worker.main: %s", e)
                await message.reply_text(trans("Ocurrió un error al preparar los archivos. Por favor, inténtalo de nuevo más tarde."))
                return ConversationHandler.END
        else:
            await message.reply_text(trans("No has seleccionado ninguna fecha o URL"))
            return ConversationHandler.END
    else:
        await message.reply_text(trans("Todas las preguntas están vacías"))
        return ConversationHandler.END

    # After preparation, ask the user if they want to prepare another article
    keyboard = [
        [InlineKeyboardButton(trans("Sí"), callback_data='yes')],
        [InlineKeyboardButton(trans("No"), callback_data='no')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(trans("¿Deseas preparar con otras preguntas u otro artículo de La Atalaya?\nNota: Si decide no seguir, las preguntas adicionales que haya añadido se eliminarán."), reply_markup=reply_markup)
    return AFTER_PREPARATION

async def after_preparation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    user = update.effective_user
    logger.info("AFTER_PREPARATION - User ID: {0} - Choice: {1}".format(user.id, user_choice))
    translation = context.user_data['translation']
    trans = translation.gettext

    now = datetime.now(pytz.timezone('Europe/Madrid'))

    # Check LastRun timestamp unless user is admin
    if user.id not in [835003, 5978895313]:
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT LastRun FROM Main WHERE UserId = ?", (user.id,))
        last_run_row = cursor.fetchone()
        connection.close()

        if last_run_row:
            last_run_str = last_run_row[0]
            if last_run_str:
                last_run = datetime.fromisoformat(last_run_str)
                time_since_last_run = now - last_run
                if time_since_last_run < timedelta(hours=1):
                    remaining_time = timedelta(hours=1) - time_since_last_run
                    minutes = int(remaining_time.total_seconds() // 60)
                    await query.message.reply_text(
                        trans("Por favor, inténtelo de nuevo dentro de {} minutos. Así puedo controlar mejor los gastos, ya que es gratuito. Si tiene algún problema, contacte con @geiserdrums").format(minutes)
                    )
                    # Conversation ends
                    context.user_data['conversation_active'] = False
                    return ConversationHandler.END

    # No longer deleting questions in database
    # Questions are now persisted at all times

    if user_choice == 'yes':
        await query.message.reply_text(trans("Comenzando de nuevo..."))
        return await ask_backup(update, context)
    else:
        await query.message.reply_text(trans("Para ejecutar el bot nuevamente, por favor escribe /start"))
        # Conversation ends
        context.user_data['conversation_active'] = False
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info("User %s canceled the conversation.", user.first_name)
    translation = context.user_data.get('translation', get_translation(context))
    trans = translation.gettext
    await update.message.reply_text(trans("Operación cancelada."))
    # Conversation ends
    context.user_data['conversation_active'] = False
    return ConversationHandler.END

async def admin_broadcast_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id in [835003, 5978895313]:
        message_text = update.message.text.partition(' ')[2]  # Get text after command
        if not message_text:
            await update.message.reply_text("Por favor, proporciona un mensaje para enviar a todos los usuarios.")
            return
        # Fetch all user IDs from the database
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT UserId FROM Main")
        user_ids = cursor.fetchall()
        connection.close()
        # Send the message to all users
        success_count = 0
        for user_id_tuple in user_ids:
            user_id = user_id_tuple[0]
            try:
                await context.bot.send_message(chat_id=user_id, text=message_text)
                success_count +=1
            except Exception as e:
                logger.error(f"Failed to send message to {user_id}: {e}")
        await update.message.reply_text(f"Mensaje enviado a {success_count} usuarios.")
    else:
        await update.message.reply_text("No tienes permiso para usar este comando.")

def main() -> None:
    application = Application.builder().token(os.environ["TOKEN"]).build()

    # Create 'dbs' directory if not exists
    os.makedirs('dbs', exist_ok=True)

    # Connect to the SQLite database
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()

    # Create the 'Main' table if it does not exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS "Main" (
    	"UserId"	INTEGER NOT NULL,
    	"UserName"	TEXT,
    	"FirstName"	TEXT,
    	"LastName"	TEXT,
    	"LangCodeTelegram"	TEXT,
    	"LangSelected"	TEXT,
    	"IsBot"	TEXT,
    	"Url"	TEXT,
    	"WeekDelta"	INTEGER,
    	"Q1"	TEXT,
    	"Q2"	TEXT,
    	"Q3"	TEXT,
    	"Q4"	TEXT,
    	"Q5"	TEXT,
    	"Q6"	TEXT,
    	"Q7"	TEXT,
    	"Q8"	TEXT,
    	"Q9"	TEXT,
    	"Q10"	TEXT,
    	"LastRun"	TEXT,
    	PRIMARY KEY("UserId")
    );''')
    connection.commit() # ALTER TABLE Main DROP COLUMN StandardLangCode; - delete when next version
    connection.close()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('change_language', change_language)],
        states={
            LANG_SELECT: [
                CallbackQueryHandler(language_selected, pattern='^lang_'),
                CommandHandler('cancel', cancel),
            ],
            RECEIVE_KEEP_QUESTIONS_RESPONSE: [
                CallbackQueryHandler(receive_keep_questions_response),
                CommandHandler('cancel', cancel),
            ],
            RECEIVE_BACKUP_FILE: [
                MessageHandler(filters.Document.ALL, receive_backup_file_document),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_backup_file_text),
                CommandHandler('cancel', cancel),
            ],
            RECEIVE_DATE_OR_URL_CHOICE: [
                CallbackQueryHandler(receive_date_or_url_choice),
                CommandHandler('cancel', cancel),
            ],
            RECEIVE_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url),
                CommandHandler('cancel', cancel),
            ],
            RECEIVE_DATE_SELECTION: [
                CallbackQueryHandler(receive_date_selection),
                CommandHandler('cancel', cancel),
            ],
            CUSTOMIZE_QUESTIONS_YES_NO: [
                CallbackQueryHandler(customize_questions_yes_no),
                CommandHandler('cancel', cancel),
            ],
            CHOOSE_EDIT_OR_DELETE: [
                CallbackQueryHandler(choose_edit_or_delete),
                CommandHandler('cancel', cancel),
            ],
            RECEIVE_QUESTION_NUMBER: [
                CallbackQueryHandler(receive_question_number),
                CommandHandler('cancel', cancel),
            ],
            RECEIVE_QUESTION_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_question_text),
                CommandHandler('cancel', cancel),
            ],
            ASK_FOR_MORE_ACTIONS: [
                CallbackQueryHandler(handle_more_actions_response),
                CommandHandler('cancel', cancel),
            ],
            W_PREPARE: [
                MessageHandler(filters.StatusUpdate.ALL, w_prepare),
                CommandHandler('cancel', cancel),
            ],
            AFTER_PREPARATION: [
                CallbackQueryHandler(after_preparation),
                CommandHandler('cancel', cancel),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('admin_broadcast_msg', admin_broadcast_msg))

    application.run_polling()

if __name__ == "__main__":
    main()