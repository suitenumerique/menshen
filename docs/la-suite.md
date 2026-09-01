# LaSuite: reference implementation

This document aim to provide a reference implementation as we designed it at
LaSuite. In the following sections, you will find our nomenclature and example
rules.

## Resource servers

Current section is an attempt to document exhaustively every resource
accessible within LaSuite services. Resources are accessible using APIs
implementing the OAuth 2.0 Resource Server specification.

> Please note that every API endpoint should be concatenated with the root
> path: `/external_api/v1.0`, _i.e._ `/external_api/v1.0/{endpoint}`

> Please, also note that all API endpoints referenced in this document may not
> be activated in LaSuite services instances. They reflect what actions may be
> possible using services APIs.

### Docs

> `config` and `user-reconciliations` resources have been explicitly ignored as
> we think they are out-of-scope for a resource server exposition.

<details>

<summary>Resource: <code>document</code></summary>

| Resource | HTTP verb | Endpoint                              | Action            |
| -------- | --------- | ------------------------------------- | ----------------- |
| document | GET       | `/documents/`                         | list              |
| document | POST      | `/documents/`                         | create            |
| document | GET       | `/documents/{id}/`                    | retrieve          |
| document | PUT       | `/documents/{id}/`                    | update            |
| document | DELETE    | `/documents/{id}/`                    | delete            |
| document | POST      | `/documents/{id}/ai-proxy/`           | ai-proxy          |
| document | POST      | `/documents/{id}/ai-transform/`       | ai-transform      |
| document | POST      | `/documents/{id}/ai-translate/`       | ai-translate      |
| document | POST      | `/documents/{id}/attachment-upload/`  | attachment-upload |
| document | GET       | `/documents/{id}/can-edit`            | can-edit          |
| document | GET       | `/documents/{id}/children/`           | list-children     |
| document | POST      | `/documents/{id}/children/`           | create-children   |
| document | GET       | `/documents/{id}/content/`            | content           |
| document | PATCH     | `/documents/{id}/content/`            | update-content    |
| document | GET       | `/documents/{id}/cors-proxy/`         | cors-proxy        |
| document | POST      | `/documents/{id}/duplicate/`          | duplicate         |
| document | POST      | `/documents/{id}/favorite/`           | create-favorite   |
| document | DELETE    | `/documents/{id}/favorite/`           | delete-favorite   |
| document | GET       | `/documents/{id}/formatted-content/`  | formatted-content |
| document | POST      | `/documents/{id}/leave/`              | leave             |
| document | PUT       | `/documents/{id}/link-configuration/` | update-link       |
| document | GET       | `/documents/{id}/media-check/`        | media-check       |
| document | POST      | `/documents/{id}/move/`               | move              |
| document | POST      | `/documents/{id}/restore/`            | restore           |
| document | GET       | `/documents/{id}/tree/`               | tree              |
| document | GET       | `/documents/all/`                     | list-all          |
| document | POST      | `/documents/create-for-owner/`        | create-for-owner  |
| document | GET       | `/documents/favorite_list/` \*\*      | list-favorite     |
| document | GET       | `/documents/media-auth/`              | list-media-auth   |
| document | GET       | `/documents/search/`                  | search            |
| document | GET       | `/documents/trashbin/`                | list-deleted      |

\*\* **Should be fixed**

</details>

<details>

<summary>Resource: <code>document-version</code></summary>

| Resource         | HTTP verb | Endpoint                        | Action   |
| ---------------- | --------- | ------------------------------- | -------- |
| document-version | GET       | `/documents/{id}/versions/`     | list     |
| document-version | GET       | `/documents/{id}/versions/{id}` | retrieve |
| document-version | DELETE    | `/documents/{id}/versions/{id}` | delete   |

</details>

<details>

<summary>Resource: <code>document-access</code></summary>

| Resource        | HTTP verb | Endpoint                         | Action         |
| --------------- | --------- | -------------------------------- | -------------- |
| document-access | GET       | `/documents/{id}/accesses/`      | list           |
| document-access | POST      | `/documents/{id}/accesses/`      | create         |
| document-access | DELETE    | `/documents/{id}/accesses/{id}/` | delete         |
| document-access | GET       | `/documents/{id}/accesses/{id}/` | retrieve       |
| document-access | PATCH     | `/documents/{id}/accesses/{id}/` | update-partial |
| document-access | PUT       | `/documents/{id}/accesses/{id}/` | update         |

</details>

<details>

<summary>Resource: <code>document-access-request</code></summary>

