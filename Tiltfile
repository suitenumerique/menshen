load('ext://uibutton', 'cmd_button', 'bool_input', 'location')

# Reload configuration and apply it when the Helm Chart is changed
watch_file('./src/helm/')

# =========================================================
# Images build
# =========================================================

docker_build(
    'localhost:5001/menshen:backend-development',
    context='.',
    dockerfile='./src/backend/Dockerfile',
    only=[
      './src/backend',
      './docker',
    ],
    target = 'backend-production',
    build_args={'DOCKER_USER': '1000:1000'},
    live_update=[
        sync(
            './src/backend',
            '/app'
        ),
        run(
            'uv sync',
            trigger=['./src/backend/uv.lock']
        )
    ]
)

# =========================================================
# Resources
# =========================================================

k8s_resource(
    'menshen-backend-migrate',
    resource_deps=['dev-backend-postgres']
)

k8s_resource(
    'menshen-backend-createsuperuser',
    resource_deps=['menshen-backend-migrate']
)

k8s_resource(
    'dev-backend-keycloak',
    resource_deps=['dev-backend-keycloak-pg']
)

k8s_resource(
    'menshen-backend',
    resource_deps=[
        'menshen-backend-migrate',
        'dev-backend-redis',
        'dev-backend-keycloak',
        'dev-backend-postgres'
    ]
)

# Use Helmfile command to generate the Chart manifest
k8s_yaml(
  local('cd ./src/helm && helmfile -n menshen -e dev template .')
)

# =========================================================
# Custom UI
# =========================================================

#
# Make migrations from the UI
#
migration = '''
set -eu
# get k8s pod name from tilt resource name
POD_NAME="$(tilt get kubernetesdiscovery menshen-backend -ojsonpath='{.status.pods[0].name}')"
kubectl -n menshen exec "$POD_NAME" -- uv run python manage.py makemigrations
'''
cmd_button('Make migration',
           argv=['sh', '-c', migration],
           resource='menshen-backend',
           icon_name='developer_board',
           text='Run makemigration',
)

#
# Migrate from the UI
#
pod_migrate = '''
set -eu
# get k8s pod name from tilt resource name
POD_NAME="$(tilt get kubernetesdiscovery menshen-backend -ojsonpath='{.status.pods[0].name}')"
kubectl -n menshen exec "$POD_NAME" -- uv run python manage.py migrate --no-input
'''
cmd_button('Migrate db',
           argv=['sh', '-c', pod_migrate],
           resource='menshen-backend',
           icon_name='developer_board',
           text='Run database migration',
)
