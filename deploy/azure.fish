#!/usr/bin/env fish
# Deploys InteraX (Postgres + FastAPI server + Next.js web app) to Azure Container Apps.
#
#   fish deploy/azure.fish
#
# Safe to re-run. Images are tagged with a hash of their build folder, so a
# folder that hasn't changed isn't uploaded or rebuilt, and an unchanged db
# isn't restarted (no CSV reload). The server is always restarted so new
# settings/secrets from .env take effect.
#
# These are read from the repo-root .env (a variable already set in the shell wins):
#   UNSLOTH_BASE_URL, UNSLOTH_MODEL, UNSLOTH_API_KEY  - OCR model endpoint (must be reachable from Azure)
#   RXLABEL_BASE_URL, RXLABEL_API_KEY                 - drug-interaction API used by /api/interactions
#   UPLOAD_TTL                                        - seconds before an upload is deleted (optional, default 3600)
#   SESSION_TTL, SESSION_IDLE_TTL                     - clinician session lifetime / idle timeout in seconds (optional)
#   BOOTSTRAP_ADMIN_USERNAME, BOOTSTRAP_ADMIN_PASSWORD
#       - optional; an admin created whenever the users table is empty. Recommended
#         here: the db has no volume, so every db restart deletes all users.
#
# What gets created in the resource group:
#   - Container registry (ACR) $ACR: stores our Docker images; images are built
#     in Azure (`az acr build`), so the Mac's ARM architecture doesn't matter.
#   - Container Apps environment $ACA_ENV: the shared network the apps live in.
#   - App interax-db: Postgres, internal TCP ingress only (not on the internet).
#     No volume: the vocabulary reloads from the CSVs in the image on every
#     start (takes a little while), and users/sessions/uploads are lost.
#   - App interax-server: the FastAPI API, internal HTTP ingress only.
#   - App interax (web): the Next.js app, the only public HTTPS URL. It proxies
#     /api/* to the server, so the browser sees one origin.

set -l TEAM 89
set -l RG rg-team$TEAM
set -l LOCATION swedencentral
set -l ACA_ENV aca-team$TEAM-sandbox
# Registry names are globally unique, lowercase letters/digits only.
set -l ACR acrteam{$TEAM}interax
set -l DB_APP interax-db
set -l SERVER_APP interax-server
# The app name is the first label of the public URL: https://interax.<env-domain>
set -l WEB_APP interax
# Used to force a new revision (= restart) when only secrets changed.
set -l STAMP (date +%Y%m%d%H%M%S)

set -l PG_DB interax
set -l PG_USER interax

# Inside the environment, apps reach each other by app name. Internal HTTP
# ingress listens on port 80 and forwards to the server's port 8080.
set -l SERVER_INTERNAL_URL http://$SERVER_APP

function step
    set_color --bold blue
    echo "==> $argv"
    set_color normal
end

function fail
    set_color red
    echo "error: $argv" >&2
    set_color normal
    exit 1
end

# Short content hash of a build folder, roughly mirroring its .dockerignore.
# Dockerfile is deliberately included: changing it must trigger a rebuild.
# Extra arguments (e.g. build args) are mixed into the hash.
function context_hash --argument-names dir
    set -l extra $argv
    set -e extra[1]
    pushd $dir; or return 1
    begin
        find . -type f \
            -not -path './serverenv/*' -not -path './.venv/*' -not -path './venv/*' \
            -not -path '*/__pycache__/*' -not -name '*.py[cod]' \
            -not -path '*/.pytest_cache/*' -not -path '*/.ruff_cache/*' \
            -not -path './node_modules/*' -not -path './.next/*' -not -name '*.tsbuildinfo' \
            -not -name '.env' -not -name '.env.*' -not -name '.DS_Store' \
            -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256
        for value in $extra
            echo $value
        end
    end | shasum -a 256 | string sub -l 12
    popd
end

# Builds $repo:$tag from $dir in Azure unless that tag already exists.
# Extra arguments are passed to `az acr build` (e.g. --build-arg X=y).
function build_if_missing --argument-names acr repo tag dir
    set -l extra $argv
    set -e extra[1..4]
    if az acr repository show --name $acr --image $repo:$tag -o none 2>/dev/null
        step "$repo:$tag already in registry, skipping build"
        return 0
    end
    step "Building $repo:$tag in Azure from $dir"
    az acr build --registry $acr --image $repo:$tag --platform linux/amd64 $extra $dir
end

