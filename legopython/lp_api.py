#pylint: disable=line-too-long, consider-using-f-string
'''
Handles API calls for other modules.
APIS to test against https://github.com/toddmotto/public-apis
'''

from enum import Enum
from functools import wraps
from getpass import getpass
from pathlib import Path
from time import time
import json
import base64
import requests
from legopython.lp_logging import logger


def print_raw_request(requesttype:str, url: str, **kwargs):
    """Prints raw http requests to console for troubleshooting purposes.

    requesttype = HTTP Method, enter one of: delete, get, post, patch, head, put
    url = Address to send the api request
    **Kwargs accepts params for send_http_call
    """
    req = requests.Request(method = requesttype, url = url, **kwargs)
    req = req.prepare()
    print('{}\n{}\r\n{}\r\n\r\n{}'.format(
        '-----------START-----------',
        req.method + ' ' + req.url,
        '\r\n'.join('{}: {}'.format(key, value) for key, value in req.headers.items()),
        req.body,
    ))


def send_http_call(method:str, url:str, print_request:bool = False, timeout:int = 1000, http_attempts:int = 1, **kwargs) -> requests:
    '''Sends an api call via requests.request(method, url, args) and handles errors and retries

    method = HTTP Method, enter one of: delete, get, post, patch, head, put, 
    url = String Address to send the api request
    Timeout = Time in ms to wait for a response. ex) 500 = 0.5 seconds
    http_attempts = Whole int number of times to attempt to retry and get a response if the request times out.
    **Kwargs accepts values for the following dictionary keys: data, params, headers, cookies, files, auth, allow_redirects, proxies, hooks, stream, verify, cert, json 

    Request Module Exceptions: https://github.com/kennethreitz/requests/blob/master/requests/exceptions.py
    '''
    #Print the raw request sent for troubleshooting purposes.
    if print_request:
        print_raw_request(method, url, **kwargs)
    
    #Make an API call as specified, retrying failures and raising exceptions for invalid statuses as specified.
    for retry in range(http_attempts):
        try:
            response = requests.request(method = method, url = url, timeout = timeout, **kwargs)
            response.raise_for_status()
        except requests.exceptions.ConnectTimeout:
            logger.info(f'API Attempt #{retry} Timed out while trying to connect to server.')
            continue
        except requests.exceptions.ReadTimeout:
            logger.info(f'API Attempt #{retry}. Server did not send data in alotted time.')
            continue
        except requests.exceptions.HTTPError:
            logger.debug(f'API Attempt #{retry} returned http code {response.status_code}.')
            continue
        except requests.exceptions.RequestException as general_error: #General catch for other errors.
            raise requests.exceptions.RequestException("Response from {} errored, returned status code {}: {} \n{}".format(response.url, response.status_code, response.reason, response.content)) from general_error
        else:
            return response
    

class AuthType(Enum):
    """Different authentication types supported by the AuthHandler.
    https://www.geeksforgeeks.org/authentication-using-python-requests/
    """
    BASIC = 1
    JWT_BEARER = 2
    OAUTH2 = 3 #TODO THIS DOES NOT WORK

home_folder = Path.home()/".lp"