| Resource                | HTTP verb | Endpoint                                      | Action   |
| ----------------------- | --------- | --------------------------------------------- | -------- |
| document-access-request | GET       | `/documents/{id}/ask-for-access/`             | list     |
| document-access-request | POST      | `/documents/{id}/ask-for-access/`             | create   |
| document-access-request | DELETE    | `/documents/{id}/ask-for-access/{id}/`        | delete   |
| document-access-request | GET       | `/documents/{id}/ask-for-access/{id}/`        | retrieve |
| document-access-request | POST      | `/documents/{id}/ask-for-access/{id}/accept/` | accept   |

</details>

<details>

<summary>Resource: <code>document-invitation</code></summary>

| Resource            | HTTP verb | Endpoint                            | Action         |
| ------------------- | --------- | ----------------------------------- | -------------- |
| document-invitation | GET       | `/documents/{id}/invitations/`      | list           |
| document-invitation | POST      | `/documents/{id}/invitations/`      | create         |
| document-invitation | DELETE    | `/documents/{id}/invitations/{id}/` | delete         |
| document-invitation | GET       | `/documents/{id}/invitations/{id}/` | retrieve       |
| document-invitation | PATCH     | `/documents/{id}/invitations/{id}/` | update-partial |
| document-invitation | PUT       | `/documents/{id}/invitations/{id}/` | update         |

</details>

<details>

<summary>Resource: <code>document-thread</code></summary>

| Resource        | HTTP verb | Endpoint                                  | Action    |
| --------------- | --------- | ----------------------------------------- | --------- |
| document-thread | GET       | `/documents/{id}/threads/`                | list      |
| document-thread | GET       | `/documents/{id}/threads/{id}/`           | retrieve  |
| document-thread | DELETE    | `/documents/{id}/threads/{id}/`           | delete    |
| document-thread | POST      | `/documents/{id}/threads/{id}/resolve/`   | resolve   |
| document-thread | POST      | `/documents/{id}/threads/{id}/unresolve/` | unresolve |

</details>

<details>

<summary>Resource: <code>document-thread-comment</code></summary>

| Resource                | HTTP verb | Endpoint                                                | Action          |
| ----------------------- | --------- | ------------------------------------------------------- | --------------- |
| document-thread-comment | GET       | `/documents/{id}/threads/{id}/comments/`                | list            |
| document-thread-comment | POST      | `/documents/{id}/threads/{id}/comments/`                | create          |
| document-thread-comment | GET       | `/documents/{id}/threads/{id}/comments/{id}/`           | retrieve        |
| document-thread-comment | PUT       | `/documents/{id}/threads/{id}/comments/{id}/`           | update          |
| document-thread-comment | PATCH     | `/documents/{id}/threads/{id}/comments/{id}/`           | update-partial  |
| document-thread-comment | DELETE    | `/documents/{id}/threads/{id}/comments/{id}/`           | delete          |
| document-thread-comment | POST      | `/documents/{id}/threads/{id}/comments/{id}/reactions/` | create-reaction |
| document-thread-comment | DELETE    | `/documents/{id}/threads/{id}/comments/{id}/reactions/` | delete-reaction |

</details>

<details>

<summary>Resource: <code>user</code></summary>

| Resource | HTTP verb | Endpoint                  | Action          |
| -------- | --------- | ------------------------- | --------------- |
| user     | GET       | `/users/`                 | list            |
| user     | PUT       | `/users/{id}/`            | update          |
| user     | PATCH     | `/users/{id}/`            | update-partial  |
| user     | GET       | `/users/me/`              | me              |
| user     | POST      | `/users/onboarding-done/` | onboarding-done |

</details>

### Drive

> `config` and `user-reconciliations` resources have been explicitly ignored as
> we think they are out-of-scope for a resource server exposition.

<details>

<summary>Resource: <code>item</code></summary>

