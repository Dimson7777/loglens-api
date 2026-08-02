FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV APP_HOME=/app
ENV APP_USER=loglens
ENV APP_UID=10001
ENV APP_GID=10001

WORKDIR ${APP_HOME}

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid ${APP_GID} ${APP_USER} \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --home-dir /home/${APP_USER} --shell /usr/sbin/nologin ${APP_USER}

COPY --chown=${APP_UID}:${APP_GID} . .

RUN pip install --upgrade pip \
    && pip install .

RUN chown -R ${APP_UID}:${APP_GID} ${APP_HOME} /home/${APP_USER} \
    && chmod 750 ${APP_HOME} \
    && chmod 700 /home/${APP_USER}

USER ${APP_UID}:${APP_GID}

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
