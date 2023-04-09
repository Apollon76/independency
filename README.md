# Independency
Independency is a DI container library. Unlike many other Python DI containers Independency operates in the local scope. It's inspired by [punq](https://github.com/bobthemighty/punq), so the API is very similar.

Independency supports generics and other specific typings.


## Installation

```bash
pip install independency
```

## Usage
Independency avoids global state, so you must explicitly create a container in the entrypoint of your application:

```python3
import independency

builder = independency.ContainerBuilder()
# register application dependencies
container = builder.build()
obj: SomeRegisteredClass = container.resolve(SomeRegisteredClass)
```

### Registering Dependencies

```python3
builder.register(User, User)  # creates new object on each `resolve`
builder.singleton(User, User)  # creates object only once
builder.singleton(Storage[int], Storage[int])  # use generics
builder.singleton('special_storage', Storage[int])  # or literals to register dependency
```

The second argument is a factory, so you can provide not only a class `__init__` function:

```python3
def create_db(config: Config) -> Database:
    return Database(config.dsn)

builder.singleton(Config, Config)
builder.singleton(Database, create_db)
```

If you need to pass some specific dependency as an argument to a factory, use `Dependency`:

```python3
from independency import Dependency as Dep

builder.singleton(SpecificConnection, SpecificConnection)
builder.singleton(Storage, conn=Dep(SpecificConnection))
```

## Examples
```python3
import requests

from independency import Container, ContainerBuilder


class Config:
    def __init__(self, url: str):
        self.url = url


class Getter:
    def __init__(self, config: Config):
        self.config = config

    def get(self):
        return requests.get(self.config.url)


def create_container() -> Container:
    builder = ContainerBuilder()
    builder.singleton(Config, Config, url='http://example.com')
    builder.singleton(Getter, Getter)
    return builder.build()


def main():
    container = create_container()
    getter: Getter = container.resolve(Getter)
    print(getter.get().status_code)


if __name__ == '__main__':
    main()
```

Suppose we need to declare multiple objects of the same type and use them correspondingly.

```python3
from independency import Container, ContainerBuilder, Dependency as Dep


class Queue:
    def __init__(self, url: str):
        self.url = url

    def pop(self):
        ...

    
class Consumer:
    def __init__(self, q: Queue):
        self.queue = q

    def consume(self):
        while True:
            message = self.queue.pop()
            # process message


def create_container() -> Container:
    builder = ContainerBuilder()
    builder.singleton('first_q', Queue, url='http://example.com')
    builder.singleton('second_q', Queue, url='http://example2.com')
    builder.singleton('c1', Consumer, q=Dep('first_q'))
    builder.singleton('c2', Consumer, q=Dep('second_q'))
    return builder.build()


def main():
    container = create_container()
    consumer: Consumer = container.resolve('c1')
    consumer.consume()


if __name__ == '__main__':
    main()
```

## Contributing

If you find a bug or have a feature request, please open an issue on GitHub. Pull requests are also welcome!