| Resource | HTTP verb | Endpoint                          | Action          |
| -------- | --------- | --------------------------------- | --------------- |
| item     | GET       | `/items/`                         | list            |
| item     | POST      | `/items/`                         | create          |
| item     | DELETE    | `/items/{id}/`                    | soft-delete     |
| item     | GET       | `/items/{id}/`                    | retrieve        |
| item     | PATCH     | `/items/{id}/`                    | update-partial  |
| item     | PUT       | `/items/{id}/`                    | update          |
| item     | GET       | `/items/{id}/breadcrumb/`         | list-breadcrumb |
| item     | GET       | `/items/{id}/children/`           | list-children   |
| item     | POST      | `/items/{id}/children/`           | create-children |
| item     | GET       | `/items/{id}/download/`           | download        |
| item     | POST      | `/items/{id}/duplicate/`          | duplicate       |
| item     | GET       | `/items/{id}/export/`             | export          |
| item     | POST      | `/items/{id}/favorite/`           | create-favorite |
| item     | DELETE    | `/items/{id}/favorite/`           | delete-favorite |
| item     | DELETE    | `/items/{id}/hard-delete/`        | delete          |
| item     | PUT       | `/items/{id}/link-configuration/` | update-link     |
| item     | GET       | `/items/{id}/media-auth/`         | media-auth      |
| item     | POST      | `/items/{id}/move/`               | move            |
| item     | POST      | `/items/{id}/restore/`            | restore         |
| item     | GET       | `/items/{id}/tree/`               | tree            |
| item     | POST      | `/items/{id}/upload-ended/`       | upload-ended    |
| item     | GET       | `/items/{id}/wopi/`               | wopi            |
| item     | GET       | `/items/favorite_list/` \*\*      | list-favorite   |
| item     | GET       | `/items/media-auth/`              | list-media-auth |
| item     | GET       | `/items/recents/`                 | recents         |
| item     | GET       | `/items/search/`                  | search          |
| item     | GET       | `/items/trashbin/`                | list-deleted    |

\*\* **Should be fixed**

</details>

<details>

<summary>Resource: <code>item-access</code></summary>

| Resource    | HTTP verb | Endpoint                     | Action         |
| ----------- | --------- | ---------------------------- | -------------- |
| item-access | GET       | `/items/{id}/accesses/`      | list           |
| item-access | POST      | `/items/{id}/accesses/`      | create         |
| item-access | DELETE    | `/items/{id}/accesses/{id}/` | delete         |
| item-access | GET       | `/items/{id}/accesses/{id}/` | retrieve       |
| item-access | PATCH     | `/items/{id}/accesses/{id}/` | update-partial |
| item-access | PUT       | `/items/{id}/accesses/{id}/` | update         |

</details>

<details>

<summary>Resource: <code>item-invitation</code></summary>

| Resource        | HTTP verb | Endpoint                        | Action         |
| --------------- | --------- | ------------------------------- | -------------- |
| item-invitation | GET       | `/items/{id}/invitations/`      | list           |
| item-invitation | POST      | `/items/{id}/invitations/`      | create         |
| item-invitation | DELETE    | `/items/{id}/invitations/{id}/` | delete         |
| item-invitation | GET       | `/items/{id}/invitations/{id}/` | retrieve       |
| item-invitation | PATCH     | `/items/{id}/invitations/{id}/` | update-partial |
| item-invitation | PUT       | `/items/{id}/invitations/{id}/` | update         |

</details>

<details>

<summary>Resource: <code>user</code></summary>

| Resource | HTTP verb | Endpoint           | Action         |
| -------- | --------- | ------------------ | -------------- |
| user     | GET       | `/users/`          | list           |
| user     | GET       | `/users/contacts/` | list-contacts  |
| user     | PATCH     | `/users/{id}/`     | update-partial |
| user     | PUT       | `/users/{id}/`     | update         |
| user     | GET       | `/users/me/`       | me             |

</details>

### Meet

> `config` and `addons/sessions` resources have been explicitly ignored as we
> think they are out-of-scope for a resource server exposition.

<details>

<summary>Resource: <code>file</code></summary>

| Resource | HTTP verb | Endpoint                    | Action         |
| -------- | --------- | --------------------------- | -------------- |
| file     | GET       | `/files/`                   | list           |
| file     | POST      | `/files/`                   | create         |
| file     | PUT       | `/files/{id}`               | update         |
| file     | PATCH     | `/files/{id}`               | update-partial |
| file     | DELETE    | `/files/{id}`               | soft-delete    |
| file     | POST      | `/files/{id}/upload-ended/` | upload-ended   |
| file     | GET       | `/files/{id}/media-auth/`   | media-auth     |

</details>

<details>

<summary>Resource: <code>recording</code></summary>

| Resource  | HTTP verb | Endpoint                             | Action                |
| --------- | --------- | ------------------------------------ | --------------------- |
| recording | GET       | `/recordings/`                       | list                  |
| recording | GET       | `/recordings/{id}/`                  | retrieve              |
| recording | DELETE    | `/recordings/{id}/`                  | delete                |
| recording | POST      | `/recordings/external-process-hook/` | external-process-hook |
| recording | GET       | `/recordings/media-auth/`            | list-media-auth       |
| recording | POST      | `/recordings/storage-hook/`          | storage-hook          |