class AuthHandler:
    """Handles authentication for APIs."""
    def __init__(self, name:str, auth_type:AuthType, env_config:list, env:str = 'prod') :
        self.name = name
        self.auth_type = auth_type
        self.env_config = env_config
        self.env = env
        self.credentials = None

    @property
    def name(self):
        """Name for the function using the auth handler"""
        return self._name

    @name.setter
    def name(self, name:str):
        self._name = name

    @property
    def auth_type(self):
        """Auth type for the API"""
        return self._auth_type

    @auth_type.setter
    def auth_type(self, auth_type:AuthType):
        self._auth_type = auth_type

    @property
    def env_config(self):
        """The config for each environment"""
        return self._env_config

    @env_config.setter
    def env_config(self,env_config):
        self._env_config = env_config

    @property
    def env(self):
        """Which environment in the env_config to use"""
        return self._env

    @env.setter
    def env(self, env):
        if env not in self.env_config.keys():
            #raise TypeError(f"Environment {env} not in environment config")
            #In some cases you want to run QA env but QA env does not exist for Camudna. So, this should not error but instead not be a hard stop.
            #How do we get this to warn that a module doesn't have QA, for example?
            logger.warn(f"Environment {env} does not exist as a config")
        else:
            self._env = env
        #if the environment changes we want to eliminate the cached credentials
        self.credentials = None

    @property
    def credentials(self):
        """The active credentials used to authenticate"""
        return self._credentials

    @credentials.setter
    def credentials(self, credentials):
        self._credentials = credentials

    def _get_cached_credentials(self):
        """Private function to get credentials stored on disk"""
        Path(home_folder).mkdir(exist_ok=True)
        cached_credential_path = Path(home_folder) / f"{self.name}-{self.env}.json"
        credfile = Path(cached_credential_path)
        if not credfile.exists():
            logger.debug("Could not find cached credentials at %s", cached_credential_path)
            return None
        return json.loads(credfile.read_text(encoding='utf-8'))

    def _cache_credentials(self):
        """Private function to store credentials on disk"""
        Path(home_folder).mkdir(exist_ok=True)
        cached_credential_path = Path(home_folder) / f"{self.name}-{self.env}.json"
        credfile = Path(cached_credential_path)
        credfile.write_text(json.dumps(self.credentials),encoding="utf-8")

    def clear_cached_credentials(self):
        """Clears credentials cached on disk and in memory"""
        Path(home_folder).mkdir(exist_ok=True)
        cached_credential_path = Path(home_folder) / f"{self.name}-{self.env}.json"
        cached_credential_path.unlink()
        self.credentials = None

    def _get_basic_auth_credentials(self):
        """Prompt for basic authentication credentials and return the username and auth string"""
        username = input(f"Enter the username for {self.name} {self.env}: ")
        password = getpass(f"Enter the password for {self.name} {self.env}: ")
        return username, base64.b64encode(bytes(f"{username}:{password}",encoding='utf8')).decode('utf-8')

    def _request_token(self):
        """
        Calls a token URL to request a new Java Web Token.
        """
        token_params = self.env_config.get(self.env).get("token_params")
        for base_key,base_value in token_params.items():
            if isinstance(base_value,dict):
                for key,value in base_value.items():
                    if callable(value):
                        logger.debug("Config item %s for %s is a function, calling function to update value",key,base_key)
                        token_params[base_key][key] = value()
        return send_http_call(method='post', **token_params)


    def _request_oauth2_token(self):
        """
        Calls to get an oauth2 token using basic auth. #TODO THIS IS NOT WORKING, working on example_api_oauth2.
        """
        token_params = self.env_config.get(self.env).get("token_params")
        for base_key,base_value in token_params.items():
            if isinstance(base_value,dict):
                for key,value in base_value.items():
                    if callable(value):
                        logger.debug("Config item %s for %s is a function, calling function to update value",key,base_key)
                        token_params[base_key][key] = value()
        return send_http_call(method='post', **token_params)


    def get_valid_credentials(self):
        """
        Function that ensures the present authentication values are valid
        and not expired, and if they don't exists it gets some.
        """
        now = int(time())
        if self.credentials is None:
            logger.debug("Beginning loading of cached credentials")
            self.credentials = self._get_cached_credentials()
        if self.credentials is None or (self.credentials.get('expiry') and self.credentials.get('expiry',0) <= now):
            logger.debug('Getting new authentication credentials')
            self.credentials = {}
            self.credentials['received'] = now
            if self.auth_type == AuthType.BASIC:
                self.credentials["username"],self._credentials["credstring"] = self._get_basic_auth_credentials()
                self.credentials["auth_header"] = f"Basic {self._credentials.get('credstring')}"
            elif self.auth_type == AuthType.JWT_BEARER:
                self.credentials = self._request_token()
                self.credentials['expiry'] = now + self._credentials.get('expires_in',3600)
                self.credentials['auth_header'] = f"Bearer {self._credentials.get('access_token')}"
            elif self.auth_type == AuthType.OAUTH2: #TODO THIS DOES NOT WORK
                self.credentials["username"], self._credentials["credstring"] = self._get_basic_auth_credentials()
                self.credentials["auth_header"] = f"Basic {self._credentials.get('credstring')}"
                self.credentials = self._request_oauth2_token()
                self.credentials['expiry'] = now + self._credentials.get('expires_in',3600)
                self.credentials['auth_header'] = f"Bearer {self._credentials.get('access_token')}"
        self._cache_credentials()
        return self.credentials

    def manage_auth(self, func):
        """Decorator to handle authentication"""
        @wraps(func)
        def inner(*args,**kwargs):
            creds = self.get_valid_credentials()
            kwargs["api_url"] = kwargs.setdefault("api_url",self.env_config.get(self.env).get("api_url"))
            kwargs["headers"] = kwargs.setdefault("headers",{})
            kwargs["headers"]["Authorization"] = creds.get("auth_header")
            return func(*args,**kwargs)
        return inner
