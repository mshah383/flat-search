import datetime
import logging
import os
from typing import Any, List
from flat_search.data import Property
from flat_search.data.changes import PropertyChanges

from flat_search.settings import Settings

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import ssl
import jinja2
import os


def generate_email(settings: Settings, changes: PropertyChanges, properties: List[Property]):

    template_loader = jinja2.FileSystemLoader(
        searchpath=os.path.dirname(settings.email_template))
    template_env = jinja2.Environment(loader=template_loader)
    template_file = os.path.basename(settings.email_template)
    template = template_env.get_template(template_file)

    properties_dict = {x.id: x for x in properties}

    added = [{"value": properties_dict[id], "updates": [], "added": True, "removed": False}
             for id in changes.appended]

    removed = [{"value": properties_dict[id], "updates": [], "removed": True, "removed": False}
               for id in changes.removed]

    updated = [{"value": properties_dict[id], "updates": changes, "added": False, "removed2": False}
               for id, changes in changes.modified.items()]
    return template.render(properties=[*added, *removed, *updated], date=datetime.datetime.now())


def send_property_updates_email(settings: Settings, changes: PropertyChanges,  properties: List[Property]):
    """ sends the diff from the last scrape to the defined userbase """

    logging.info("Sending change emails")

    smtp_server = "smtp.gmail.com"  # for Gmail
    port = 587  # For starttls

    login = os.getenv("SMTP_LOGIN")
    password = os.getenv("SMTP_PASSWORD")
    msg = MIMEMultipart()
    msg["Subject"] = f"New property updates for {datetime.datetime.now().strftime('%A, %B')}"
    msg["From"] = login
    msg['To'] = ", ".join(settings.email_recipients)

    body_html = MIMEText(generate_email(settings, changes, properties), 'html')
    msg.attach(body_html)  # attaching to msg

    context = ssl.create_default_context()
    # Try to log in to server and send email
    try:
        server = smtplib.SMTP(smtp_server, port)
        server.ehlo()  # check connection
        server.starttls(context=context)  # Secure the connection
        server.ehlo()  # check connection
        server.login(login, password)

        # Send email here
        server.sendmail(login, settings.email_recipients, msg.as_string())

    except Exception as e:
        # Print any error messages
        logging.exception("Exception in sending email")
    finally:
        server.quit()
