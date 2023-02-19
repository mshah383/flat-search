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
RUN . /.venv/bin/activate && \
   pip install pipenv && \
   PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy --skip-lock



FROM base AS runtime
ARG TARGETPLATFORM

# Copy virtual env from python-deps stage
COPY --from=python-deps /.venv /.venv
ENV PATH="/.venv/bin:$PATH"
VOLUME /app/data
WORKDIR /app
# Install application into container
COPY . .

# Run the application
CMD python3 /app/src/backend.py
