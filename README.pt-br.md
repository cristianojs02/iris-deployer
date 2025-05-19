[English](/README.md)

# Deploy de Código-Fonte para InterSystems IRIS via GitHub Actions

[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
<!--![GitHub Actions Status](https://github.com/YOUR_GITHUB_USERNAME/YOUR_GITHUB_REPOSITORY/actions/workflows/YOUR_WORKFLOW_FILE.yml/badge.svg)-->

Este projeto consiste em uma GitHub Action que automatiza o deploy de arquivos de código-fonte para um servidor InterSystems IRIS. Ele utiliza a API REST de gerenciamento de código-fonte do IRIS para criar, atualizar, compilar e deletar documentos.

## Conteúdo

* [Dockerfile](#dockerfile)
* [Classe Python `IrisDeployer`](#classe-python-irisdeployer)
* [GitHub Action `Deploy To IRIS`](#github-action-deploy-to-iris)
* [Como Configurar e Usar](#como-configurar-e-usar)
    * [Pré-requisitos](#pré-requisitos)
    * [Configuração da GitHub Action](#configuração-da-github-action)
    * [Exemplo de Workflow](#exemplo-de-workflow)
* [Contribuição](#contribuição)
* [Licença](#licença)

## Dockerfile

O arquivo `Dockerfile` define o ambiente do container Docker que executará a GitHub Action. Ele é construído em duas etapas para otimizar o tamanho da imagem final.

**Etapa 1: `builder`**

```dockerfile
FROM python:3.12.3-slim-bookworm AS builder
ADD . /app
WORKDIR /app

# Instala a biblioteca 'requests' diretamente no diretório da aplicação
RUN pip install --target=/app requests
```

* `FROM python:3.12.3-slim-bookworm AS builder`: Define a imagem base para a construção como uma versão slim do Python 3.12 baseada no Debian Bookworm. Esta etapa é nomeada como `builder`.
* `ADD . /app`: Copia todo o conteúdo do diretório do projeto para o diretório `/app` dentro do container.
* `WORKDIR /app`: Define o diretório de trabalho para os próximos comandos como `/app`.
* `RUN pip install --target=/app requests`: Instala a biblioteca `requests`, que é utilizada pela classe Python para fazer chamadas HTTP para a API do IRIS. O parâmetro `--target=/app` garante que a biblioteca seja instalada dentro do diretório `/app`.

**Etapa 2: Imagem final**

```dockerfile
FROM gcr.io/distroless/python3-debian12
COPY --from=builder /app /app
WORKDIR /app
ENV PYTHONPATH=/app
CMD ["/app/iris_deployer.py"]
```

* `FROM gcr.io/distroless/python3-debian12`: Utiliza uma imagem "distroless" do Google Container Tools com Python 3. Esta imagem é minimalista, contendo apenas as dependências necessárias para executar aplicações Python, incluindo certificados SSL. Isso resulta em uma imagem final menor e mais segura.
* `COPY --from=builder /app /app`: Copia o conteúdo do diretório `/app` da etapa de construção (`builder`) para o diretório `/app` da imagem final. Isso inclui o código da sua aplicação e a biblioteca `requests` instalada.
* `WORKDIR /app`: Define o diretório de trabalho para os próximos comandos como `/app`.
* `ENV PYTHONPATH=/app`: Define a variável de ambiente `PYTHONPATH` para que o Python possa encontrar os módulos dentro do diretório `/app`.
* `CMD ["/app/iris_deployer.py"]`: Define o comando principal a ser executado quando o container for iniciado. Neste caso, ele executa o script Python `iris_deployer.py`.

## Classe Python `IrisDeployer`

A classe `IrisDeployer` (`iris_deployer.py`) é responsável por interagir com a API REST do InterSystems IRIS para realizar as operações de deploy.

**Funcionalidades:**

* **Inicialização (`__init__`)**:
    * Configura o logging básico.
    * Armazena as informações de conexão com o servidor IRIS (host, porta, namespace), protocolo (HTTP/HTTPS), URL base da API, versão da API, credenciais de usuário e senha do IRIS, flags de compilação padrão e o caminho da pasta de origem dos arquivos.
    * Constrói as URLs para as diferentes operações da API REST (enviar documento, deletar documentos, obter documento e compilar documentos).
    * Cria uma sessão `requests` com os headers `Content-Type: application/json`, `Accept: */*` e autenticação básica HTTP.

* **`compile_docs(self, doc_list: str)`**:
    * Recebe uma string JSON contendo uma lista de arquivos a serem compilados.
    * Faz uma requisição `POST` para a URL de compilação do IRIS, passando a lista de arquivos e as flags de compilação.
    * Processa a resposta da API, exibindo mensagens de log de sucesso, aviso ou erro com base no código de status HTTP e no conteúdo da resposta (console de saída do compilador do IRIS).
    * Define a flag interna `__has_error` como `True` em caso de erros na compilação ou na requisição.

* **`delete_docs(self, doc_list: str)`**:
    * Recebe uma string JSON contendo uma lista de arquivos a serem deletados.
    * Faz uma requisição `DELETE` para a URL de exclusão de documentos do IRIS, enviando a lista de arquivos no corpo da requisição.
    * Processa a resposta da API, exibindo mensagens de log de sucesso ou erro com base no código de status HTTP e no conteúdo da resposta.

* **`deploy_docs(self, changed_files: list)`**:
    * Recebe uma lista de arquivos que foram modificados ou criados.
    * Itera sobre cada arquivo na lista:
        * Constrói o nome do documento para o IRIS, removendo o `source_path` e substituindo barras (`/`) por pontos (`.`).
        * Verifica se o documento já existe no IRIS usando o método `get_doc()`.
        * Se o documento existir, obtém o timestamp da última modificação (`ts`) e define o header `If-None-Match` na sessão `requests` para evitar erros de conflito durante a atualização, caso o documento não tenha sido alterado no servidor.
        * Lê o conteúdo do arquivo local.
        * Formata o conteúdo em um dicionário JSON (`{'enc': False, 'content': [...]}`).
        * Envia o documento para o IRIS usando o método `put_doc()`.
    * Após enviar todos os documentos individualmente, constrói uma lista JSON de todos os arquivos alterados (com o formato de nome de documento do IRIS) e chama o método `compile_docs()` para compilar todos os arquivos de uma vez.

* **`get_doc(self, file_name: str)`**:
    * Recebe o nome do arquivo (formato de documento do IRIS).
    * Faz uma requisição `GET` para a URL de obtenção de um documento específico.
    * Processa a resposta da API. Observa-se que a API pode retornar status 409 (Conflict) mesmo para documentos existentes, o que é tratado para evitar falsos erros.
    * Retorna o conteúdo da resposta JSON em caso de sucesso (status 200) ou `None` se o documento não for encontrado (status 404). Em caso de outros erros, define a flag `__has_error`.

* **`put_doc(self, source_document: str, file_name: str)`**:
    * Recebe o conteúdo do documento e o nome do arquivo (formato de documento do IRIS).
    * Faz uma requisição `PUT` para a URL de envio de um documento específico, enviando o conteúdo JSON no corpo da requisição.
    * Processa a resposta da API, exibindo mensagens de log para diferentes códigos de status (sucesso, aviso de conflito/bloqueio, erro).
    * Define a flag `__has_error` em caso de erros na requisição.

* **`exit(self)`**:
    * Verifica o valor da flag `__has_error`. Se `True`, encerra o script com código de saída 1 (indicando erro). Caso contrário, encerra com código de saída 0 (sucesso).

* **`in_debug_mode()`**:
    * Função utilitária para verificar se o script Python está sendo executado em modo de debug.

* **`if __name__ == '__main__':`**:
    * Bloco principal de execução do script.
    * Se não estiver em modo de debug (executando como GitHub Action):
        * Cria uma instância da classe `IrisDeployer` lendo as configurações do servidor IRIS e as informações de arquivos alterados/deletados das variáveis de ambiente (`INPUT_*`).
        * Chama o método `deploy_docs()` para enviar os arquivos alterados.
        * Chama o método `delete_docs()` para remover os arquivos deletados.
        * Chama o método `exit()` para finalizar a execução com o código de saída apropriado.
    * Se estiver em modo de debug (executando localmente):
        * Define valores de exemplo para as configurações e lista de arquivos para teste local.
        * Cria uma instância de `IrisDeployer` e chama os métodos `deploy_docs()` e `delete_docs()` com os dados de teste.

## GitHub Action `Deploy To IRIS`

O arquivo YAML define a GitHub Action chamada "Deploy To IRIS", que automatiza o processo de deploy para o InterSystems IRIS.

```yaml
name: Deploy To IRIS
description: Send created, modified and deleted files to IRIS. Compile and return result of compilation.
inputs:
  host:
    description: Host name or IP address of the WebServer that communicates with the IRIS server.
    required: true
  port:
    description: Port number of the WebServer that communicates with IRIS.
    required: true
    default: "52773"
  namespace_iris:
    description: Name of IRIS namespace to deploy to.
    required: true
  https:
    description: Flag indicating the use of HTTPS by the WebServer. 1-true, 0-false
    required: true
    default: "0"
  base_api_url:
    description: The base URL to the IRIS Source Code File REST API.
    required: true
    default: "/api/atelier/"
  version_api:
    description: The version of the IRIS Source Code File REST API.
    required: true
    default: "v2"
  compilation_flags:
    description: Flags used by the IRIS compiler. See the IRIS documentation for details.
    required: true
    default: "cukb"
  source_path:
    description: The source root path. Needs to be extracted from the source file name.
    required: true
    default: "src/"
  iris_usr:
    description: Iris user name.
    required: true
  iris_pwd:
    description: Iris user password.
    required: true
  changed_files:
    description: Comma-delimited string with a list of changed files to deploy.
    required: true
  deleted_files:
    description: Comma-delimited string with a list of deleted files to remove from the server.
    required: true
runs:
  using: 'docker'
  image: "Dockerfile"
```

**Detalhes dos Inputs:**

A seção `inputs` define os parâmetros que podem ser configurados ao usar esta GitHub Action em um workflow. Cada input possui uma `description`, indica se é `required` e pode ter um `default` value.

* `host`: Nome do host ou endereço IP do servidor Web que se comunica com o servidor IRIS.
* `port`: Número da porta do servidor Web. O padrão é `52773`.
* `namespace_iris`: Nome do namespace IRIS para o qual os arquivos serão deployados.
* `https`: Flag indicando se o servidor Web utiliza HTTPS (1 para true, 0 para false). O padrão é `0` (HTTP).
* `base_api_url`: URL base da API REST de gerenciamento de código-fonte do IRIS. O padrão é `/api/atelier/`.
* `version_api`: Versão da API REST do IRIS. O padrão é `v2`.
* `compilation_flags`: Flags utilizadas pelo compilador IRIS. Consulte a documentação do IRIS para mais detalhes. O padrão é `cukb`.
* `source_path`: Caminho da pasta raiz dos arquivos de código-fonte no seu repositório. Este caminho será removido dos nomes dos documentos ao serem enviados para o IRIS. O padrão é `src/`.
* `iris_usr`: Nome de usuário do IRIS com permissões para acessar a API REST.
* `iris_pwd`: Senha do usuário IRIS.
* `changed_files`: Uma string delimitada por vírgulas contendo a lista de arquivos modificados ou criados que devem ser deployados.
* `deleted_files`: Uma string delimitada por vírgulas contendo a lista de arquivos que foram deletados e devem ser removidos do servidor IRIS.

**Seção `runs`:**

* `using: 'docker'`: Indica que esta Action será executada dentro de um container Docker.
* `image: "Dockerfile"`: Especifica que a imagem Docker a ser utilizada será construída a partir do `Dockerfile` presente no mesmo repositório da Action.

## Como Configurar e Usar

Para utilizar esta GitHub Action no seu projeto, siga os passos abaixo:

### Pré-requisitos

* Um servidor InterSystems IRIS com a API REST de gerenciamento de código-fonte configurada e acessível através de um servidor Web.
* Credenciais de um usuário do IRIS com permissões para interagir com a API REST (criar, atualizar, compilar e deletar documentos).
* Seu código-fonte organizado em um repositório GitHub.

### Configuração da GitHub Action

1.  Crie um arquivo YAML dentro do diretório `.github/workflows` no seu repositório (por exemplo, `.github/workflows/deploy_iris.yml`).

2.  Cole o seguinte conteúdo no arquivo, adaptando-o às suas necessidades:

```yaml
# Template of a workflow to create, upate, delete and compile source documents on IRIS
name: Deploy to IRIS
# Trigger execute action
on:
  push:
    # All push to these branchs trigger the action Deploy to IRIS 
    branches:
      - <put you branch>
   # All puspull_requesth to these branchs trigger the action Deploy to IRIS
  pull_request:
    branches:
      - <put you branch>
#  Allow manually worflow execution
#  workflow_dispatch:

jobs:
  deploy-to-iris:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Get changed files and write the outputs to a JSON file
        id: modified-files
        uses: tj-actions/changed-files@v44
        with:
          separator: ","
          files: |
              **/*.{cls,mac,int,inc}
      - name: Depoly to IRIS
        uses: cristianojs02/iris-deployer@main
        with:
          host: '<IP or Host Name>'
          port: '<Port Number>'
          namespace_iris: '<CODENAMESPACE>'
          # 0 - HTTP, 1 - HTTPS 
          https: '0'
          base_api_url: '/api/atelier'
          version_api: 'v2'
          # Change if you don't want default flags compilation
          compilation_flags: 'cukb'
          # Used to extract from document name before sen to IRIS, avoiding Document Not found error.
          source_path: 'src/'
          # Use github secrets
          iris_usr: '<usr>'
          iris_pwd: '<pwd>'
          changed_files: '${{ steps.modified-files.outputs.all_changed_files }}'
          deleted_files: '${{ steps.modified-files.outputs.deleted_files }}'
```

3.  **Importante:** Armazene as informações sensíveis (host, porta, namespace, usuário, senha, etc.) como [Secrets do GitHub](https://docs.github.com/pt/actions/security-secrets#creating-e-gerenciando-segredos-criptografados). Substitua os valores diretamente no arquivo YAML por referências aos seus secrets (ex: `${{ secrets.IRIS_USER }}`).

4.  Adapte o `source_path` no passo `Deploy para IRIS` para corresponder à estrutura do seu projeto.

### Exemplo de Workflow

O exemplo de workflow acima será executado sempre que houver um `push` na branch `main`. Ele realiza os seguintes passos:

1.  **Checkout do código:** Faz o download do código do seu repositório para o runner da GitHub Actions.
2.  **Identificar arquivos alterados e deletados:** ${{ steps.modified-files.outputs.all_changed_files }} e arquivos que foram deletados ${{ steps.modified-files.outputs.deleted_files }}
3.  **Deploy to IRIS:** Usa sua ação personalizada "Implantar no IRIS", passando as entradas necessárias usando os segredos do GitHub e a saída da etapa anterior.

## Contribuição

Contribuições são bem-vindas! Sinta-se à vontade para enviar pull requests ou abrir issues para sugerir melhorias ou relatar bugs.

## Licença

Este projeto está licenciado sob a [MIT License](LICENSE).
