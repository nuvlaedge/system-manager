FROM python:3-alpine AS psutil-builder

RUN apk add --no-cache linux-headers=4.18.13-r1 musl-dev=1.1.20-r4 gcc=8.3.0-r0

WORKDIR /usr/local/lib/python3.7/site-packages

COPY code/requirements.txt .
RUN pip install -r requirements.txt

# ---

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

COPY --from=psutil-builder /usr/local/lib/python3.7/site-packages/psutil /usr/local/lib/python3.7/site-packages/psutil
COPY --from=psutil-builder /usr/local/lib/python3.7/site-packages/psutil-5.6.2.dist-info /usr/local/lib/python3.7/site-packages/psutil-5.6.2.dist-info

COPY code/ /opt/nuvlabox/

WORKDIR /opt/nuvlabox/

RUN apk add --no-cache curl==7.64.0-r1 && pip install -r requirements.txt

VOLUME /srv/nuvlabox/shared

ENTRYPOINT ["./app.py"]