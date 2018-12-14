class TDLibError(Exception):
    pass


class FatalError(Exception):
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


class AuthError(TDLibError):
    pass


class PhoneCodeInvalid(AuthError):
    pass


class PasswordError(AuthError):
    pass


class TwoFactorPasswordNeeded(AuthError):
    pass
