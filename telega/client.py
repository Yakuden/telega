import logging
import os
import uuid
import time
from pathlib import Path
from time import sleep
from typing import Union, List

from telega import errors
from telega.tdjson import TDJson


logger = logging.getLogger('telega')


BASE_DIR = 'telega'
ABS_BASE_DIR = str([p for p in Path(__file__).absolute().parents if p.name == BASE_DIR][0])
# DEFAULT_TDLIB_PATH = str(os.path.join(ABS_BASE_DIR, 'td_lib/linux/libtdjson.so'),)
DEFAULT_TDLIB_PATH = str(os.path.join(ABS_BASE_DIR, 'td_lib/linux/libtdjson.so.1.4.0'),)


class AuthStates:
    Ready = 'authorizationStateReady'

    WaitTdlibParameters = 'authorizationStateWaitTdlibParameters'
    WaitEncryptionKey = 'authorizationStateWaitEncryptionKey'
    WaitPhoneNumber = 'authorizationStateWaitPhoneNumber'
    WaitCode = 'authorizationStateWaitCode'
    WaitPassword = 'authorizationStateWaitPassword'

    LoggingOut = 'authorizationStateLoggingOut'
    Closing = 'authorizationStateClosing'
    Closed = 'authorizationStateClosed'


class ProxyTypes:
    """
        You can use custom proxy types like {'@type': 'proxyTypeMtproto', 'secret': '123'}
        https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1_proxy_type.html
    """
    Socks5 = {'@type': 'proxyTypeSocks5'}
    Http = {'@type': 'proxyTypeHttp'}


