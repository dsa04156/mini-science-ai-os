FROM python:3.12.3-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --gid 10001 science && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin science
WORKDIR /opt/science-ai
COPY requirements.txt /opt/science-ai/requirements.txt
RUN python -m pip install --no-cache-dir --requirement /opt/science-ai/requirements.txt
COPY services /opt/science-ai/services
RUN chown -R 10001:10001 /opt/science-ai
USER 10001:10001

ENV PYTHONPATH=/opt/science-ai/services
EXPOSE 8000
ENTRYPOINT ["python"]

