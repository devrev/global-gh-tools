#!/bin/sh -xe
export AWS_ENDPOINT_URL=http://localhost:8000
export AWS_ACCESS_KEY_ID=dummy
export AWS_SECRET_ACCESS_KEY=dummy
export AWS_SESSION_TOKEN=dummy
venv/bin/python checks/check_patching_sla.py changed_files.txt devrev/alchemy comment.txt