FROM python:3.14.3-slim-bookworm

RUN rm -rf /usr/local/bin/pip* \
           /usr/local/lib/python3.14/site-packages/pip* \
           /usr/local/lib/python3.14/ensurepip \
    && groupadd --gid 65532 gamr \
    && useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin gamr \
    && mkdir -p /opt/gamr /input /workspace \
    && chown -R 65532:65532 /opt/gamr /input /workspace

COPY populate_input.py /opt/gamr/populate_input.py

ENV PYTHONNOUSERSITE=1
ENV PYTHONDONTWRITEBYTECODE=1
USER 65532:65532
WORKDIR /workspace