</details>

<details>

<summary>Resource: <code>resource-access</code></summary>

| Resource        | HTTP verb | Endpoint                   | Action         |
| --------------- | --------- | -------------------------- | -------------- |
| resource-access | GET       | `/resource-accesses/`      | list           |
| resource-access | POST      | `/resource-accesses/`      | create         |
| resource-access | GET       | `/resource-accesses/{id}/` | retrieve       |
| resource-access | PUT       | `/resource-accesses/{id}/` | update         |
| resource-access | PATCH     | `/resource-accesses/{id}/` | update-partial |
| resource-access | DELETE    | `/resource-accesses/{id}/` | delete         |

</details>

<details>

<summary>Resource: <code>room</code></summary>

| Resource | HTTP verb | Endpoint                           | Action              |
| -------- | --------- | ---------------------------------- | ------------------- |
| room     | GET       | `/rooms/`                          | list                |
| room     | POST      | `/rooms/`                          | create              |
| room     | GET       | `/rooms/{id}/`                     | retrieve            |
| room     | PUT       | `/rooms/{id}/`                     | update              |
| room     | PATCH     | `/rooms/{id}/`                     | update-partial      |
| room     | DELETE    | `/rooms/{id}/`                     | delete              |
| room     | POST      | `/rooms/{id}/enter/`               | enter               |
| room     | POST      | `/rooms/{id}/invite/`              | invite              |
| room     | POST      | `/rooms/{id}/mute-participant/`    | mute-participant    |
| room     | POST      | `/rooms/{id}/remove-participant/`  | remove-participant  |
| room     | POST      | `/rooms/{id}/rename/`              | rename              |
| room     | POST      | `/rooms/{id}/request-entry/`       | request-entry       |
| room     | POST      | `/rooms/{id}/start-recording/`     | start-recording     |
| room     | POST      | `/rooms/{id}/start-subtitle/`      | start-subtitle      |
| room     | POST      | `/rooms/{id}/stop-recording/`      | stop-recording      |
| room     | POST      | `/rooms/{id}/toggle-hand/`         | toggle-hand         |
| room     | POST      | `/rooms/{id}/update-participant/`  | update-participant  |
| room     | GET       | `/rooms/{id}/waiting-participant/` | waiting-participant |
| room     | POST      | `/rooms/creation-callback/`        | creation-callback   |
| room     | POST      | `/rooms/webhooks-livekit/`         | webhooks-livekit    |

</details>

<details>

<summary>Resource: <code>user</code></summary>

| Resource | HTTP verb | Endpoint       | Action         |
| -------- | --------- | -------------- | -------------- |
| user     | GET       | `/users/`      | list           |
| user     | PATCH     | `/users/{id}/` | update-partial |
| user     | PUT       | `/users/{id}/` | update         |
| user     | GET       | `/users/me/`   | me             |

</details>

## Token exchange request scopes

Given services, resources and API endpoint actions, we propose to define scopes given the following pattern:

<center><code>service:resource[:action]</code></center>

Two types of scope may be used: with or without the `action` field.

The first scope type must include the expected triplet to fully describe which
action will be performed on which service's resource:

- `service`: the target service that will handle the exchanged token
- `resource`: the resource the target service handles
- `action`: the action that will be performed on the resource (_e.g._ the
  endpoint attached to the service resource)

👉 Example scopes: `drive:item:create`, `docs:document-invitation:delete`, …

The second type of scope is optional and will describe the type of resource the
source service expects to send to the target service:

- `service`: the source service that requests an exchanged token
- `resource`: the resource the source service may submit

👉 Example scopes: `meet:recording`, `drive:user`, …

## Token exchange rules examples

In the following sections, we will introduce plausible _scenarii_ that can
occur between LaSuite services. For each scenario, example scopes, token
exchange request and implementations are provided.

> Note that those _scenarii_ are illustrative examples that may not reflect
> real implementations running in production.

### Save Meet recordings to Drive

When Meet records a call, the recording may be stored in a third-party drive
service once properly encoded. In the this example, we choose to save the
recording to LaSuite Drive.

| Source service | Source resource | Target service | Target resource | Scopes                                   |
| -------------- | --------------- | -------------- | --------------- | ---------------------------------------- |
| Meet           | recording       | Drive          | item            | `drive:item:create`, `meet:recording` \* |

\* optional

Since we want to write the recording to Drive, following our
`service:resource:action` scope pattern, we may restrict the request scope to
`drive:item:create`. Optionally, if we want to fine-tune permissions control in
Drive, we can also add the `meet:recording` scope so that when Drive receives
this request, it knows that the request corresponds to a meet recording storage
request and act consequently.

