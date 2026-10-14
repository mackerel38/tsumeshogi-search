FROM python:3.11-slim
WORKDIR /workspace
COPY requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir -r /opt/requirements.txt
COPY research /workspace/research
COPY candidates /workspace/candidates
COPY scripts /workspace/scripts
ENTRYPOINT ["python", "scripts/run_search.py"]
