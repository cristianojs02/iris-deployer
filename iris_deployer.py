import os
import sys
import logging
import json
import requests
from requests.auth import HTTPBasicAuth

class IrisDeployer(object):
    '''
    Calss used to communicate wiht IRIS server to create, update, compile and
    delete source documents.
    '''
    def __init__(self, host: str, port: int, namespace_iris: str, https: int,
                api_base_url: str, iris_usr: str, iris_pwd: str, api_version: str,
                compilation_flags: str, source_path: str) -> None:
        
        logging.basicConfig(level = logging.INFO)
        
        self.__host = host
        self.__port = port
        self.__namespace_iris = namespace_iris
        self.__https = https
        self.__api_base_url = api_base_url
        self.__api_version = api_version
        self.__compilation_flags = compilation_flags
        self.__source_path = source_path
        self.__has_error: bool = False
        
        protocol: str = 'http' if self.__https == 0 else 'https'

        self.__PUT_DOC_URL: str = f'{protocol}://{self.__host}:{self.__port}'
        self.__PUT_DOC_URL += f'{self.__api_base_url}{self.__api_version}/{self.__namespace_iris}/doc/'

        self.__DELETE_DOCS_URL: str = f'{protocol}://{self.__host}:{self.__port}{self.__api_base_url}'
        self.__DELETE_DOCS_URL += f'{self.__api_version}/{self.__namespace_iris}/docs'

        self.__GET_DOC_URL: str = f'{protocol}://{self.__host}:{self.__port}{self.__api_base_url}'
        self.__GET_DOC_URL += f'{self.__api_version}/{self.__namespace_iris}/doc/'

        self.__COMPLIE_DOCS_URL: str = f'{protocol}://{self.__host}:{self.__port}{self.__api_base_url}'
        self.__COMPLIE_DOCS_URL += f'{self.__api_version}/{self.__namespace_iris}/action/compile'

        self.__iris_session = requests.Session()
        self.__iris_session.headers = {'Content-Type': 'application/json', 'Accept': '*/*'}
        self.__iris_session.auth = HTTPBasicAuth(iris_usr, iris_pwd)

    def compile_docs(self, doc_list: str)-> None:
        '''
        Receive a list with one or more files to compile. If no flags is passed,
        use default flags: "cukb"
        '''
        url = self.__COMPLIE_DOCS_URL + '?source=0&flags=' + self.__compilation_flags
        response = self.__iris_session.post(url, doc_list)
        iris_response: dict = json.loads(response.text)
        console_message: str = '\n'.join(iris_response['console'])
        match response.status_code:
            case 200 | 201:
                if iris_response['status']['summary'] is not None:
                    logging.error(console_message)
                    self.__has_error = True
                else:
                    logging.info(console_message)
            case 409 | 403:
                logging.warning(console_message)
            case _:
                logging.error(console_message)
                self.__has_error = True

    def delete_docs(self, doc_list: str)-> None:
        '''
        Receive a string with list with one or more files to delete.
        '''
        response = self.__iris_session.delete(self.__DELETE_DOCS_URL, data=doc_list)
        iris_response: dict = json.loads(response.text)
        match response.status_code:
            case 200:
                logging.info('\n'.join(iris_response['console']))
            case _:
                logging.error(iris_response['result']['status'])

    def deploy_docs(self, changed_files: list)-> None:
        '''
        Put each doc individual to IRIS, than compile all at once.
        '''
        if len(changed_files) == 0:
            logging.info('0 FILES TO DEPLOY!')
            return
        
        for source_file in changed_files:            
            # Fix document name. Remove sourcePath (IE.: src.)
            # from document name to avoid error in IRIS.
            file_name: str = source_file.replace(self.__source_path, '').replace('/', '.')
            document = self.get_doc(file_name)
            # if document exists set If-None-Match header to avoid conflict error
            if document is not None:                
                documentTimestamp = document['result']['ts']
                if documentTimestamp != "":
                    self.__iris_session.headers.update({'If-None-Match' : documentTimestamp})
            
            with open(source_file, 'r') as reader:
                source_document = {'enc': False, 'content' : []}
                content = []

                for line in reader:
                    content.append(line.rstrip())

                source_document['content'] = content
                self.put_doc(source_document, file_name)

        files_to_compile = '["' + '","'.join(changed_files) \
                .replace(self.__source_path, '') \
                .replace('/', '.') + '"]'

        self.compile_docs(files_to_compile)

    def get_doc(self, file_name: str)-> None:
        '''
        Get document before send a update avoiding false conflict error.
        '''
        url: str = self.__GET_DOC_URL + file_name
        response = self.__iris_session.get(url)
        iris_response: dict = json.loads(response.text)
        match response.status_code:
            case 200 | 404:
                pass
            case _:
                logging.error(iris_response['result']['status'])
                self.__has_error = True
        
    def put_doc(self, source_document: str, file_name: str)-> None:
        '''
        Send document to IRIS
        '''
        url: str = self.__PUT_DOC_URL + file_name        
        response = self.__iris_session.put(url, data=json.dumps(source_document, ensure_ascii=True))        
        iris_response: dict = json.loads(response.text)
        match response.status_code:
            case 200 | 201:
                pass
            case 409 | 425:
                logging.warning(iris_response['console'])
            case _:
                logging.error(iris_response['result']['status'])
                self.__has_error = True
    
    def exit(self) -> None:
        '''Existis according __has_error flag'''
        logging.info(f'EXITNIG WITH STATUS ERROR {self.__has_error}')
        if self.__has_error:
            sys.exit(1)
        
        sys.exit(0)

