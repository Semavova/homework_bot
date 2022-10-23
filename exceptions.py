class EmptyList(Exception):
    """Исключение пустого списка."""

    pass


class ApiError(Exception):
    """Исключение доступа к Api."""

    pass


class StatusNotOk(Exception):
    """Исключение при статусе отличном от OK."""

    pass


class ServerReject(Exception):
    """Исключение при отказе сервера."""

    pass
