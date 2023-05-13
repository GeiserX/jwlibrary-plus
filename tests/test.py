import asyncio
from pathlib import Path
from decouple import config
from pyrogram import Client
import os
from dotenv import load_dotenv
from tgintegration import BotController

SESSION_NAME: str = "jwlibrary_plus_testing"
load_dotenv() # .env File

def create_client(session_name: str = SESSION_NAME) -> Client:
    return Client(
        name=session_name,
        api_id = os.getenv("API_ID") ,
        api_hash = os.getenv("API_HASH") 
    )


async def run_test(client: Client):
    controller = BotController(
        peer="@jwlibrary_plus_dev_bot", # @jwlibrary_plus_bot
        client=client,
        max_wait=5,  # Maximum timeout for responses (optional)
        wait_consecutive=5,  # Minimum time to wait for more/consecutive messages (optional)
        raise_no_response=True,  # Raise `InvalidResponseError` when no response received (defaults to True)
        #global_action_delay=2.5,  # Choosing a rather high delay so we can follow along in realtime (optional)
    )

    print("Clearing chat to start with a blank screen")
    await controller.clear_chat()

    #Initialize DB - TODO

    print("Sending /start")
    async with controller.collect(count=1) as response:
        await controller.send_command("start")
    assert "Bienvenido" in response.messages[0].text
    print("First message contains the link to the bot's source code")

    print("Sending /date_select")
    async with controller.collect(count=1) as response:
        await controller.send_command("date_select")
    inline_keyboard = response.inline_keyboards[0]
    assert len(inline_keyboard.rows) == 4
    print("Dates shown")

    print("Clicking the first option")
    async with controller.collect(count=1) as response:
        await inline_keyboard.click(index=0)
    assert "seleccionada" in response.messages[0].text
    print("Selected the first option")

    print("Sending /date_show")
    async with controller.collect(count=1) as response:
        await controller.send_command("date_show")
    assert "configurada" in response.messages[0].text
    print("Date shown")

    print("Sending /date_delete")
    async with controller.collect(count=1) as response:
        await controller.send_command("date_delete")
    assert "eliminada" in response.messages[0].text
    print("Date deleted")

    async with controller.collect(count=1, max_wait=30) as response: # Intermediate step
        await controller.send_command("date_select")
    inline_keyboard = response.inline_keyboards[0]
    await inline_keyboard.click(index=0)
    
    print("Sending /url_select")
    async with controller.collect(count=2) as response:
        await controller.send_command("url_select", args=["https://www.jw.org/es/biblioteca/revistas/atalaya-estudio-julio-2023/Seamos-razonables-como-Jehov%C3%A1/"])
    assert "32" in response.messages[1].text
    print("Url selected")   

    print("Sending /url_show")
    async with controller.collect(count=1) as response:
        await controller.send_command("url_show")
    assert "jw.org" in response.messages[0].text
    print("Url selected")

    print("Sending /url_delete")
    async with controller.collect(count=1) as response:
        await controller.send_command("url_delete")
    assert "eliminada" in response.messages[0].text
    print("URL deleted")

    print("Upload document")
    async with controller.collect(count=1) as response:
        await controller.send_document(str(Path(__file__).parent.resolve()) + os.sep + "test.jwlibrary")
    assert "correctamente" in response.messages[0].text
    print("Document uploaded")

    print("Describe document")
    async with controller.collect(count=1) as response:
        await controller.send_command("backup_describe")
    assert "15" in response.messages[0].text
    print("Document described")

    print("Delete document")
    async with controller.collect(count=1) as response:
        await controller.send_command("backup_delete")
    assert "eliminado" in response.messages[0].text
    print("Document described")

    print("Show questions")
    async with controller.collect(count=1) as response:
        await controller.send_command("q_show")
    assert "1." in response.messages[0].text
    print("Questions shown") 

    print("Delete questions")
    async with controller.collect(count=1) as response:
        await controller.send_command("q_delete")
    assert "eliminadas" in response.messages[0].text
    print("Questions deleted") 

    print("Insert all questions at once")
    async with controller.collect(count=2) as response:
        await controller.send_command("q_set_all", args=["a\nNo respondas a ninguna pregunta"])
    assert "guardada" in response.messages[1].text
    print("All question(s) saved") 

    print("Insert question 1")
    async with controller.collect(count=1) as response:
        await controller.send_command("q1", args=["No respondas a ninguna pregunta a partir de ahora"])
    assert "guardada" in response.messages[0].text
    print("Question 1 saved") 

    print("Provoke error when inserting q10")
    async with controller.collect(count=1) as response:
        await controller.send_command("q10", args=["a"])
    assert "Rellene" in response.messages[0].text
    print("Question 10 correctly not saved") 

    print("Prepare watchtower")
    async with controller.collect(count=9, max_wait=600) as response:
        await controller.send_command("w_prepare")
    assert "Inicializando" in response.messages[0].text
    assert "Testeando" in response.messages[1].text
    assert "URL guardada" in response.messages[2].text
    assert "ChatGPT" in response.messages[3].text
    assert "JW Library" in response.messages[4].text
    assert response.messages[5].document.file_name.endswith(".jwlibrary")
    assert "PDF" in response.messages[6].text
    assert response.messages[7].document.file_name.endswith(".docx")
    assert response.messages[8].document.file_name.endswith(".pdf")
    print("File prepared")

    print("Provoke error when sending text without commands")
    async with controller.collect(count=1) as response:
        await controller.send_message("a")
    assert "bot" in response.messages[0].text
    print("Error correctly provoked") 

    print("Provoke error when sending a non-existent command")
    async with controller.collect(count=1) as response:
        await controller.send_command("abcde")
    assert "comando" in response.messages[0].text
    print("Error correctly provoked") 

    print("Send a broadcast to every user that interacted with the dev bot")
    async with controller.collect(count=1) as response:
        await controller.send_command("admin_broadcast_msg", args=["Test finished!"])
    assert "finished" in response.messages[0].text
    print("Success!")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(run_test(create_client()))