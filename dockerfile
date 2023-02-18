FROM seleniarm/standalone-chromium:110.0 as base

# Setup env
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1


FROM base AS python-deps

RUN sudo apt-get update
RUN sudo apt-get -y install python3.9.12 
RUN python3.9 -m pip install pip
# Install pipenv and compilation dependencies
RUN sudo -H pip install pipenv 
# RUN apt-get update && apt-get install -y --no-install-recommends gcc

# Install python dependencies in /.venv
COPY Pipfile .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy --skip-lock


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
