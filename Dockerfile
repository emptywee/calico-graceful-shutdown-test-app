FROM python:3.8-slim-buster AS production
ARG APP_NAME=calico-test
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get -yu upgrade && \
    apt-get -y install git && \
    apt-get clean && \
    rm -rf /var/cache/apt/* /var/lib/apt/lists/*

WORKDIR /opt/app/${APP_NAME}/
COPY boot.sh /opt/app/${APP_NAME}/
COPY calico-test.py /opt/app/${APP_NAME}/
RUN adduser --no-create-home --uid 1002 ${APP_NAME}

USER ${APP_NAME}

EXPOSE 8080
ENTRYPOINT ["./boot.sh"]
