FROM python:3-alpine

ARG GIT_BRANCH
ARG GIT_COMMIT_ID
ARG GIT_DIRTY
ARG GIT_BUILD_TIME
ARG TRAVIS_BUILD_NUMBER
ARG TRAVIS_BUILD_WEB_URL

LABEL git.branch=${GIT_BRANCH}
LABEL git.commit.id=${GIT_COMMIT_ID}
LABEL git.dirty=${GIT_DIRTY}
LABEL git.build.time=${GIT_BUILD_TIME}
LABEL travis.build.number=${TRAVIS_BUILD_NUMBER}
LABEL travis.build.web.url=${TRAVIS_BUILD_WEB_URL}

RUN apk add --no-cache linux-headers=4.18.13-r1 musl-dev=1.1.20-r4 gcc=8.3.0-r0

COPY code/ /opt/nuvlabox/

WORKDIR /opt/nuvlabox/

RUN pip install -r requirements.txt

VOLUME /srv/nuvlabox/shared

ENTRYPOINT ["./app.py"]