cd (dirname (status filename))/..; or fail "cannot cd to repo root"

# Last `KEY=value` in .env, surrounding quotes stripped. No ${VAR} expansion.
function dotenv_get --argument-names key
    test -f .env; or return 1
    set -l value (string match -rg '^\s*(?:export\s+)?'$key'\s*=\s*(.*)$' < .env)[-1]
    or return 1
    string trim -- $value | string trim -c '"\''
end

for key in UNSLOTH_BASE_URL UNSLOTH_MODEL UNSLOTH_API_KEY RXLABEL_BASE_URL RXLABEL_API_KEY \
        UPLOAD_TTL SESSION_TTL SESSION_IDLE_TTL BOOTSTRAP_ADMIN_USERNAME BOOTSTRAP_ADMIN_PASSWORD \
        IRIS_HOST IRIS_PORT IRIS_HTTP_PORT IRIS_NAMESPACE IRIS_USER IRIS_PASSWORD
    set -q $key; and continue
    set -l value (dotenv_get $key)
    test -n "$value"; and set -gx $key $value
end

step "Settings"
echo "UNSLOTH_BASE_URL = "(set -q UNSLOTH_BASE_URL; and echo $UNSLOTH_BASE_URL; or echo "(not set)")
echo "UNSLOTH_MODEL    = "(set -q UNSLOTH_MODEL; and echo $UNSLOTH_MODEL; or echo "(not set)")
echo "UNSLOTH_API_KEY  = "(set -q UNSLOTH_API_KEY; and echo "(set, hidden)"; or echo "(not set)")
echo "RXLABEL_BASE_URL = "(set -q RXLABEL_BASE_URL; and echo $RXLABEL_BASE_URL; or echo "(not set)")
echo "RXLABEL_API_KEY  = "(set -q RXLABEL_API_KEY; and echo "(set, hidden)"; or echo "(not set)")
echo "IRIS             = "(set -q IRIS_HOST; and echo "$IRIS_HOST:"(set -q IRIS_PORT; and echo $IRIS_PORT; or echo 1972)" (password "(set -q IRIS_PASSWORD; and echo set; or echo "not set")")"; or echo "(not set, interactions use the fallback)")
echo "BOOTSTRAP_ADMIN  = "(set -q BOOTSTRAP_ADMIN_USERNAME; and set -q BOOTSTRAP_ADMIN_PASSWORD; and echo "$BOOTSTRAP_ADMIN_USERNAME (password hidden)"; or echo "(not set)")

step "Hashing build folders"
set -l DB_TAG (context_hash ./database)
set -l SERVER_TAG (context_hash ./server)
# The server URL is baked into the web build, so it's part of the tag.
set -l WEB_TAG (context_hash ./app $SERVER_INTERNAL_URL)
test -n "$DB_TAG" -a -n "$SERVER_TAG" -a -n "$WEB_TAG"; or fail "could not hash build folders"
echo "database -> $DB_TAG"
echo "server   -> $SERVER_TAG"
echo "web      -> $WEB_TAG"

step "Installing/upgrading the containerapp CLI extension"
az extension add --name containerapp --upgrade --only-show-errors
or fail "could not install the containerapp extension"

step "Registering resource providers (no-op if already registered)"
for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry
    az provider register --namespace $ns --wait --only-show-errors
    or echo "warning: could not register $ns (maybe no permission); continuing"
end

if not az acr show --name $ACR --resource-group $RG -o none 2>/dev/null
    step "Creating container registry $ACR"
    az acr create --name $ACR --resource-group $RG --location $LOCATION \
        --sku Basic --admin-enabled true -o none --only-show-errors
    or fail "could not create registry $ACR (name taken? change ACR at the top)"
end
set -l ACR_SERVER (az acr show --name $ACR --resource-group $RG --query loginServer -o tsv)
set -l ACR_USER (az acr credential show --name $ACR --query username -o tsv)
set -l ACR_PASS (az acr credential show --name $ACR --query 'passwords[0].value' -o tsv)
test -n "$ACR_PASS"; or fail "could not read registry credentials"

build_if_missing $ACR interax-db $DB_TAG ./database
or fail "db image build failed"
build_if_missing $ACR interax-server $SERVER_TAG ./server
or fail "server image build failed"
build_if_missing $ACR interax-web $WEB_TAG ./app --build-arg API_INTERNAL_URL=$SERVER_INTERNAL_URL
or fail "web image build failed"

