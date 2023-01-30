# Property Hunter

This app will pull in data based on a query from configured property sources, keep track of it and email you the changes.

# Set up

create a .env file with the following variables:
``` bash
ZA_URL_FORMAT="<property endpoint>/{area}/?search_source=home&price_frequency=per_month&q={location_query}&price_min={price_min}&price_max={price_max}&pn={page_no}"
SMTP_LOGIN="<gmail login>"
SMTP_PASSWORD="<gmail app password, or account password>"
```
Reccomended way to setup gmail is to register an app like so: https://levelup.gitconnected.com/an-alternative-way-to-send-emails-in-python-5630a7efbe84