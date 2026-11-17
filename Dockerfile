FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYENV_ROOT="/root/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
ENV GRASSBIN=/usr/bin/grass

RUN apt-get update && apt-get install -y --no-install-recommends \
    make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
    libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev \
    libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev git \
    software-properties-common python3-pip python3-dev python3-opencv \
    libgdal-dev gdal-bin nodejs npm grass grass-core grass-dev ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN curl https://pyenv.run | bash && \
    pyenv install 3.13.7 && \
    pyenv global 3.13.7

WORKDIR /app
RUN mkdir -m 777 logs tmp

# Instala o debugpy para o VSCode conseguir "atracar" no processo
RUN pip install --upgrade pip setuptools debugpy

COPY . .

# Porta do Flask e porta do Debugger
EXPOSE 5000 5678

# Comando para rodar com debugpy habilitado
CMD ["sleep", "infinity"]