if not az containerapp env show --name $ACA_ENV --resource-group $RG -o none 2>/dev/null
    step "Creating Container Apps environment $ACA_ENV"
    az containerapp env create --name $ACA_ENV --resource-group $RG \
        --location $LOCATION -o none --only-show-errors
    or fail "could not create environment $ACA_ENV"
end

set -l DB_IMAGE $ACR_SERVER/interax-db:$DB_TAG
set -l PG_PASS
if az containerapp show --name $DB_APP --resource-group $RG -o none 2>/dev/null
    # Reuse the running db's password so an untouched db keeps working.
    set PG_PASS (az containerapp secret show --name $DB_APP --resource-group $RG \
        --secret-name pg-password --query value -o tsv 2>/dev/null)
    set -l current_image (az containerapp show --name $DB_APP --resource-group $RG \
        --query 'properties.template.containers[0].image' -o tsv)

    if test -z "$PG_PASS"
        step "Could not read db password, setting a new one and restarting $DB_APP"
        set PG_PASS (openssl rand -hex 24)
        az containerapp secret set --name $DB_APP --resource-group $RG \
            --secrets pg-password=$PG_PASS -o none --only-show-errors
        or fail "could not update db secrets"
        # Fresh revision = fresh container = initdb runs with the new password.
        az containerapp update --name $DB_APP --resource-group $RG \
            --image $DB_IMAGE --revision-suffix r$STAMP -o none --only-show-errors
        or fail "could not update $DB_APP"
    else if test "$current_image" != "$DB_IMAGE"
        step "Updating $DB_APP to $DB_TAG (db restarts and reloads the CSVs)"
        az containerapp update --name $DB_APP --resource-group $RG \
            --image $DB_IMAGE -o none --only-show-errors
        or fail "could not update $DB_APP"
    else
        step "$DB_APP unchanged, leaving it running"
    end
else
    step "Creating $DB_APP"
    # Hex keeps it URL-safe for DATABASE_URL.
    set PG_PASS (openssl rand -hex 24)
    # max-replicas 1: each replica would be a separate, independent database.
    az containerapp create --name $DB_APP --resource-group $RG --environment $ACA_ENV \
        --image $DB_IMAGE \
        --registry-server $ACR_SERVER --registry-username $ACR_USER --registry-password $ACR_PASS \
        --ingress internal --transport tcp --target-port 5432 --exposed-port 5432 \
        --cpu 1 --memory 2Gi --min-replicas 1 --max-replicas 1 \
        --secrets pg-password=$PG_PASS \
        --env-vars POSTGRES_DB=$PG_DB POSTGRES_USER=$PG_USER POSTGRES_PASSWORD=secretref:pg-password \
        -o none --only-show-errors
    or fail "could not create $DB_APP"
end

# Inside the environment, apps reach each other by app name + exposed port.
set -l DATABASE_URL "postgresql://$PG_USER:$PG_PASS@$DB_APP:5432/$PG_DB"

set -l server_secrets database-url=$DATABASE_URL
set -l server_env DATABASE_URL=secretref:database-url
for key in UPLOAD_TTL SESSION_TTL SESSION_IDLE_TTL UNSLOTH_BASE_URL UNSLOTH_MODEL RXLABEL_BASE_URL \
        IRIS_HOST IRIS_PORT IRIS_HTTP_PORT IRIS_NAMESPACE IRIS_USER
    set -q $key; and set -a server_env $key=$$key
end
if set -q UNSLOTH_API_KEY
    set -a server_secrets unsloth-api-key=$UNSLOTH_API_KEY
    set -a server_env UNSLOTH_API_KEY=secretref:unsloth-api-key
end
if set -q RXLABEL_API_KEY
    set -a server_secrets rxlabel-api-key=$RXLABEL_API_KEY
    set -a server_env RXLABEL_API_KEY=secretref:rxlabel-api-key
end
if set -q IRIS_PASSWORD
    set -a server_secrets iris-password=$IRIS_PASSWORD
    set -a server_env IRIS_PASSWORD=secretref:iris-password
end
if set -q BOOTSTRAP_ADMIN_USERNAME; and set -q BOOTSTRAP_ADMIN_PASSWORD
    set -a server_secrets bootstrap-admin-password=$BOOTSTRAP_ADMIN_PASSWORD
    set -a server_env BOOTSTRAP_ADMIN_USERNAME=$BOOTSTRAP_ADMIN_USERNAME \
        BOOTSTRAP_ADMIN_PASSWORD=secretref:bootstrap-admin-password
