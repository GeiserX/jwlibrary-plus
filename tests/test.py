import asyncio
from pathlib import Path

from decouple import config
from pyrogram import Client

from tgintegration import BotController
from tgintegration import Response

SESSION_NAME: str = "jwlibrary_plus_testing"

def create_client(session_name: str = SESSION_NAME) -> Client:
    return Client(
        session_name=session_name,

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

    print("Clearing chat to start with a blank screen...")
    await controller.clear_chat()

    print("Sending /start and waiting for exactly 3 messages...")
    async with controller.collect(count=1) as response:  # type: Response
        await controller.send_command("start")

    # assert response.num_messages == 1
    # print("Three messages received, bundled as a `Response`.")
    assert "https://github.com/GeiserX/jwlibrary-plus" in response.messages[0].text
    print("First message contains the link to the bot's source code.")



    # print("Let's examine the buttons in the response...")
    # inline_keyboard = response.inline_keyboards[0]
    # assert len(inline_keyboard.rows[0]) == 3
    # print("Yep, there are three buttons in the first row.")

    # # We can also press the inline keyboard buttons, in this case based on a pattern:
    # print("Clicking the button matching the regex r'.*Examples'")
    # examples = await inline_keyboard.click(pattern=r".*Examples")

    # assert "Examples for contributing to the BotList" in examples.full_text
    # # As the bot edits the message, `.click()` automatically listens for "message edited"
    # # updates and returns the new state as `Response`.

    # print("So what happens when we send an invalid query or the peer fails to respond?")
    # from tgintegration import InvalidResponseError

    # try:
    #     # The following instruction will raise an `InvalidResponseError` after
    #     # `controller.max_wait` seconds. This is because we passed `raise_no_response=True`
    #     # during controller initialization.
    #     print("Expecting unhandled command to raise InvalidResponseError...")
    #     async with controller.collect():
    #         await controller.send_command("ayylmao")
    # except InvalidResponseError:
    #     print("Ok, raised as expected.")

    # # If `raise_` is explicitly set to False, no exception is raised
    # async with controller.collect(raise_=False) as response:  # type: Response
    #     print("Sending a message but expecting no reply...")
    #     await client.send_message(controller.peer_id, "Henlo Fren")

    # # In this case, tgintegration will simply emit a warning, but you can still assert
    # # that no response has been received by using the `is_empty` property.
    # assert response.is_empty

    print("Success!")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(run_test(create_client()))