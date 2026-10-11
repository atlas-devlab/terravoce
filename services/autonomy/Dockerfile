FROM python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641
WORKDIR /agent
COPY services/autonomy/requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
COPY services/autonomy/.runtime/agent /agent
RUN aea -s fingerprint skill terravoce/oracle_abci:0.1.0
CMD ["sh", "-c", "aea issue-certificates >/dev/null && exec aea run --connections valory/abci:0.1.0,valory/http_client:0.23.0"]