end

set -l SERVER_IMAGE $ACR_SERVER/interax-server:$SERVER_TAG
if az containerapp show --name $SERVER_APP --resource-group $RG -o none 2>/dev/null
    step "Updating $SERVER_APP"
    az containerapp secret set --name $SERVER_APP --resource-group $RG \
        --secrets $server_secrets -o none --only-show-errors
    or fail "could not update server secrets"
    # New revision every time: secret changes alone don't restart the app.
    az containerapp update --name $SERVER_APP --resource-group $RG \
        --image $SERVER_IMAGE --set-env-vars $server_env \
        --revision-suffix r$STAMP -o none --only-show-errors
    or fail "could not update $SERVER_APP"
else
    step "Creating $SERVER_APP"
    az containerapp create --name $SERVER_APP --resource-group $RG --environment $ACA_ENV \
        --image $SERVER_IMAGE \
        --registry-server $ACR_SERVER --registry-username $ACR_USER --registry-password $ACR_PASS \
        --ingress internal --target-port 8080 \
        --cpu 0.5 --memory 1Gi --min-replicas 1 --max-replicas 1 \
        --secrets $server_secrets \
        --env-vars $server_env \
        -o none --only-show-errors
    or fail "could not create $SERVER_APP"
end

# Internal only (the web app is the public entry point), and plain HTTP allowed
# so the web app's http://interax-server calls aren't redirected to HTTPS
# (a redirect would drop POST bodies). Also converts an older external server.
step "Making $SERVER_APP internal"
az containerapp ingress update --name $SERVER_APP --resource-group $RG \
    --type internal --allow-insecure true -o none --only-show-errors
or fail "could not update $SERVER_APP ingress"

set -l WEB_IMAGE $ACR_SERVER/interax-web:$WEB_TAG
if az containerapp show --name $WEB_APP --resource-group $RG -o none 2>/dev/null
    step "Updating $WEB_APP"
    az containerapp update --name $WEB_APP --resource-group $RG \
        --image $WEB_IMAGE -o none --only-show-errors
    or fail "could not update $WEB_APP"
else
    step "Creating $WEB_APP"
    # Stateless (sessions live in the db), so it may scale out.
    az containerapp create --name $WEB_APP --resource-group $RG --environment $ACA_ENV \
        --image $WEB_IMAGE \
        --registry-server $ACR_SERVER --registry-username $ACR_USER --registry-password $ACR_PASS \
        --ingress external --target-port 3000 \
        --cpu 0.5 --memory 1Gi --min-replicas 1 --max-replicas 3 \
        -o none --only-show-errors
    or fail "could not create $WEB_APP"
end

set -l FQDN (az containerapp show --name $WEB_APP --resource-group $RG \
    --query properties.configuration.ingress.fqdn -o tsv)

step "Done"
echo "App:     https://$FQDN"
echo "Doctor:  https://$FQDN/doctor"
echo "API:     https://$FQDN/api/... (proxied to $SERVER_APP, which is not public)"
echo
echo "If the db was (re)started, give it a minute or two to load the CSVs before"
echo "DB-backed endpoints work. Logs:"
echo "  az containerapp logs show -n $DB_APP -g $RG --type console --follow"
echo "  az containerapp logs show -n $SERVER_APP -g $RG --type console --follow"
echo "  az containerapp logs show -n $WEB_APP -g $RG --type console --follow"
echo
echo "Manage clinician accounts (prompts for the password):"
echo "  az containerapp exec -n $SERVER_APP -g $RG --command 'python -m app.manage create-user <name> --role clinician'"

if not set -q BOOTSTRAP_ADMIN_USERNAME; or not set -q BOOTSTRAP_ADMIN_PASSWORD
    set_color yellow
    echo
    echo "warning: BOOTSTRAP_ADMIN_USERNAME/PASSWORD not set. The db has no volume, so after"
    echo "every db restart there are no users until you create one with the command above."
    set_color normal
end

if not set -q UNSLOTH_BASE_URL
    set_color yellow
    echo
    echo "warning: UNSLOTH_BASE_URL not set; /api/scan will try 127.0.0.1:8000 inside the"
    echo "container and fail. Set it to a publicly reachable model endpoint and re-run."
    set_color normal
end

if not set -q RXLABEL_BASE_URL
    set_color yellow
    echo
    echo "warning: RXLABEL_BASE_URL not set; /api/interactions will fail. Add it to .env and re-run."
    set_color normal
end
