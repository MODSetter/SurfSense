FROM opensandbox/code-interpreter:v1.1.0

SHELL ["/bin/bash", "-c"]

USER root

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
        fonts-liberation \
        fonts-noto-cjk \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libreoffice \
        pandoc \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# The entrypoint activates the interpreter named by PYTHON_VERSION and binds the
# Jupyter kernel to it. The base default is 3.14, which lacks wheels for parts of
# the stack below; pin 3.12 so the kernel is the interpreter carrying them.
ENV PYTHON_VERSION=3.12

# code-interpreter-env.sh only mutates the calling shell, so it must be sourced
# in the same layer as the install. Unqualified pip would otherwise land in the
# unrelated Ubuntu /usr/bin/python3.12 that the kernel never sees.
RUN set -euo pipefail \
    && . /opt/code-interpreter/code-interpreter-env.sh python "${PYTHON_VERSION}" \
    && python3 -m pip install --no-cache-dir --break-system-packages \
        matplotlib \
        openpyxl \
        pandas \
        pypdf \
        python-docx \
        python-pptx \
        reportlab \
        weasyprint \
        xlsxwriter \
    && python3 -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version; assert sys.prefix.startswith('/opt/python/versions'), sys.prefix" \
    && python3 -c "import docx, matplotlib, openpyxl, pandas, pypdf, pptx, reportlab, weasyprint, xlsxwriter"

# A global npm install is not on node's resolution path from /workspace, so pin
# the prefix and point NODE_PATH at it to make require('docx') work anywhere.
ENV NPM_CONFIG_PREFIX=/opt/node-global \
    NODE_PATH=/opt/node-global/lib/node_modules

RUN set -euo pipefail \
    && npm install --global docx \
    && node -e "require('docx')"

# The base image also ships skills. Replace the formats SurfSense owns in one
# layer so OverlayFS records removed base-image files as deletions.
COPY skills /tmp/surfsense-skills
RUN set -euo pipefail \
    && mkdir -p /opt/skills \
    && for skill in /tmp/surfsense-skills/*; do \
        name="${skill##*/}"; \
        rm -rf "/opt/skills/${name}"; \
        cp -a "${skill}" "/opt/skills/${name}"; \
        rm -rf "/opt/skills/${name}/scripts"; \
    done \
    && rm -rf /tmp/surfsense-skills

ENTRYPOINT ["/opt/code-interpreter/code-interpreter.sh"]
