[Português Brasil](/README.pt-br.md)

# Source Code Deployment to InterSystems IRIS via GitHub Actions

[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
<!--![GitHub Actions Status](https://github.com/YOUR_GITHUB_USERNAME/YOUR_GITHUB_REPOSITORY/actions/workflows/YOUR_WORKFLOW_FILE.yml/badge.svg)!-->

This project consists of a GitHub Action that automates the deployment of source code files to an InterSystems IRIS server. It utilizes the IRIS source code management REST API to create, update, compile, and delete documents.

## Contents

* [Dockerfile](#dockerfile)
* [Python Class `IrisDeployer`](#python-class-irisdeployer)
* [GitHub Action `Deploy To IRIS`](#github-action-deploy-to-iris)
* [How to Configure and Use](#how-to-configure-and-use)
    * [Prerequisites](#prerequisites)
    * [GitHub Action Configuration](#github-action-configuration)
    * [Workflow Example](#workflow-example)
* [Contribution](#contribution)
* [License](#license)

## Dockerfile

The `Dockerfile` defines the Docker container environment that will execute the GitHub Action. It is built in two stages to optimize the final image size.

**Stage 1: `builder`**

```dockerfile
FROM python:3.12.3-slim-bookworm AS builder
ADD . /app
WORKDIR /app

# Installs the 'requests' library directly into the application directory
RUN pip install --target=/app requests
```

* `FROM python:3.12.3-slim-bookworm AS builder`: Defines the base image for building as a slim version of Python 3.12 based on Debian Bookworm. This stage is named `builder`.
* `ADD . /app`: Copies the entire contents of the project directory to the `/app` directory inside the container.
* `WORKDIR /app`: Sets the working directory for subsequent commands to `/app`.
* `RUN pip install --target=/app requests`: Installs the `requests` library, which is used by the Python class to make HTTP calls to the IRIS API. The `--target=/app` parameter ensures that the library is installed within the `/app` directory.

**Stage 2: Final Image**

```dockerfile
FROM gcr.io/distroless/python3-debian12
COPY --from=builder /app /app
WORKDIR /app
ENV PYTHONPATH=/app
CMD ["/app/iris_deployer.py"]
```

* `FROM gcr.io/distroless/python3-debian12`: Uses a "distroless" image from Google Container Tools with Python 3. This image is minimal, containing only the necessary dependencies to run Python applications, including SSL certificates. This results in a smaller and more secure final image.
* `COPY --from=builder /app /app`: Copies the contents of the `/app` directory from the build stage (`builder`) to the `/app` directory of the final image. This includes your application code and the installed `requests` library.
* `WORKDIR /app`: Sets the working directory for subsequent commands to `/app`.
* `ENV PYTHONPATH=/app`: Sets the `PYTHONPATH` environment variable so that Python can find the modules within the `/app` directory.
* `CMD ["/app/iris_deployer.py"]`: Defines the main command to be executed when the container starts. In this case, it runs the Python script `iris_deployer.py`.

## Python Class `IrisDeployer`

The `IrisDeployer` class (`iris_deployer.py`) is responsible for interacting with the InterSystems IRIS REST API to perform deployment operations.

**Features:**

* **Initialization (`__init__`)**:
    * Configures basic logging.
    * Stores connection information to the IRIS server (host, port, namespace), protocol (HTTP/HTTPS), API base URL, API version, IRIS user credentials, default compilation flags, and the source file path.
    * Constructs the URLs for different REST API operations (put document, delete documents, get document, and compile documents).
    * Creates a `requests` session with the headers `Content-Type: application/json`, `Accept: */*`, and HTTP basic authentication.

* **`compile_docs(self, doc_list: str)`**:
    * Receives a JSON string containing a list of files to compile.
    * Makes a `POST` request to the IRIS compilation URL, passing the list of files and compilation flags.
    * Processes the API response, displaying log messages for success, warning, or error based on the HTTP status code and the response content (IRIS compiler console output).
    * Sets the internal flag `__has_error` to `True` in case of compilation or request errors.

* **`delete_docs(self, doc_list: str)`**:
    * Receives a JSON string containing a list of files to delete.
    * Makes a `DELETE` request to the IRIS delete documents URL, sending the list of files in the request body.
    * Processes the API response, displaying log messages for success or error based on the HTTP status code and the response content.

* **`deploy_docs(self, changed_files: list)`**:
    * Receives a list of files that have been modified or created.
    * Iterates over each file in the list:
        * Constructs the document name for IRIS by removing the `source_path` and replacing slashes (`/`) with periods (`.`).
        * Checks if the document already exists in IRIS using the `get_doc()` method.
        * If the document exists, it retrieves the last modification timestamp (`ts`) and sets the `If-None-Match` header in the `requests` session to avoid conflict errors during updates if the document hasn't changed on the server.
        * Reads the content of the local file.
        * Formats the content into a JSON dictionary (`{'enc': False, 'content': [...]}`).
        * Sends the document to IRIS using the `put_doc()` method.
    * After sending all individual documents, it constructs a JSON list of all changed files (with the IRIS document name format) and calls the `compile_docs()` method to compile all files at once.

* **`get_doc(self, file_name: str)`**:
    * Receives the file name (IRIS document format).
    * Makes a `GET` request to the URL for retrieving a specific document.
    * Processes the API response. It's noted that the API might return a 409 (Conflict) status even for existing documents, which is handled to avoid false errors.
    * Returns the content of the JSON response on success (status 200) or `None` if the document is not found (status 404). In case of other errors, it sets the `__has_error` flag.

* **`put_doc(self, source_document: str, file_name: str)`**:
    * Receives the document content and the file name (IRIS document format).
    * Makes a `PUT` request to the URL for sending a specific document, sending the JSON content in the request body.
    * Processes the API response, displaying log messages for different status codes (success, warning for conflict/locking, error).
    * Sets the `__has_error` flag in case of request errors.

* **`exit(self)`**:
    * Checks the value of the `__has_error` flag. If `True`, it exits the script with an exit code of 1 (indicating an error). Otherwise, it exits with an exit code of 0 (success).

* **`in_debug_mode()`**:
    * Utility function to check if the Python script is being run in debug mode.

* **`if __name__ == '__main__':`**:
    * Main execution block of the script.
    * If not in debug mode (running as a GitHub Action):
        * Creates an instance of the `IrisDeployer` class by reading the IRIS server configurations and changed/deleted file information from environment variables (`INPUT_*`).
        * Calls the `deploy_docs()` method to send the changed files.
        * Calls the `delete_docs()` method to remove the deleted files.
        * Calls the `exit()` method to finalize execution with the appropriate exit code.
    * If in debug mode (running locally):
        * Defines example values for configurations and the file list for local testing.
        * Creates an instance of `IrisDeployer` and calls the `deploy_docs()` and `delete_docs()` methods with the test data.

## GitHub Action `Deploy To IRIS`

The YAML file defines the GitHub Action named "Deploy To IRIS," which automates the deployment process to InterSystems IRIS.

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

**Input Details:**

The `inputs` section defines the parameters that can be configured when using this GitHub Action in a workflow. Each input has a `description`, indicates if it is `required`, and can have a `default` value.

* `host`: Host name or IP address of the WebServer that communicates with the IRIS server.
* `port`: Port number of the WebServer. The default is `52773`.
* `namespace_iris`: Name of the IRIS namespace to deploy to.
* `https`: Flag indicating whether the WebServer uses HTTPS (1 for true, 0 for false). The default is `0` (HTTP).
* `base_api_url`: Base URL of the IRIS Source Code File REST API. The default is `/api/atelier/`.
* `version_api`: Version of the IRIS REST API. The default is `v2`.
* `compilation_flags`: Flags used by the IRIS compiler. Refer to the IRIS documentation for more details. The default is `cukb`.
* `source_path`: Root path of the source code files in your repository. This path will be removed from the document names when sending them to IRIS. The default is `src/`.
* `iris_usr`: Username of the IRIS user with permissions to access the REST API.
* `iris_pwd`: Password of the IRIS user.
* `changed_files`: A comma-delimited string containing the list of modified or created files to be deployed.
* `deleted_files`: A comma-delimited string containing the list of files that have been deleted and should be removed from the IRIS server.

**`runs` Section:**

* `using: 'docker'`: Indicates that this Action will be executed inside a Docker container.
* `image: "Dockerfile"`: Specifies that the Docker image to be used will be built from the `Dockerfile` present in the same repository as the Action.

## How to Configure and Use

To use this GitHub Action in your project, follow the steps below:

### Prerequisites

* An InterSystems IRIS server with the source code management REST API configured and accessible through a WebServer.
* Credentials for an IRIS user with permissions to interact with the REST API (create, update, compile, and delete documents).
* Your source code organized in a GitHub repository.

### GitHub Action Configuration

1.  Create a YAML file within the `.github/workflows` directory in your repository (for example, `.github/workflows/deploy_iris.yml`).

2.  Paste the following content into the file, adapting it to your needs:

```yaml
# Template of a workflow to create, upate, delete and compile source documents on IRIS
name: Deploy to IRIS
# Trigger execute action
on:
  push:
    # All push to these branchs trigger the action Deploy to IRIS 
    branches:
      - <main>
  # All puspull_requesth to these branchs trigger the action Deploy to IRIS
  #pull_request:
  #  branches:
  #    - <put you branch>
#  Allow manually worflow execution
#  workflow_dispatch:

jobs:
  deploy-to-iris:
    runs-on: ubuntu-latest
    steps:
    # The 2 steps bellow checkout the changed files to deploy to IRIS, don't change.
      - name: Checkout
        uses: actions/checkout@v4
      - name: Get changed files and write the outputs to a JSON file
        id: modified-files
        uses: tj-actions/changed-files@v44
        with:
          separator: ","
          files: |
              **/*.{cls,mac,int,inc}
      # Final checkout files
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
          iris_usr: '${{ secrets.IRIS_USER }}'
          iris_pwd: '${{ secrets.IRIS_PWD }}'
          # don't change bellow lines
          changed_files: '${{ steps.modified-files.outputs.all_changed_files }}'
          deleted_files: '${{ steps.modified-files.outputs.deleted_files }}'
```

3.  **Important:** Store sensitive information (host, port, namespace, user, password, etc.) as [GitHub Secrets](https://docs.github.com/en/actions/security-secrets#creating-and-managing-encrypted-secrets). Replace the direct values in the YAML file with references to your secrets (e.g., `${{ secrets.IRIS_USER }}`).

4.  Adapt the `source_path` in the `Deploy to IRIS` step to match your project structure.

### Workflow Example

The example workflow above will run whenever there is a `push` to the `main` branch. It performs the following steps:

1.  **Checkout code:** Downloads your repository code to the GitHub Actions runner.
2.  **Identify changed and deleted files:** identify files that have been modified or added `${{ steps.modified-files.outputs.all_changed_files }}` and files that have been deleted `${{ steps.modified-files.outputs.all_changed_files }}`.
3.  **Deploy to IRIS:** Uses your custom "Deploy To IRIS" action, passing the necessary inputs using the GitHub Secrets and the output from the previous step.

## Contribution

Contributions are welcome! Please feel free to submit pull requests or open issues to suggest improvements or report bugs.

## License

This project is licensed under the [MIT License](LICENSE).
