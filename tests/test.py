import asyncio
from pathlib import Path

from decouple import config
from pyrogram import Client

import time
import os

from dotenv import load_dotenv

from tgintegration import BotController
from tgintegration import Response

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
        peer="@jwlibrary_plus_dev_bot", 
        client=client,
        max_wait=5,  # Maximum timeout for responses (optional)
        wait_consecutive=5,  # Minimum time to wait for more/consecutive messages (optional)
        raise_no_response=True,  # Raise `InvalidResponseError` when no response received (defaults to True)
        global_action_delay=2.5,  # Choosing a rather high delay so we can follow along in realtime (optional)
    )

    print("Clearing chat to start with a blank screen")
    await controller.clear_chat()

    #Initialize DB - TODO

    print("Sending /start")
    async with controller.collect(count=1) as response:
        await controller.send_command("start")
    assert "https://github.com/GeiserX/jwlibrary-plus" in response.messages[0].text
    print("First message contains the link to the bot's source code")

    # print("Sending /date_select")
    # async with controller.collect(count=1) as response:
    #     await controller.send_command("date_select")
    # inline_keyboard = response.inline_keyboards[0]
    # assert len(inline_keyboard.rows) == 4
    # print("Dates shown")

    # print("Clicking the first option")
    # async with controller.collect(count=1) as response:
    #     await inline_keyboard.click(index=0)
    # assert "0" in response.messages[0].text
    # print("Selected the first option")

    # print("Sending /date_show")
    # async with controller.collect(count=1) as response:
    #     await controller.send_command("date_show")
    # assert "0" in response.messages[0].text
    # print("Date shown")

    # print("Sending /date_delete")
    # async with controller.collect(count=1) as response:
    #     await controller.send_command("date_delete")
    # assert "eliminada" in response.messages[0].text
    # print("Date deleted")

    # async with controller.collect(count=1) as response: 
    #     await controller.send_command("date_select")
    # inline_keyboard = response.inline_keyboards[0]
    # await inline_keyboard.click(index=0)
    
    # print("Sending /url_select")
    # async with controller.collect(count=2) as response:
    #     await controller.send_command("url_select", args=["https://www.jw.org/es/biblioteca/revistas/atalaya-estudio-julio-2023/Seamos-razonables-como-Jehov%C3%A1/"])
    # assert "32" in response.messages[1].text
    # print("Url selected")   

    # print("Sending /url_show")
    # async with controller.collect(count=1) as response:
    #     await controller.send_command("url_show")
    # assert "jw.org" in response.messages[0].text
    # print("Url selected")

    # print("Sending /url_delete")
    # async with controller.collect(count=1) as response:
    #     await controller.send_command("url_delete")
    # assert "eliminada" in response.messages[0].text
    # print("URL deleted")

    # print("Upload document")
    # async with controller.collect(count=1) as response:
    #     await controller.send_document(str(Path(__file__).parent.resolve()) + os.sep + "test.jwlibrary")
    # assert "correctamente" in response.messages[0].text
    # print("Document uploaded")

    # print("Describe document")
    # async with controller.collect(count=1) as response:
    #     await controller.send_command("backup_describe")
    # assert "15" in response.messages[0].text
    # print("Document described")

    # print("Delete document")
    # async with controller.collect(count=1) as response:
    #     await controller.send_command("backup_delete")
    # assert "eliminado" in response.messages[0].text
    # print("Document described")



    print("Success!")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(run_test(create_client()))