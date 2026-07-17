FROM ghcr.io/home-assistant/base-python:3.13-alpine3.21

ARG BUILD_ARCH
ARG BUILD_VERSION

LABEL \
  io.hass.name="Knaus Copilot" \
  io.hass.description="Assistente AI personale per la caravan" \
  io.hass.arch="aarch64|amd64|armv7" \
  io.hass.type="app" \
  io.hass.version="${BUILD_VERSION}"

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
