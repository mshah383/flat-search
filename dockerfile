FROM seleniarm/standalone-chromium:110.0 as base

# Setup env
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1


FROM base AS python-deps

RUN sudo apt-get update && sudo apt-get install libssl-dev openssl build-essential zlib1g-dev -y
RUN sudo wget https://www.python.org/ftp/python/3.9.12/Python-3.9.12.tgz  && \
   sudo tar xzvf Python-3.9.12.tgz
RUN cd Python-3.9.12 && \
   sudo ./configure --prefix /app_python && \
   sudo make && \
   sudo make install

RUN sudo mkdir /.venv && sudo chmod 777 /app_python /.venv 
RUN /app_python/bin/python3 -m venv /.venv
COPY Pipfile .

# Install python dependencies in /.venv
RUN  . /.venv/bin/activate && pip3 install setuptools pipenv
RUN . /.venv/bin/activate && python3 -m pipenv install --deploy --skip-lock



FROM base AS runtime

# Copy virtual env from python-deps stage
COPY --from=python-deps /.venv /.venv
COPY --from=python-deps /app_python /app_python
VOLUME /app/data
VOLUME /app/logs
WORKDIR /app
# Install application into container
COPY . .

# Run the application
CMD /.venv/bin/python /app/src/backend.py
