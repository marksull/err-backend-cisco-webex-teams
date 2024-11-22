FROM errbotio/errbot:latest

LABEL maintainer="mark@sullivans.id.au"

USER root

RUN apt-get update && apt-get install -y --no-install-recommends git

RUN git clone https://github.com/marksull/err-backend-cisco-webex-teams.git backends/err-backend-cisco-webex-teams

WORKDIR backends/err-backend-cisco-webex-teams

RUN pip install -r requirements.txt

COPY CiscoWebexTeams.config.py config.py

USER errbot
