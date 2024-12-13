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
import core_worker  # Ensure core_worker module is correctly imported and accessible
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
    CHOOSE_EDIT_OR_DELETE,
    RECEIVE_QUESTION_NUMBER,
    RECEIVE_QUESTION_TEXT,
    ASK_FOR_MORE_ACTIONS,
    W_PREPARE,
    AFTER_PREPARATION
) = range(12)

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
    await check_if_user_exists(update, context)

    # Check LastRun timestamp unless user is admin
    if user.id != 835003:  # Admin user ID
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT LastRun, LangSelected FROM Main WHERE UserId = ?", (user.id,))
        result = cursor.fetchone()
        connection.close()

        last_run_str = result[0] if result else None
        lang_selected = result[1] if result else None

        # Set the user's selected language in context
        if lang_selected:
            context.user_data['language'] = lang_selected

        _ = get_translation_function(context)

        now = datetime.now(pytz.timezone('Europe/Madrid'))
        if last_run_str:
            last_run = datetime.fromisoformat(last_run_str)
            time_since_last_run = now - last_run
            if time_since_last_run < timedelta(hours=8):
                remaining_time = timedelta(hours=8) - time_since_last_run
                hours, remainder = divmod(remaining_time.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                await update.message.reply_text(
                    _("Por favor, inténtelo de nuevo dentro de {} horas y {} minutos. Así puedo controlar mejor los gastos, ya que es gratuito. Si tiene algún problema, contacte con @geiserdrums").format(hours, minutes)
                )
                return ConversationHandler.END  # End the conversation
    else:
        # Admin user bypasses the last run check
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT LangSelected FROM Main WHERE UserId = ?", (user.id,))
        result = cursor.fetchone()
        connection.close()
        lang_selected = result[0] if result else None
        if lang_selected:
            context.user_data['language'] = lang_selected

    # Proceed as usual
    logger.info("START - User ID: {0} - Username: {1}".format(user.id, user.username))
    # Reset the conversation_active flag
    context.user_data['conversation_active'] = True

    _ = get_translation_function(context)
    context.user_data['command'] = 'start'  # Indicate that the entry point is /start

    # Send the greeting message
    if user.is_bot:
        await update.message.reply_text(_("Los bots no están permitidos"))
        return ConversationHandler.END

    await update.message.reply_html(_(rf"""😊 ¡Bienvenido! 😊

Este bot le ayudará a mejorar y profundizar en la preparación de <b>La Atalaya</b> usando <b>Inteligencia Artificial</b>. El modelo está personalizado por mí en OpenAI para intentar apegarse lo más posible a la realidad, pero es imposible que todas las respuestas sean correctas y sin alucinaciones.

El bot funciona respondiendo a las preguntas que le dictes. Es decir: si en la pregunta 1, le solicitas que te explique algún punto del párrafo con una ilustración, lo que hará será contestar a la pregunta de el/los párrafo(s) de la Atalaya, e introducirla en el recuadro de texto habilitado para ello.

Más adelante <b>se le sugerirá enviar su archivo de respaldo de .jwlibrary para no perder ninguna información en su dispositivo</b>. Esto es particularmente importante, ya que al restaurar el archivo .jwlibrary que se genera, sus notas y marcas que tenía anteriormente en la aplicación, se perderán. Recomendamos, además, que el artículo de estudio que quiera prepararse esté vacío en su dispositivo, para evitar incongruencias.

Cada vez que ejecute /start , sus preguntas guardadas se <b>borrarán</b> y comenzará con las que el software ofrece por defecto.

Esta aplicación no es oficial ni está afiliada de ningún modo con JW.ORG

Si el bot tardara en responder, espere unos minutos y contacte con @geiserdrums . El bot sirve a cada usuario individualmente de manera secuencial, con lo que quizá lo esté usando otra persona en este mismo instante, sea paciente"""))

    if 'language' in context.user_data:
        # Language is already set; proceed to the next step
        return await ask_backup(update, context)
    else:
        # Ask user to select language
        return await language_select(update, context)

async def language_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info("LANGUAGE_SELECT - User ID: {0}".format(user.id))

    languages = [("English", "en"), ("Español", "es"), ("Français", "fr"), ("Português", "pt"), ("Deutsch", "de"), ("Български", "bg")]

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

    context.user_data['language'] = lang_code

    # Save to database
    connection = sqlite3.connect("dbs/main.db")
    cursor = connection.cursor()
    cursor.execute("UPDATE Main SET LangSelected = ? WHERE UserId = ?", (lang_code, user.id))
    connection.commit()
    connection.close()

    # Acknowledge the selection
    _ = get_translation_function(context)
    await query.edit_message_text(_("Idioma seleccionado: {0}").format(lang_code))

    # Decide what to do next based on the command
    if context.user_data.get('command') == 'change_language':
        # End the conversation
        await query.message.reply_text(_("Idioma cambiado exitosamente."))
        return ConversationHandler.END
    elif context.user_data.get('command') == 'start':
        # Send the greeting message
        if user.is_bot:
            await query.message.reply_text(_("Los bots no están permitidos"))
            return ConversationHandler.END

        await query.message.reply_html(_(rf"""😊 ¡Bienvenido! 😊

Este bot le ayudará a mejorar y profundizar en la preparación de <b>La Atalaya</b> usando <b>Inteligencia Artificial</b>. El modelo está personalizado por mí en OpenAI para intentar apegarse lo más posible a la realidad, pero es imposible que todas las respuestas sean correctas y sin alucinaciones.

El bot funciona respondiendo a las preguntas que le dictes. Es decir: si en la pregunta 1, le solicitas que te explique algún punto del párrafo con una ilustración, lo que hará será contestar a la pregunta de el/los párrafo(s) de la Atalaya, e introducirla en el recuadro de texto habilitado para ello.

Más adelante <b>se le sugerirá enviar su archivo de respaldo de .jwlibrary para no perder ninguna información en su dispositivo</b>. Esto es particularmente importante, ya que al restaurar el archivo .jwlibrary que se genera, sus notas y marcas que tenía anteriormente en la aplicación, se perderán. Recomendamos, además, que el artículo de estudio que quiera prepararse esté vacío en su dispositivo, para evitar incongruencias.

Cada vez que ejecute /start , sus preguntas guardadas se <b>borrarán</b> y comenzará con las que el software ofrece por defecto.

Esta aplicación no es oficial ni está afiliada de ningún modo con JW.ORG

Si el bot tardara en responder, espere unos minutos y contacte con @geiserdrums . El bot sirve a cada usuario individualmente de manera secuencial, con lo que quizá lo esté usando otra persona en este mismo instante, sea paciente"""))

        # Proceed to next step in the conversation
        return await ask_backup(update, context)
    else:
        # Just in case
        return ConversationHandler.END

async def ask_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = get_translation_function(context)
    context.user_data['conversation_active'] = True  # Set flag indicating conversation is active
    if update.message:
        await update.message.reply_text(_("¿Deseas proporcionar tu archivo de respaldo .jwlibrary? Por favor envíalo ahora. Si prefieres no hacerlo, escribe 'no' u 'omitir'."))
    elif update.callback_query:
        await update.callback_query.message.reply_text(_("¿Deseas proporcionar tu archivo de respaldo .jwlibrary? Por favor envíalo ahora. Si prefieres no hacerlo, escribe 'no' u 'omitir'."))
    return RECEIVE_BACKUP_FILE

async def receive_backup_file_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    _ = get_translation_function(context)
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
            await update.message.reply_html(_("""Estado de tu archivo <code>.jwlibrary</code>:
<u>Notas:</u> {0}
<u>Tags individuales:</u> {1}
<u>Notas con tags:</u> {2}
<u>Escritos en cuadros de texto:</u> {3}
<u>Favoritos:</u> {4}
<u>Frases subrayadas:</u> {5}
<u>Última vez modificado:</u> {6}""").format(notesN, tagN, tagMaptN, inputN, bookmarkN, userMarkN, lastModified))
        except Exception as e:
            logger.error("Error in describe_jwlibrary: %s", e)
            await update.message.reply_text(_("Ocurrió un error al analizar tu archivo. Continuaremos sin él."))
        # Proceed to next step
        return await ask_date_or_url(update, context)
    else:
        await update.message.reply_text(_("Formato de archivo erróneo. Por favor, envía un archivo .jwlibrary válido."))
        # Ask again
        return RECEIVE_BACKUP_FILE

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
    if update.message:
        await update.message.reply_text(_("¿Deseas seleccionar una fecha o proporcionar una URL específica?"), reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(_("¿Deseas seleccionar una fecha o proporcionar una URL específica?"), reply_markup=reply_markup)
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
    cursor.execute("UPDATE Main SET WeekDelta = ?, Url = null WHERE UserId = ?", (date_selection, user.id))
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
            cursor.execute("UPDATE Main SET Url = ?, WeekDelta = null WHERE UserId = ?", (url, user.id))
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
    has_questions = False
    for i in range(num_questions):
        if data[i]:
            has_questions = True
            questions_text += "{0}. {1}\n".format(i+1, data[i])

    if not has_questions:
        # Initialize default questions
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE Main SET Q1 = ?, Q2 = ?, Q3 = ? WHERE UserId = ?",
            (init_questions[0], init_questions[1], init_questions[2], user.id)
        )
        connection.commit()
        connection.close()
        questions_text += "\n".join(f"{i+1}. {q}" for i, q in enumerate(init_questions))

    # Reworded question and buttons
    question_text = _("¿Quieres personalizar las preguntas?")
    keyboard = [
        [InlineKeyboardButton(_("Sí, quiero personalizar"), callback_data='yes')],
        [InlineKeyboardButton(_("No, usar predeterminadas"), callback_data='no')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_html(questions_text)
        await update.message.reply_text(question_text, reply_markup=reply_markup)
    elif update.callback_query:
        message = update.callback_query.message
        await message.reply_html(questions_text)
        await message.reply_text(question_text, reply_markup=reply_markup)
    return CUSTOMIZE_QUESTIONS_YES_NO

async def customize_questions_yes_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    logger.info("CUSTOMIZE_QUESTIONS_YES_NO - User ID: {0} - Choice: {1}".format(update.effective_user.id, user_choice))
    _ = get_translation_function(context)
    if user_choice == 'yes':
        # Proceed to ask whether to edit or delete questions
        return await ask_edit_or_delete(update, context)
    else:
        # Proceed to preparation
        return await w_prepare(update, context)

async def ask_edit_or_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = get_translation_function(context)
    # Ask user if they want to edit or delete questions
    keyboard = [
        [InlineKeyboardButton(_("Editar preguntas"), callback_data='edit')],
        [InlineKeyboardButton(_("Eliminar preguntas"), callback_data='delete')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(_("¿Deseas editar o eliminar preguntas?"), reply_markup=reply_markup)
    return CHOOSE_EDIT_OR_DELETE

async def choose_edit_or_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data  # 'edit' or 'delete'
    context.user_data['action'] = action
    logger.info("CHOOSE_EDIT_OR_DELETE - User ID: {0} - Action: {1}".format(update.effective_user.id, action))
    _ = get_translation_function(context)
    # Proceed to select question to edit or delete
    return await ask_for_question_number(update, context)

async def ask_for_question_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = get_translation_function(context)
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
        text = _("Por favor, selecciona el número de la pregunta que deseas editar:")
    else:
        # For 'delete', show only questions that have content
        for i in range(1, 11):
            if data[i-1]:
                keyboard.append([InlineKeyboardButton(f"Q{i}", callback_data=str(i))])
        text = _("Por favor, selecciona el número de la pregunta que deseas eliminar:")
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    return RECEIVE_QUESTION_NUMBER

async def receive_question_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    question_number = int(query.data)
    action = context.user_data['action']  # 'edit' or 'delete'
    logger.info("RECEIVE_QUESTION_NUMBER - User ID: {0} - Question Number: {1} - Action: {2}".format(update.effective_user.id, question_number, action))
    _ = get_translation_function(context)
    # Save question number in context
    context.user_data['question_number'] = question_number

    if action == 'edit':
        await query.edit_message_text(_("Por favor, ingresa el texto para la pregunta {0}:").format(question_number))
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
            await query.message.reply_text(_("No puedes eliminar la última pregunta. Debe haber al menos una pregunta."))
            # Return to ask whether to edit or delete
            return await ask_edit_or_delete(update, context)
        else:
            # Delete the question
            cursor.execute(f"UPDATE Main SET Q{question_number} = NULL WHERE UserId = ?", (user.id,))
            connection.commit()
            connection.close()
            await query.message.reply_text(_("Pregunta {0} eliminada correctamente.").format(question_number))
            # Ask if user wants to perform another action
            return await ask_for_more_actions(update, context)

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
    # Ask if user wants to perform another action
    return await ask_for_more_actions(update, context)

async def ask_for_more_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = get_translation_function(context)
    keyboard = [
        [InlineKeyboardButton(_("Sí"), callback_data='yes')],
        [InlineKeyboardButton(_("No"), callback_data='no')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(_("¿Deseas realizar otra acción sobre las preguntas?"), reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(_("¿Deseas realizar otra acción sobre las preguntas?"), reply_markup=reply_markup)
    return ASK_FOR_MORE_ACTIONS

async def handle_more_actions_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    logger.info("HANDLE_MORE_ACTIONS_RESPONSE - User ID: {0} - Choice: {1}".format(update.effective_user.id, user_choice))
    _ = get_translation_function(context)
    if user_choice == 'yes':
        # Ask whether to edit or delete again
        return await ask_edit_or_delete(update, context)
    else:
        # Proceed to preparation
        return await w_prepare(update, context)

async def w_prepare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    _ = get_translation_function(context)
    # Determine the message object
    if update.message:
        message = update.message
        await message.reply_text(_("Comenzando la preparación. Por favor, espera..."))
        await message.reply_chat_action(action=telegram.constants.ChatAction.TYPING)
    elif update.callback_query:
        message = update.callback_query.message
        await message.reply_text(_("Comenzando la preparación. Por favor, espera..."))
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
            await message.reply_text(_("Tienes guardados una fecha y una URL. Se está tomando la fecha como valor predeterminado. Si quieres usar la URL, borra la fecha con /date_delete"))
        if date is not None:
            # Logic to fetch URL based on date
            if url is None:
                await message.reply_text(_("Obteniendo el URL basado en la fecha seleccionada. Por favor, espera..."))
                # Implement the logic to get the URL from the date
                # Fetch the URL based on date and language
                # --- Begin logic to fetch URL based on date ---
                try:
                    now = datetime.now(pytz.timezone('Europe/Madrid'))
                    start_date = now - timedelta(days=now.weekday()) + timedelta(int(date)*7)
                    dates = []
                    for i in range(5):
                        dates.append((start_date - timedelta(7*i)).strftime("%Y-%m-%d"))

                    jsonurl = requests.get("https://app.jw-cdn.org/catalogs/publications/v4/manifest.json")
                    manifest_id = jsonurl.json()['current']
                    catalog = requests.get("https://app.jw-cdn.org/catalogs/publications/v4/" + manifest_id + "/catalog.db.gz")
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

                    # Map langSelected to JW language codes
                    lang_codes = {
                        'es': 'S',
                        'en': 'E',
                        'fr': 'F',
                        'pt': 'P',
                        'de': 'D',
                        'bg': 'B',
                        # Add other language codes as needed
                    }
                    lang = lang_codes.get(langSelected, 'E')

                    year = publication[0][5]
                    symbol = publication[0][2]
                    month = str(publication[0][1])[4:6]
                    magazine = requests.get(f"https://www.jw.org/finder?wtlocale={lang}&issue={year}-{month}&pub={symbol}").text
                    soup = BeautifulSoup(magazine, features="html.parser")
                    div_study_articles = soup.find_all("div", {"class":"docClass-40"})

                    url = "https://www.jw.org" + div_study_articles[delta_start_week_found].find("a").get("href")
                    # Save URL to database
                    connection = sqlite3.connect("dbs/main.db")
                    cursor = connection.cursor()
                    cursor.execute("UPDATE Main SET Url = ? WHERE UserId = ?", (url, user.id))
                    connection.commit()
                    connection.close()
                    await message.reply_text(_("URL obtenido a partir de la fecha seleccionada."))
                except Exception as e:
                    logger.error("Error fetching URL based on date: %s", e)
                    await message.reply_text(_("No se pudo obtener el URL basado en la fecha seleccionada."))
                    return ConversationHandler.END
                # --- End logic to fetch URL based on date ---

        if (url is not None):
            await message.reply_text(_("Comenzando peticiones a ChatGPT. Podría tardar incluso más de 10 minutos dependiendo del número de preguntas que hayas configurado."))

            try:
                filenamejw, filenamedoc, filenamepdf = core_worker.main(url, user.id, qs)
                if os.path.isfile('userBackups/{0}.jwlibrary'.format(user.id)):
                    await message.reply_text(_("Aquí tienes tu fichero, impórtalo en JW Library. Recuerda hacer una copia de seguridad para no perder los datos, ya que proporcionaste tu archivo .jwlibrary"))
                else:
                    await message.reply_text(_("Aquí tienes tu fichero, impórtalo en JW Library. Al no haber proporcionado tu copia de seguridad, hazlo con precaución."))

                # Send the JW Library file
                await message.reply_document(document=open(filenamejw, "rb"))
                os.remove(filenamejw)

                await message.reply_text(_("Aquí también encontrarás los archivos en formato Word y PDF"))
                await message.reply_document(document=open(filenamedoc, "rb"))
                os.remove(filenamedoc)

                await message.reply_document(document=open(filenamepdf, "rb"))
                os.remove(filenamepdf)

            except Exception as e:
                logger.error("Error in core_worker.main: %s", e)
                await message.reply_text(_("Ocurrió un error al preparar los archivos. Por favor, inténtalo de nuevo más tarde."))
                return ConversationHandler.END
        else:
            await message.reply_text(_("No has seleccionado ninguna fecha o URL"))
            return ConversationHandler.END
    else:
        await message.reply_text(_("Todas las preguntas están vacías"))
        return ConversationHandler.END

    # After preparation, ask the user if they want to prepare another article
    keyboard = [
        [InlineKeyboardButton(_("Sí"), callback_data='yes')],
        [InlineKeyboardButton(_("No"), callback_data='no')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(_("¿Deseas preparar con otras preguntas u otro artículo de La Atalaya?\nNota: Las preguntas ahora se eliminan."), reply_markup=reply_markup)
    return AFTER_PREPARATION

async def after_preparation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_choice = query.data
    user = update.effective_user
    logger.info("AFTER_PREPARATION - User ID: {0} - Choice: {1}".format(user.id, user_choice))
    _ = get_translation_function(context)

    now = datetime.now(pytz.timezone('Europe/Madrid'))

    # Check LastRun timestamp unless user is admin
    if user.id != 835003:
        connection = sqlite3.connect("dbs/main.db")
        cursor = connection.cursor()
        cursor.execute("SELECT LastRun FROM Main WHERE UserId = ?", (user.id,))
        last_run_str = cursor.fetchone()[0]
        connection.close()

        if last_run_str:
            last_run = datetime.fromisoformat(last_run_str)
            time_since_last_run = now - last_run
            if time_since_last_run < timedelta(hours=8):
                remaining_time = timedelta(hours=8) - time_since_last_run
                hours, remainder = divmod(remaining_time.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                await query.message.reply_text(
                    _("Por favor, inténtelo de nuevo dentro de {} horas y {} minutos. Así puedo controlar mejor los gastos, ya que es gratuito. Si tiene algún problema, contacte con @geiserdrums").format(hours, minutes)
                )
                # Conversation ends
                context.user_data['conversation_active'] = False
                return ConversationHandler.END

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
        await query.message.reply_text(_("Comenzando de nuevo..."))
        return await ask_backup(update, context)
    else:
        await query.message.reply_text(_("Las preguntas ahora están eliminadas. Para ejecutar el bot nuevamente, por favor escribe /start"))
        # Conversation ends
        context.user_data['conversation_active'] = False
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info("User %s canceled the conversation.", user.first_name)
    _ = get_translation_function(context)
    await update.message.reply_text(_("Operación cancelada."))
    # Conversation ends
    context.user_data['conversation_active'] = False
    return ConversationHandler.END

async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info("CHANGE_LANGUAGE - User ID: {0}".format(user.id))

    context.user_data['command'] = 'change_language'  # Indicate that the entry point is /change_language

    return await language_select(update, context)

async def admin_broadcast_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id == 835003:  # Admin user ID
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

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('change_language', change_language)],
        states={
            LANG_SELECT: [
                CallbackQueryHandler(language_selected, pattern='^lang_'),
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
                # If w_prepare doesn't expect user input, you can use a MessageHandler to proceed
                MessageHandler(filters.ALL, w_prepare),
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