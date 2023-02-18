# Property Hunter

This app will pull in data based on a query from configured property sources, keep track of it and email you the changes.

## Set up

create a .env file with the following variables:
``` bash
ZA_URL_FORMAT="<property endpoint>/{area}/?search_source=home&price_frequency=per_month&q={location_query}&price_min={price_min}&price_max={price_max}&pn={page_no}"
SMTP_LOGIN="<gmail login>"
SMTP_PASSWORD="<gmail app password, or account password>"
ENV="<DEV/PROD>"
```
Reccomended way to setup gmail is to register an app like so: https://levelup.gitconnected.com/an-alternative-way-to-send-emails-in-python-5630a7efbe84

customize `settings-<ENV>.json` files to suit your environments, it's reccomended you setup a mocking server with `src/mock.py` for development and make sure to enable proxies in your production environment.

in development, use:
`firefox -marionette --start-debugger-server 2828` to see what the bot is doing.

## Requirements
- firefox (NOT THE SNAP STORE VERSION)
- geckodriver 
