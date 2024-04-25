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

        self.__host = host
        self.__port = port
        self.__namespace_iris = namespace_iris
        self.__https = https
        self.__api_base_url = api_base_url
        self.__api_version = api_version
        self.__compilation_flags = compilation_flags
        self.__source_path = source_path
        protocol: str = 'http' if self.__https == 0 else 'https'

        self.__PUT_DOC_URL: str = f'{protocol}://{self.__host}:{self.__port}'
        self.__PUT_DOC_URL += f'/api/atelier/{self.__api_version}/{self.__namespace_iris}/doc/'

        self.__DELETE_DOCS_URL: str = f'{protocol}://{self.__host}:{self.__port}/api/atelier/'
        self.__DELETE_DOCS_URL += f'{self.__api_version}/{self.__namespace_iris}/docs'

        self.__GET_DOC_URL: str = f'{protocol}://{self.__host}:{self.__port}/api/atelier/'
        self.__GET_DOC_URL += f'{self.__api_version}/{self.__namespace_iris}/doc/'

        self.__COMPLIE_DOCS_URL: str = f'{protocol}://{self.__host}:{self.__port}/api/atelier/'
        self.__COMPLIE_DOCS_URL += f'{self.__api_version}/{self.__namespace_iris}/action/compile'

        self.__iris_session = requests.Session()
        self.__iris_session.headers = {'Content-Type': 'application/json', 'Accept': '*/*'}
        self.__iris_session.auth = HTTPBasicAuth(iris_usr, iris_pwd)

    def compile_docs(self, doc_list: str, flags: str = "cukb")-> None:
        '''
        Receive a list with one or more files to compile. If no flags is passed,
        use default flags: "cukb"
        '''
        logging.info(f'COMPILLING DOCUMENTS: {doc_list}')
        response = self.__iris_session.post(self.__COMPLIE_DOCS_URL, doc_list)
        match response.status_code:
            case 200:
                logging.info(f'DOCUMENT COMPILED!')
                logging.info(response.text)
            case 201:
                logging.info(f'DOCUMENT UPDATED!')
                logging.info(response.text)
            case 409:
                logging.warning(f'DOCUMENT UPDATE WITH CONFLICT!')
                logging.warning(response.text)
            case 423:
                logging.warning(f'DOCUMENT IS LOCKED AND CANNOT BE COMPILED!')
                logging.warning(response.text)
            # default error status
            case _:
                logging.error(f'COMPILATION ERROR!')
                logging.error(response.text)

    def delete_docs(self, doc_list: str)-> None:
        '''
        Receive a list with one or more files to delete.
        '''
        logging.info(f'DELETING DOCUMENTS: {doc_list}')
        response = self.__iris_session.delete(self.__DELETE_DOCS_URL, data=doc_list)
        match response.status_code:
            case 200:
                logging.info(f'DOCUMENTS DELETED!')
                logging.info(response.text)
            # default error status
            case _:
                logging.error(f'DELETION ERROR!')
                logging.error(response.text)

    def deploy_docs(self, changed_files: list)-> None:
        '''
        Put each doc individual to IRIS, than compile all at once.
        '''
        if changed_files.count == 0:
            logging.info('0 FILES TO DEPLOY!')
            return
        
        for source_file in changed_files:            
            # Fix document name. Remove sourcePath (IE.: src.)
            # from document name to avoid error in IRIS.
            file_name = source_file.replace(self.__source_path, '').replace('/', '.')
            document = self.get_doc(file_name)
            if document is None:
                continue
            
            # if document exists set If-None-Match header to avoid conflict error
            if document.ts != "":
                self.__iris_session.headers.update({'If-None-Match' : document.ts})
            
            print(f'PROCESSING FILE {source_file}')
            with open(source_file, 'r') as reader:
                source_document = {'enc': False, 'content' : []}
                content = []

                for line in reader:
                    content.append(line.rstrip())

                # JSON document with source code
                source_document['content'] = content
                self.put_doc(source_document, file_name)

        files_to_compile = '["' + '","'.join(changed_files) \
                .replace(self.__source_path, '') \
                .replace('/', '.') + '"]'

        self.compile_docs(files_to_compile)

    def get_doc(self, file_name: str)-> dict:
        '''
        Get document before send a update avoiding false conflict error.
        '''
        logging.info(f'GETTING DOCUMENT: {url}')
        url: str = self.__GET_DOC_URL + file_name
        response = self.__iris_session.get(url)
        
        match response.status_code:
            case 200 | 404:
                return json.load(response.text)
            case _:
                logging.error(f'ERROR GETTING DOCUMENT!')
                logging.error(response.text)
        
        return None
        
    def put_doc(self, source_document: str, file_name: str)-> None:
        '''
        Send document to IRIS
        '''
        url: str = self.__PUT_DOC_URL + file_name
        logging.info(f'DEPLOYING DOCUMENT: {url}')
        response = self.__iris_session.put(url, data=json.dumps(source_document, ensure_ascii=True))

        match response.status_code:
            case 200:
                logging.info(f'DOCUMENT CREATED!')
                logging.info(response.text)
            case 201:
                logging.info(f'DOCUMENT UPDATED!')
                logging.info(response.text)
            case 409:
                logging.warning(f'DOCUMENT WITH CONFLICTS. NOT UPDATED!')
                logging.warning(response.text)
            case 425:
                logging.warning(f'DOCUMENT IS LOCKED AND CANNOT BE WRITTEN!')
                logging.warning(response.text)
            # default status error
            case _:
                logging.error(f'DOCUMENT SENT WITH ERROR!')
                logging.error(response.text)

if __name__ == '__main__':
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
    if changed_files.count > 0:
        iris_deployer.deploy_docs()
    else:
        logging.info('0 FILES TO DEPLOY!')

    deleted_files = os.environ['INPUT_DELETED_FILES'].split(',')
    if deleted_files.count > 0:
        iris_deployer.delete_docs('["' + '","'.join(deleted_files.split(',')) \
            .replace(os.environ['INPUT_SOURCE_PATH'], '').replace('/', '.') + '"]')

#
# Standalone test need to comment the __main__ block above and uncomment the block bellow #
#
'''
source_path = 'C:\\Users\\Cristiano Silva\\OneDrive - CONFLUENCE\\Projetos\\Linker\\src\\'
changed_files = ['C:\\Users\\Cristiano Silva\\OneDrive - CONFLUENCE\\Projetos\\Linker\\src\\test\\githubaction\\Test.cls', 'C:\\Users\\Cristiano Silva\\OneDrive - CONFLUENCE\\Projetos\\Linker\\src\\test\\githubaction\\Test1.cls', 'C:\\Users\\Cristiano Silva\\OneDrive - CONFLUENCE\\Projetos\\Linker\\src\\test\\githubaction\\Test2.cls']
iris_deployer = IrisDeployer('192.168.1.7',57776,'LINKER_CORE_DEV', 0, '/api/atelier', 'cristiano.silva', 'Sup3rS3nh@', 'v2','cuk',source_path)
iris_deployer.deploy_documents(changed_files)
deleted_files = '["' + '","'.join(changed_files).replace(source_path, '').replace('\\', '.') + '"]'
iris_deployer.delete_docs(deleted_files)
'''
