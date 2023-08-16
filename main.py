import email
import imaplib
import logging
from typing import Dict, List, Union, Optional

import toml
from bs4 import BeautifulSoup
from langchain.agents import AgentType, initialize_agent
from langchain.agents.agent_toolkits import PlayWrightBrowserToolkit
from langchain.chat_models import ChatOpenAI
from langchain.tools.playwright.utils import create_sync_playwright_browser
from pydantic import BaseModel
from tqdm import tqdm
from email.header import decode_header

"""
Email Unsubscriber App

This script connects to a user's email account, fetches the last 100 emails,
analyzes them to determine if they are unwanted (e.g., marketing, newsletters),
and provides an option to unsubscribe from them using Langchain and Playwright.
"""

model_name = "gpt-3.5-turbo"

logger = logging.getLogger(__name__)
# set log level to info
logger.setLevel(logging.INFO)

sync_browser = create_sync_playwright_browser()
toolkit = PlayWrightBrowserToolkit.from_browser(sync_browser=sync_browser)
tools = toolkit.get_tools()

llm = ChatOpenAI(temperature=0.2, model_name=model_name)

agent_chain = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
)


class Config(BaseModel):
    """
    Configuration model.
    """

    imap_server: str
    email_address: str
    password: str


class Email(BaseModel):
    """
    Email model.
    """

    subject: str
    content: str
    from_address: str


def load_config(path: str = "config.toml") -> Config:
    """
    Loads the configuration file.

    :param path: Path to the configuration file

    :return: Configuration dictionary
    """
    # load from config.toml
    toml_config = toml.load(path)
    return Config(**toml_config)


def get_content(msg: email.message.Message) -> str:
    """
    Gets the content of the email message.

    :param msg: Email message object
    :return: Email content
    """
    if msg.is_multipart():
        parts = [get_content(part) for part in msg.get_payload()]
        return "\n".join(parts)

    content_disposition = str(msg.get("Content-Disposition"))

    # Ignore attachments
    if "attachment" not in content_disposition:
        payload = msg.get_payload(
            decode=True
        )  # Automatically decodes based on Content-Transfer-Encoding
        charset = msg.get_content_charset()
        if charset:
            return payload.decode(charset)
        else:
            return (
                payload.decode()
            )  # Fallback to default encoding if charset is not provided

    return ""


def decode_field(field: str) -> str:
    decoded_header = decode_header(field)
    field_parts = [
        part.decode(encoding or "utf-8") if isinstance(part, bytes) else part
        for part, encoding in decoded_header
    ]
    return "".join(field_parts)


def connect_to_email(
    imap_server: str, email_address: str, password: str
) -> List[Email]:
    """
    Connects to the email account and fetches the last 100 emails.

    :param imap_server: IMAP server address
    :param email_address: User's email address
    :param password: User's password
    :return: List of email messages
    """
    logger.info("Connecting to email account")
    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(email_address, password)
    logger.info("Connected to email account")
    mail.select()
    typ, data = mail.search(None, "ALL")
    email_ids = data[0].split()[-100:]
    emails: List[Email] = []
    for e_id in tqdm(email_ids):
        logger.info(f"Fetching email {e_id}")
        typ, data = mail.fetch(e_id, "(RFC822)")
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        subj = msg.get("Subject")
        decoded_subj = decode_field(subj)  # Decode the subject line
        from_address = msg.get("From")
        decoded_from = decode_field(from_address)  # Decode the from address
        content = get_content(msg)
        e = Email(
            subject=decoded_subj, content=content, from_address=decoded_from
        )  # Include the from address
        emails.append(e)
    mail.logout()
    return emails


def analyze_email(email_msg: Email) -> Dict[str, Union[str, bool]]:
    """
    Analyzes the email to determine if it's unwanted.

    :param email_msg: Email message object
    :return: Result containing analysis details
    """
    if "unsubscribe" in email_msg.content.lower():
        return {"is_unwanted": True}
    return {"is_unwanted": False}


def get_unsubscribe_url(email_content: Email) -> Optional[str]:
    """
    Gets the unsubscribe URL from the email content.

    :param email_content: Email content
    :return: Unsubscribe URL
    """
    soup = BeautifulSoup(email_content.content, "html.parser")
    unsubscribe_links = []

    for a_tag in soup.find_all("a"):
        if "unsubscribe" in a_tag.text.lower() and "http" in a_tag["href"]:
            unsubscribe_links.append(a_tag["href"])

    if len(unsubscribe_links) > 0:
        return unsubscribe_links[-1]
    return None


def unsubscribe_from_email(url: str) -> None:
    """
    Unsubscribes from the email using Langchain and Playwright.

    :param email_content: Email content
    """
    result = agent_chain.run(
        "Use the tools provided to unsubscribe from the email. The URL provided here"
        " is from an unsubscribe link originating in a marketing email. Nagivating to"
        " the URL should present a page or sequence that lets you click on buttons or"
        " links, or deselect checkboxes in order to unsubscribe from all marketing"
        " emails. With the browser tools provided, read and understand the content on"
        " the page and then interact with it to unsubscribe from all marketing emails."
        f" The URL to unsubscribe: {url}"
    )
    print(result)


def interact_with_user(email_msg: Email) -> bool:
    """
    Interacts with the user to get a choice for unsubscribing.

    :param email_msg: Email message object
    :return: True if the user wants to unsubscribe, False otherwise
    """
    subject = email_msg.subject
    from_address = email_msg.from_address
    print(f"Subject: {subject}\tFrom: {from_address}")
    choice = input("Do you want to unsubscribe from this email? (y/n): ")
    return choice.lower() == "y"


def main(imap_server: str, email_address: str, password: str) -> None:
    """
    Main function to execute the app.

    :param imap_server: IMAP server address
    :param email_address: User's email address
    :param password: User's password
    """
    emails = connect_to_email(imap_server, email_address, password)

    for email_msg in emails:
        result = analyze_email(email_msg)

        if result["is_unwanted"]:
            if True:  # interact_with_user(email_msg):
                url = get_unsubscribe_url(email_msg)
                if url is not None:
                    try:
                        unsubscribe_from_email(url)
                    except Exception as e:
                        print(f"Error while unsubscribing: {e}")


if __name__ == "__main__":
    config = load_config()
    logger.info(f"Loaded config: {config}")

    main(config.imap_server, config.email_address, config.password)