class TelegramTDLibClient:

    database_encryption_key_length = 12
    default_timeout = 60
    default_request_delay = 1  # for pagination
    default_chats_page_size = 100
    default_members_page_size = 200

    def __init__(self,
                 api_id: int,
                 api_hash: str,
                 phone: str,
                 database_encryption_key: str,
                 library_path: str = DEFAULT_TDLIB_PATH,  # 'libtdjson.so'
                 tdlib_log_level=2,
                 timeout: Union[int, float] = default_timeout,
                 request_delay: Union[int, float] = default_request_delay,
                 sessions_directory: str = 'tdlib_sessions',
                 use_test_data_center: bool = False,
                 use_message_database: bool = True,
                 # proxy: dict = None,  # Deprecated. Use self.set_proxy()
                 device_model: str = 'SpecialDevice',
                 application_version: str = '7.62',
                 system_version: str = '5.45',
                 system_language_code: str = 'en') -> None:

        if len(database_encryption_key) != self.database_encryption_key_length:
            raise ValueError('database_encryption_key len must be %d' % self.database_encryption_key_length)

        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self._database_encryption_key = database_encryption_key
        self.timeout = timeout
        self.request_delay = request_delay
        self.files_directory = sessions_directory
        self.use_test_data_center = use_test_data_center
        self.use_message_database = use_message_database
        self.device_model = device_model
        self.application_version = application_version
        self.system_version = system_version
        self.system_language_code = system_language_code

        self._tdjson_client = TDJson(library_path, tdlib_log_level)
        self._init()

    def __del__(self):
        if hasattr(self, '_tdjson'):
            self._tdjson_client.destroy()

    def remove_proxy(self) -> None:
        proxies = self.call_method('getProxies')
        for proxy in proxies['proxies']:
            self.call_method('removeProxy', proxy_id=proxy['id'])

    def set_proxy(self, host: str, port: int, proxy_type=ProxyTypes.Http, check_proxy=True) -> None:
        """
            Since TDLib 1.3.0 addProxy can be called to enable proxy any time, even before setTdlibParameters. (lie)
            Also you can use custom proxy_type like {'@type': 'proxyTypeMtproto', 'secret': '123'}
        """
        self.remove_proxy()
        self.call_method('addProxy', server=host, port=port, enable=True, type=proxy_type)
        if check_proxy:
            self.check_proxy()

    def check_proxy(self) -> float:
        # getting current proxy -------------------------------------------
        proxies = self.call_method('getProxies')['proxies']
        if not proxies:
            raise errors.BadProxy('No any proxy')
        if len(proxies) != 1:
            logger.error('len(proxies) = %d. Smth went wrong', len(proxies))
        proxy = proxies[0]

        try:
            result = self.call_method('pingProxy', proxy_id=proxy['id'])
            logger.info('Proxy (%s:%s) works. Response time: %s seconds' %
                        (proxy['server'], proxy['port'], result['seconds']))
            return result['seconds']
        except (errors.InternalTdLibTimeoutExpired, errors.TdLibConnectionError):
            raise errors.BadProxy

    def get_auth_state(self) -> str:
        result = self.call_method('getAuthorizationState')
        authorization_state = result['@type']
        return authorization_state

    def is_authorized(self) -> bool:
        authorization_state = self.get_auth_state()
        return authorization_state == AuthStates.Ready

    def auth_request(self) -> None:
        logger.info('Sending code request for phone number (%s)', self.phone)

        try:
            response = self.call_method('setAuthenticationPhoneNumber',
                                        phone_number=self.phone,
                                        allow_flash_call=False,
                                        is_current_phone_number=False)
            logger.info('Sending code response: %s', response)

        except errors.SetAuthenticationPhoneNumberUnexpected:
            auth_state = self.get_auth_state()
            if auth_state == AuthStates.Ready:
                raise errors.AlreadyAuthorized
            raise errors.SetAuthenticationPhoneNumberUnexpected(f'Current AuthState: {auth_state}')

    def send_sms_code(self, sms_code: str, password: str = None) -> None:
        authorization_state = self.get_auth_state()
        if authorization_state == AuthStates.WaitCode:
            send_code_result = self.call_method('checkAuthenticationCode', code=sms_code)
            logger.debug('checkAuthenticationCode response: %s', send_code_result)
            authorization_state = self.get_auth_state()
        if authorization_state == AuthStates.WaitPassword:
            if not password:
                raise errors.TwoFactorPasswordNeeded
            send_password_result = self.call_method('checkAuthenticationPassword', password=password)
            logger.debug('checkAuthenticationPassword response: %s', send_password_result)

        sleep(0.2)
        self.get_auth_state()  # just for wait auth data saving

    def log_out(self) -> None:
        try:
            self.call_method('logOut')
        except errors.TDLibError as e:
            if self.is_authorized():
                raise e
        logger.info('Logged out %s. Current state: "%s"', self.phone, self.get_auth_state())

    def get_me(self) -> dict:
        result = self.call_method('getMe')
        return result

    def get_all_chats(self, page_size=default_chats_page_size) -> List[dict]:
        if page_size <= 1:
            raise errors.TDLibError('Invalid "page_size"')

        chats = []
        added_chat_ids = set()
        offset_order = 2 ** 63 - 1
        offset_chat_id = 0
        has_next_page = True

        while has_next_page:
            result = self.call_method('getChats',
                                      offset_order=offset_order, offset_chat_id=offset_chat_id, limit=page_size)

            chat_id_list = result['chat_ids']
            for chat_id in chat_id_list:
                if chat_id not in added_chat_ids:
                    result = self.call_method('getChat', chat_id=chat_id)  # offline request
                    chats.append(result)
                    added_chat_ids.add(chat_id)

            if chat_id_list and not len(chat_id_list) < page_size:
                offset_order = chats[-1]['order']
                sleep(self.request_delay)
            else:
                has_next_page = False

        return chats

    def get_group_members(self, group_id: int, page_size=default_members_page_size) -> List[dict]:
        """ for basic group, super group (channel) """
        try:
            chat = self.call_method('getChat', chat_id=group_id)  # offline request
        except errors.ObjectNotFound:
            self.get_all_chats()
            chat = self.call_method('getChat', chat_id=group_id)  # offline request

        if chat['type']['@type'] == 'chatTypeBasicGroup':
            members = self.call_method('getBasicGroupFullInfo',
                                       basic_group_id=chat['type']['basic_group_id'])['members']

        elif chat['type']['@type'] == 'chatTypeSupergroup':
            members = self._get_super_group_members(chat, page_size)

        else:
            raise errors.TDLibError('Unknown group type: %s' % chat['type']['@type'])

        return members

    def get_user(self, user_id: int) -> dict:
        """ This is an offline request if the current user is not a bot. """
        user = self.call_method('getUser', user_id=user_id)
        return user

    def _get_super_group_members(self, chat: dict, page_size=default_members_page_size) -> List[dict]:
        if page_size <= 1:
            raise errors.TDLibError('Invalid "page_size"')

        members = []
        added_ids = set()
        offset = 0
        total_count = None
        has_next_page = True

        while has_next_page:
            response = self.call_method('getSupergroupMembers',
                                        supergroup_id=chat['type']['supergroup_id'], offset=offset, limit=page_size)
            page = response['members']
            total_count = response['total_count']  # may be different for different requests

            for member in page:
                if member['user_id'] not in added_ids:
                    members.append(member)
                    added_ids.add(member['user_id'])

            if len(page):
                offset += len(page)
                sleep(self.request_delay)
            else:
                has_next_page = False

            logger.info('Got %d members. Total: %d', len(page), len(members))

        if total_count != len(members):
            logger.warning('total_count != len(members):  %s/%s' % (total_count, len(members)))
        return members

    def call_method(self, method_name: str, timeout=None, **params) -> dict:
        """ Use this method to call any other method of the tdlib. """
        timeout = timeout or self.timeout
        request_id = uuid.uuid4().hex
        data = {'@type': method_name,
                '@extra': {'request_id':  request_id}}
        data.update(params)
        self._tdjson_client.send(data)

        result = self._wait_result(request_id, timeout)
        return result

    def _wait_result(self, request_id: str, timeout: float) -> dict:
        """ Blocking method to wait for the result """
        started_at = time.time()
        while True:
            response = self._tdjson_client.receive(0.1)
            if response:
                received_request_id = response.get('@extra', {}).get('request_id')
                if request_id == received_request_id:
                    self._handle_errors(response)
                    return response

            if timeout and time.time() - started_at > timeout:
                raise errors.TdLibResponseTimeoutError('TdLibResponseTimeoutError')

    @staticmethod
    def _handle_errors(response: dict):   # TODO: refactoring
        if response['@type'] == 'error':
            message = response.get('message', 'Empty error message')
            code = response.get('code')
            exc_msg = f'Telegram error: %s -> %s' % (code, message)

            if message == 'PHONE_NUMBER_INVALID':
                raise errors.InvalidPhoneNumber(exc_msg)

            if message == 'PASSWORD_HASH_INVALID':
                raise errors.PasswordError(exc_msg)

            if message == 'PHONE_CODE_INVALID':
                raise errors.PhoneCodeInvalid(exc_msg)

            if message == 'Supergroup members are unavailable':
                raise errors.NoPermission(exc_msg)

            if message == 'Chat not found':
                raise errors.ObjectNotFound(exc_msg)

            if message == 'setAuthenticationPhoneNumber unexpected':
                raise errors.SetAuthenticationPhoneNumberUnexpected(exc_msg)

            if message == 'Already logging out':
                raise errors.AlreadyLoggingOut(exc_msg)

            if message in ('Timeout expired', 'Pong timeout expired'):
                raise errors.InternalTdLibTimeoutExpired(exc_msg)

            if code == 401 or message == 'Unauthorized':
                raise errors.AuthError(exc_msg)

            if code in (429, 420):
                raise errors.TooManyRequests(exc_msg)

            if message.startswith('Failed to connect to'):
                raise errors.TdLibConnectionError(exc_msg)

            if message in ('Connection closed', 'Failed to connect', 'Connection timeout expired'):
                raise errors.TdLibConnectionError(exc_msg)

            if message.startswith('Read from fd') and message.endswith('has failed'):  # I know regex he he
                # https://github.com/tdlib/td/issues/476
                raise errors.TdLibConnectionError(exc_msg)

            raise errors.UnknownError(exc_msg)

    def _init(self) -> None:
        """ init before auth_request """

        self.call_method('updateAuthorizationState', **{
            '@type': 'setTdlibParameters',
            'parameters': {
                'use_test_dc': self.use_test_data_center,
                'api_id': self.api_id,
                'api_hash': self.api_hash,
                'device_model': self.device_model,
                'system_version': self.system_version,
                'application_version': self.application_version,
                'system_language_code': self.system_language_code,
                'use_message_database': self.use_message_database,
                'database_directory': os.path.join(self.files_directory, self.phone, 'database'),
                'files_directory': os.path.join(self.files_directory, self.phone, 'files'),
            }
        })

        self.call_method('updateAuthorizationState', **{
            '@type': 'checkDatabaseEncryptionKey',
            'encryption_key': self._database_encryption_key
        })

        self.remove_proxy()   # old proxy saved in session file
