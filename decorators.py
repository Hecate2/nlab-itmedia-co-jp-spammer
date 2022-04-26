from typing import Callable, Tuple, Union


class RetryExhausted(Exception):
    pass


class AsyncRetry:
    def __init__(self, decorated_func: Callable,
                 retries: int = 3, exceptions: Union[Exception, Tuple[Exception]] = (Exception,)):
        self.decorated_func = decorated_func
        self.retries = retries
        self.exceptions = exceptions
    
    async def __call__(self, *func_args, **func_kwargs):
        tries = 0
        while self.retries != tries:
            tries += 1
            try:
                return await self.decorated_func(*func_args, **func_kwargs)
            except self.exceptions:
                pass
        raise RetryExhausted

    @classmethod
    def retry(cls, *decorator_args, **decorator_kwargs):
        if len(decorator_args) == 1 and decorator_kwargs == {} and callable(decorator_args[0]):
            # @decorator is called
            # decorator_args[0] is the decorated func
            return cls(decorator_args[0])
        # @decorator(...) is called
        return lambda decorated_func: cls(decorated_func, *decorator_args, **decorator_kwargs)