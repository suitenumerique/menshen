# Menshen API client

`menshen_client` is an API client distributed as a Python's library to
integrate Menshen OAuth2 Token Exchange server in your autorization flow. It
has been designed to add few extra-dependencies to your project.

## Installation

The API client is available from PyPI and can be added to your project using:

```bash
uv add menshen_client
# or 
pip install menshen_client
```

## Usage

### Configure the client

You can create your client configuration using the following snippet:

```python 
from menshen_client import MenshenClient, MenshenConfiguration

# Configure the client
config = MenshenConfiguration(
   client_id="acme",
   client_secret="super-secret",
   server_root_url="https://menshen.example.org",
)

# Create the client instance
client = MenshenClient(config=config)
```

In this example, the client identifier and secret are those provided by your
Menshen instance administrator that should have registered a service provider
for your service. The `server_root_url` is the root URL of your Menshen server.

### Token exchange request

To generate an exchange token given a subject token and a related token type
use: 

```python
from menshen_client import (
    MenshenSupportedTokenType, 
    TokenExchangeRequest, 
    TokenExchangeResponse,
)

# Create the token exchange request
exchange_request = TokenExchangeRequest(
    subject_token="exampletoken",
    subject_token_type=MenshenSupportedTokenType.ACCESS_TOKEN,
    audience="https://target.example.org",
    scope="target:write",
)

# Get the exchanged token response
exchange_response: TokenExchangeResponse = client.exchange(exchange_request)
```

> For a full list of available fields in the token exchange request, please
> check the `TokenExchangeRequest` dataclass in the project's repository (and
> the [RFC 8693](https://www.rfc-editor.org/info/rfc8693/#name-request)).

The token exchange response contains the exchanged token that can be used to
query the target resource server:

```python
import requests 

resources = requests.get(
    "https://target.example.org/external_api/v1.0/resource/", 
    headers={
        "Authorization": f"Bearer {exchange_response.access_token}",
        "Content-Type": "application/json",
    }
)
```

> For a full list of available fields in the token exchange response, please
> check the `TokenExchangeResponse` dataclass in the project's repository (and
> the [RFC 8693](https://www.rfc-editor.org/info/rfc8693/#name-response)).

### Exchanged token instrospection

If you are the target resource server, you may want to introspect exchanged
tokens _via_ your autorization server instance using:

```python
from menshen_client import (
    MenshenSupportedTokenType, 
    IntrospectionRequest, 
    IntrospectionResponse,
)

# Create the token instrospection request
introspection_request = IntrospectionRequest(
    token="exampletoken",
    token_type_hint=MenshenSupportedTokenType.ACCESS_TOKEN,
)

# Get the token introspection response
introspection_response: IntrospectionResponse = client.introspect(introspection_request)

# Check if the token is still valid to access the resource and get user information
assert introspection_response.active
assert introspection_response.sub == "1234567890"
assert introspection_response.email == "jane.doe@example.org"
```

> For a full list of available fields in the token instrospection response,
> please check the `IntrospectionResponse` dataclass in the project's
> repository (and the [RFC
> 7662](https://www.rfc-editor.org/info/rfc7662/#section-2.2)).

### Exchanged token revocation

If for any reason, you want to revoke an exchaged token, you can query your
Menshen instance dedicated endpoint:

```python
from menshen_client import (
    MenshenSupportedTokenType, 
    RevocationRequest, 
)

# Create the token revocation request
revocation_request = RevocationRequest(
    token="exampletoken",
    token_type_hint=MenshenSupportedTokenType.ACCESS_TOKEN,
)

# Token revocation response is empty
client.revoke(revocation_request)
```

## License

This work is released under the MIT License (see
[LICENSE](https://github.com/suitenumerique/menshen/blob/main/LICENSE)).

While this project is a public-driven initiative, our license choice is an
invitation for private sector actors to use, sell and contribute to it.
