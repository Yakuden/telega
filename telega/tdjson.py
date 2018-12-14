import json
import logging
from typing import Any, Dict
from ctypes import (
    CDLL,
    CFUNCTYPE,
    c_int,
    c_char_p,
    c_double,
    c_void_p,
    c_longlong,
)

from telega import errors


logger = logging.getLogger('telega')


class TDJson:

    def __init__(self, library_path: str, log_verbosity_level=2) -> None:
        logger.info(f'[TDJson] Using TDLib path "{library_path}"')
        if not library_path:
            raise errors.FatalError('Excuse me, where is a library_path (libtdjson.so file)')
        self._load_functions(library_path)

        self._client_id: int = self._td_json_client_create()
        self._td_set_log_verbosity_level(log_verbosity_level)  # c++ lib logging level
        self._td_set_log_fatal_error_callback(self._lib_callback_type(self._on_fatal_error_callback))

    def send(self, query: Dict[Any, Any]) -> None:
        dumped_query = json.dumps(query).encode('utf-8')
        self._td_json_client_send(self._client_id, dumped_query)
        logger.debug(f'[TDJson][me ==>] Sent {query}')

    def receive(self, timeout=1.0) -> Dict[Any, Any]:
        result = self._td_json_client_receive(self._client_id, timeout)
        if result:
            result = json.loads(result.decode('utf-8'))
            logger.debug(f'[TDJson][me <==] Received {result}')
        return result

    def destroy(self) -> None:
        self._td_json_client_destroy(self._client_id)

    def _load_functions(self, library_path: str):
        """ load TDLib functions from shared library """
        lib = CDLL(library_path)

        self._td_json_client_create = lib.td_json_client_create
        self._td_json_client_create.restype = c_void_p
        self._td_json_client_create.argtypes = []

        self._td_json_client_receive = lib.td_json_client_receive
        self._td_json_client_receive.restype = c_char_p
        self._td_json_client_receive.argtypes = [c_void_p, c_double]

        self._td_json_client_send = lib.td_json_client_send
        self._td_json_client_send.restype = None
        self._td_json_client_send.argtypes = [c_void_p, c_char_p]

        self._td_json_client_execute = lib.td_json_client_execute
        self._td_json_client_execute.restype = c_char_p
        self._td_json_client_execute.argtypes = [c_void_p, c_char_p]

        self._td_json_client_destroy = lib.td_json_client_destroy
        self._td_json_client_destroy.restype = None
        self._td_json_client_destroy.argtypes = [c_void_p]

        self._td_set_log_file_path = lib.td_set_log_file_path
        self._td_set_log_file_path.restype = c_int
        self._td_set_log_file_path.argtypes = [c_char_p]

        self._td_set_log_max_file_size = lib.td_set_log_max_file_size
        self._td_set_log_max_file_size.restype = None
        self._td_set_log_max_file_size.argtypes = [c_longlong]

        self._td_set_log_verbosity_level = lib.td_set_log_verbosity_level
        self._td_set_log_verbosity_level.restype = None
        self._td_set_log_verbosity_level.argtypes = [c_int]

        self._lib_callback_type = CFUNCTYPE(None, c_char_p)
        self._td_set_log_fatal_error_callback = lib.td_set_log_fatal_error_callback
        self._td_set_log_fatal_error_callback.restype = None
        self._td_set_log_fatal_error_callback.argtypes = [self._lib_callback_type]

    @staticmethod
    def _on_fatal_error_callback(error_message):
        raise errors.FatalError(error_message)
