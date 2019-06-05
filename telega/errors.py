class TDLibError(Exception):
    pass


class FatalError(TDLibError):
    pass


class InternalTdLibTimeoutExpired(TDLibError):
    """ In C++ """
    pass


class TdLibResponseTimeoutError(TDLibError):
    """ In Python """
    pass


class BadProxy(TDLibError):
    pass


class TdLibConnectionError(TDLibError):
    pass


class NoPermission(TDLibError):
    pass


class UnknownError(TDLibError):
    pass


class ObjectNotFound(TDLibError):
    pass


class TooManyRequests(TDLibError):
    pass


class AlreadyAuthorized(TDLibError):
    pass


class SetAuthenticationPhoneNumberUnexpected(TDLibError):
    pass


class AuthError(TDLibError):
    pass


class InvalidPhoneNumber(AuthError):
    pass


class PhoneCodeInvalid(AuthError):
    pass


class PasswordError(AuthError):
    pass


class TwoFactorPasswordNeeded(AuthError):
    pass


class AlreadyLoggingOut(TDLibError):
    pass