def in_debug_mode():
    """
    Checks if the Python program is running in debug mode.
    Returns True if in debug mode, False otherwise.
    """
    return ((hasattr(sys, 'gettrace')) and (sys.gettrace() is not None))
     
if __name__ == '__main__':
    if not in_debug_mode():
        iris_deployer = IrisDeployer(os.environ['INPUT_HOST'],
                                    int(os.environ['INPUT_PORT']),
                                    os.environ['INPUT_NAMESPACE_IRIS'],
                                    int(os.environ['INPUT_HTTPS']),
                                    os.environ['INPUT_BASE_API_URL'],
                                    os.environ['INPUT_IRIS_USR'],
                                    os.environ['INPUT_IRIS_PWD'],
                                    os.environ['INPUT_VERSION_API'],
                                    os.environ['INPUT_COMPILATION_FLAGS'],
                                    os.environ['INPUT_SOURCE_PATH'])
        
        changed_files = os.environ['INPUT_CHANGED_FILES'].split(',')
        if len(changed_files) > 0:
            iris_deployer.deploy_docs(changed_files)
        else:
            logging.info('0 FILES TO DEPLOY!')
    
        deleted_files = os.environ['INPUT_DELETED_FILES'].split(',')
        if len(deleted_files) > 0:
            iris_deployer.delete_docs('["' + '","'.join(deleted_files) \
                .replace(os.environ['INPUT_SOURCE_PATH'], '').replace('/', '.') + '"]')
        
        iris_deployer.exit()
    else:
        source_path = 'C:/Users/Cristiano Silva/OneDrive - CONFLUENCE/Projetos/Linker/src/'
        changed_files = [f'{source_path}test/githubaction/Test1.cls', f'{source_path}test/githubaction/Teste3.cls', f'{source_path}test/githubaction/Test4.cls']
        iris_deployer = IrisDeployer('189.1.174.141',57776,'LINKER_CORE_DEV', 0, '/api/atelier/', 'cristiano.silva', 'Sup3rS3nh@', 'v2','cuk',source_path)
        iris_deployer.deploy_docs(changed_files)
        deleted_files = '["' + '","'.join(changed_files).replace(source_path, '').replace('/', '.') + '"]'
        iris_deployer.delete_docs(deleted_files)
        iris_deployer.exit()