#### Example token exchange request

The token exchange request payload should contain the original user's
`access_token` as the subject token to introspect. This request should target
the Drive service audience for a specific resource (request user Drive's
workspace with the UUID `510902ae-e907-4177-b93a-37ae7c6c9105`):

```json
// Token exchange request example
{
  "subject_token": "...",
  "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
  "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
  "resource": "https://drive.example.org/external_api/v1.0/item/510902ae-e907-4177-b93a-37ae7c6c9105/children/",
  "audience": "106bf623-961f-4c81-9176-fd6446a21149", // Drive audience identifier
  "scope": "drive:item:create meet:recording",
  "requested_token_type": "urn:ietf:params:oauth:token-type:jwt"
}
```

As mentioned in the previous section, two scopes are claimed in this request,
but the `meet:recording` scope is optional and may be ignored if the target
Drive instance does not check permissions related to this scope.

> Note that we request a JWT token type in this case, but an opaque access
> token would also fit. Depending on extra informations it should carry (such
> as throttling policy, etc.), you should define expected token type
> consequently.

#### Source: Meet, example python implementation

The following code snippet may be used as an example implementation of the
source side of this request, _i.e._ the Meet service willing to store a
recording to Drive.

```python
import request

from menshen_client import (
    Configuration,
    TokenExchangeClient,
    TokenExchangeRequest,
    TokenExchangeResponse,
    TokenType,
)

# Configure the client
config = Configuration(
   client_id="meet",
   client_secret="super-secret",
   server_root_url="https://menshen.example.org",
)

# Create the client instance
client = TokenExchangeClient(config=config)

# We suppose we have the user workspace, e.g. "Recording" folder, from a previous request to drive
workspace = "..."

# We also suppose you are in a HTTP request context and have already parsed the bearer token
access_token = "..."

# Configure the resource
drive_instance_url = "https://drive.example.org"
drive_resource_endpoint = f"/external_api/v1.0/items/{workspace}/children/"
target_resource = f"{drive_instance_url}{drive_resource_endpoint}"

# Create the token exchange request
exchange_request = TokenExchangeRequest(
    subject_token=access_token,
    subject_token_type=MenshenSupportedTokenType.ACCESS_TOKEN,
    resource=target_resource,
    audience="106bf623-961f-4c81-9176-fd6446a21149",  # Drive audience identifier
    scope="drive:item:create meet:recording",
    requested_token_type=MenshenSupportedTokenType.JWT,
)

# Submit the request
exchange_response: TokenExchangeResponse = client.exchange(exchange_request)

# Create Meet recording file in Drive using the exchanged token
response = requests.post(
    target_resource,
    json={
        "type": "file",
        "filename": "recording-b2f22a8c-5509-4104-83eb-e9bce2265289.mp4",
    },
    headers={
        "Authorization": f"Bearer {exchange_response.access_token}",
        "Content-Type": "application/json",
    }
)

# [...] upload the file and notify drive that the upload ended
# using the same exchanged token
```

Exchanged token may be used multiple times for subsequent requests to the Drive
resource server API without particular restrictions until it expires. That
being stated, at the time of writing, depending on Menshen server rules
definition, a **throttling policy** may occur while using this exchanged token.

#### Target: Drive, example python implementation

From the target service perspective (Drive in this example), we should also
configure the authorization server client to introspect received exchanged
token and validate the file storage request.

```python
import request

from menshen_client import (
    Configuration,
    IntrospectionRequest,
    IntrospectionResponse,
    TokenExchangeClient,
)

# Configure the client
config = Configuration(
   client_id="drive",
   client_secret="super-secret",
   server_root_url="https://menshen.example.org",
)

# Create the client instance
client = TokenExchangeClient(config=config)

# We suppose you are in a HTTP request context and have already parsed the bearer token
request_token = "..."

# Create the token introspection request
introspection_request = IntrospectionRequest(token=request_token)

# Get the token introspection response
introspection_response: IntrospectionResponse = client.introspect(introspection_request)

if not introspection_response.active:
    raise Exception

# Check user permissions
# [...]

# Extra permission check from scopes
expected_scopes = {"drive:item:create", "meet:recording"}
if not expected_scopes.issubset(
    set(introspection_response.scope.split())
):
    raise Exception
```

In this example implementation, extra permissions checking given scopes are a
bit naive. We think they should not be hard-coded in the service but rather
implemented as administrator-defined configurations.
