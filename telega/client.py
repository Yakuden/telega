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
DEFAULT_TDLIB_PATH = str(os.path.join(ABS_BASE_DIR, 'td_lib/linux/libtdjson.so'),)


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


class TelegramTDLibClient:

    database_encryption_key_length = 12
    default_timeout = 60
    default_request_delay = 0.5  # for pagination
    default_chats_page_size = 100
    default_members_page_size = 200

    def __init__(self,
                 api_id: int,
                 api_hash: str,
                 phone: str,
                 database_encryption_key: str,
                 library_path: str = DEFAULT_TDLIB_PATH,  # 'libtdjson.so'
                 tdlib_log_level=2,
                 request_timeout: Union[int, float] = default_timeout,
                 request_delay: Union[int, float] = default_request_delay,
                 sessions_directory: str = 'tdlib_sessions',
                 use_test_data_center: bool = False,
                 use_message_database: bool = True,
                 proxy: dict = None,  # proxy={'host': '0.0.0.0', 'port': 9999}
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
        self.request_timeout = request_timeout
        self.request_delay = request_delay
        self.files_directory = sessions_directory
        self.use_test_data_center = use_test_data_center
        self.use_message_database = use_message_database
        self.proxy = proxy
        self.device_model = device_model
        self.application_version = application_version
        self.system_version = system_version
        self.system_language_code = system_language_code

        self._tdjson_client = TDJson(library_path, tdlib_log_level)
        self._init()

    def __del__(self):
        if hasattr(self, '_tdjson'):
            self._tdjson_client.destroy()

    def get_auth_state(self) -> str:
        result = self.call_method('getAuthorizationState')
        authorization_state = result['@type']
        return authorization_state

    def is_authorized(self) -> bool:
        authorization_state = self.get_auth_state()
        return authorization_state == AuthStates.Ready

    def auth_request(self) -> None:
        logger.info('Sending code request for phone number (%s)', self.phone)
        response = self.call_method('setAuthenticationPhoneNumber',
                                    phone_number=self.phone,
                                    allow_flash_call=False,
                                    is_current_phone_number=True)
        logger.info('Sending code response: %s', response)

    def send_sms_code(self, sms_code: str, password: str = None) -> None:
        authorization_state = self.get_auth_state()
        if authorization_state == AuthStates.WaitCode:
            send_code_result = self.call_method('checkAuthenticationCode', code=sms_code)
            logger.info('checkAuthenticationCode response: %s', send_code_result)
            authorization_state = self.get_auth_state()
        if authorization_state == AuthStates.WaitPassword:
            if not password:
                raise errors.TwoFactorPasswordNeeded
            send_password_result = self.call_method('checkAuthenticationPassword', password=password)
            logger.info('checkAuthenticationPassword response: %s', send_password_result)

        self.get_auth_state()  # just for wait auth data saving

    def log_out(self) -> None:
        try:
            self.call_method('logOut')
        except errors.AuthError:
            pass
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
        chat = self.call_method('getChat', chat_id=group_id)  # offline request

        if chat['type']['@type'] == 'chatTypeBasicGroup':
            members = self.call_method('getBasicGroupFullInfo',
                                       basic_group_id=chat['type']['basic_group_id'])['members']

        elif chat['type']['@type'] == 'chatTypeSupergroup':
            # full_info = self._call_method('getSupergroupFullInfo', supergroup_id=chat['type']['supergroup_id'])
            # if not full_info['can_get_members']:
            #     raise errors.NoPermission('administrator privileges are required "%s"' % chat['title'])
            members = self._get_super_group_members(chat, page_size)
            # return members

        else:
            raise errors.TDLibError('Unknown group type: %s' % chat['type']['@type'])

        users = [self.get_user(m['user_id']) for m in members]
        return users

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
        timeout = timeout or self.request_timeout
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
                raise errors.UnknownError('TimeOutError')

    @staticmethod
    def _handle_errors(response: dict):
        if response['@type'] == 'error':
            message = response.get('message', 'Empty error message')
            code = response.get('code')
            exc_msg = f'Telegram error: %s -> %s' % (code, message)

            if message == 'PASSWORD_HASH_INVALID':
                raise errors.PasswordError(exc_msg)

            if message == 'PHONE_CODE_INVALID':
                raise errors.PhoneCodeInvalid(exc_msg)

            if message == 'Supergroup members are unavailable':
                raise errors.NoPermission(exc_msg)

            if message == 'Chat not found':
                raise errors.ObjectNotFound(exc_msg)

            if message == 'setAuthenticationPhoneNumber unexpected':
                raise errors.AlreadyAuthorized(exc_msg)

            if code == 401 or message == 'Unauthorized':
                raise errors.AuthError(exc_msg)

            if code in (429, 420):
                raise errors.TooManyRequests(exc_msg)

            raise errors.UnknownError(exc_msg)

    def _init(self) -> None:
        """ init before auth_request """

        self.call_method('updateAuthorizationState', timeout=5, **{
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

        self.call_method('updateAuthorizationState', timeout=5, **{
            '@type': 'checkDatabaseEncryptionKey',
            'encryption_key': self._database_encryption_key
        })

        if self.proxy:
            self._set_proxy(self.proxy['host'], self.proxy['port'])

    def _set_proxy(self, host: str, port: int) -> None:
        """ SOCKS5 proxy only """
        proxy_type = {'@type': 'proxyTypeSocks5'}
        self.call_method('addProxy', timeout=5, server=host, port=port, enable=True, type=proxy_type)
